"""HousingAgent — Sheikh Zayed Housing Programme worker.

Extracts case params from message + memory, calls rules engine + risk scorer,
returns drafts in both languages. NEVER invents policy.

Behavior changes (May 2026):
- Reads memory_snippets to find facts from prior turns (cross-turn extraction).
- Returns a follow-up question if a critical field is missing, instead of guessing.
- If we have enough to compute viable plans, returns the plan options.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

from ..tools.risk_score import risk_score
from ..tools.szhp_rules import SzhpCase, SzhpDecision, szhp_rules_engine
from ..tools.uaepass import uaepass_lookup


@dataclass
class HousingWorkerResult:
    draft_en: str
    draft_ar: str
    decision: SzhpDecision | None
    tool_calls: list[dict]
    needs_more_info: list[str]


# ---- Extraction helpers ----------------------------------------------------

_NUMBER_RE = re.compile(r"(\d[\d,]*\.?\d*)")


def _extract_amount(text: str, *patterns: str) -> float | None:
    """Return the first amount matched by any of the patterns."""
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except (ValueError, IndexError):
                continue
    return None


def _months_in_arrears(text: str) -> int | None:
    m = re.search(r"(\d{1,2})\s*(?:months?|أشهر|شهر)\s*(?:behind|in arrears|late|متأخر)?", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"behind\s+(?:by\s+)?(\d{1,2})", text, re.I)
    if m:
        return int(m.group(1))
    return None


def _employment(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b(lost|losing).*\b(job|work)\b|\bunemployed\b|\bjobless\b|بطالة|فقدت\s*عملي", t):
        return "unemployed"
    if re.search(r"\bretired\b|\bpension\b|متقاعد", t):
        return "retired"
    if re.search(r"\bself[- ]?employed\b|\bfreelanc(er|ing)\b|أعمل\s*لحسابي", t):
        return "self_employed"
    if re.search(r"\b(employed|i work at|my job|monthly salary|راتب|أعمل)\b", t):
        return "employed"
    return None


def _has_prior(text: str) -> bool | None:
    t = text.lower()
    if re.search(r"already\s+rescheduled|previous(ly)?\s+rescheduled|prior\s+reschedul", t):
        return True
    return None


def _gather_from_history(memory_snippets: list[str], current_text: str) -> dict:
    """Merge facts from current message + recent user turns. Later turns win."""
    facts: dict = {}
    # Iterate oldest → newest so the most recent value wins on conflict
    all_texts = [s.split(": ", 1)[-1] for s in memory_snippets if "] user:" in s] + [current_text]
    for t in all_texts:
        if (v := _months_in_arrears(t)) is not None:
            facts["months_in_arrears"] = v
        if (v := _employment(t)) is not None:
            facts["employment_status"] = v
        if (v := _has_prior(t)) is not None:
            facts["has_prior_reschedule"] = v
        if (v := _extract_amount(t, r"(?:salary|income|راتب)[^0-9]{0,15}(\d[\d,]*\.?\d*)")) is not None:
            facts["monthly_income_aed"] = v
        if (v := _extract_amount(t, r"(?:installment|قسط)[^0-9]{0,15}(\d[\d,]*\.?\d*)")) is not None:
            facts["monthly_installment_aed"] = v
        if (v := _extract_amount(t, r"(?:balance|outstanding|remaining|متبقي|رصيد)[^0-9]{0,15}(\d[\d,]*\.?\d*)")) is not None:
            facts["outstanding_balance_aed"] = v
    return facts


def _build_case(*, user_id: str, current_text: str, memory_snippets: list[str]) -> tuple[SzhpCase | None, list[str]]:
    """Return (case, missing_critical_fields)."""
    profile = uaepass_lookup(user_id)
    if not profile:
        return None, ["emirates_id_verified"]

    facts = _gather_from_history(memory_snippets, current_text)
    age = 2026 - int(profile.date_of_birth[:4])

    missing: list[str] = []
    if "monthly_income_aed" not in facts:
        missing.append("monthly_income_aed")
    if "outstanding_balance_aed" not in facts:
        missing.append("outstanding_balance_aed")

    if missing:
        # We genuinely don't know — return partial case marked needs-info.
        return None, missing

    # Sensible defaults only for fields we can infer cheaply or that don't change outcome much
    case = SzhpCase(
        emirates_id=profile.emirates_id,
        months_in_arrears=facts.get("months_in_arrears", 0),
        monthly_income_aed=facts["monthly_income_aed"],
        monthly_installment_aed=facts.get("monthly_installment_aed", facts["outstanding_balance_aed"] / 60),
        outstanding_balance_aed=facts["outstanding_balance_aed"],
        age=age,
        employment_status=facts.get("employment_status", "employed"),
        dependents=0,
        has_prior_reschedule=facts.get("has_prior_reschedule", False),
    )
    return case, []


def _ask_for_missing(missing: list[str], language: str) -> tuple[str, str]:
    """Phrase a friendly follow-up asking for the most important missing field."""
    en_label = {
        "monthly_income_aed": "your monthly income (AED)",
        "outstanding_balance_aed": "the outstanding balance on your housing loan (AED)",
        "emirates_id_verified": "a valid Emirates ID (format 784-YYYY-XXXXXXX-X)",
    }
    ar_label = {
        "monthly_income_aed": "راتبك الشهري (بالدرهم)",
        "outstanding_balance_aed": "الرصيد المتبقي على قرض السكن (بالدرهم)",
        "emirates_id_verified": "رقم هوية صحيح (بصيغة 784-YYYY-XXXXXXX-X)",
    }
    asks_en = ", ".join(en_label.get(m, m) for m in missing)
    asks_ar = "، ".join(ar_label.get(m, m) for m in missing)

    en = (
        f"To check your eligibility for rescheduling, I need {asks_en}. "
        "You can type the number — for example: \"my salary is 15000 and balance is 250000\"."
    )
    ar = (
        f"لأتحقق من أهليتك لإعادة الجدولة، أحتاج إلى {asks_ar}. "
        "يمكنك كتابة الرقم مباشرة — مثلًا: «راتبي 15000 والرصيد 250000»."
    )
    return en, ar


# ---- Public entrypoint -----------------------------------------------------

async def run_housing_agent(*, text: str, user_id: str, language: str, memory_snippets: list[str] | None = None) -> HousingWorkerResult:
    memory_snippets = memory_snippets or []
    case, missing = _build_case(user_id=user_id, current_text=text, memory_snippets=memory_snippets)
    tool_calls: list[dict] = [{"tool": "uaepass_lookup", "args": {"emirates_id": user_id}}]

    if case is None and "emirates_id_verified" in missing:
        return HousingWorkerResult(
            draft_en=(
                "I couldn't verify your Emirates ID. Please share a valid Emirates ID "
                "(format: 784-YYYY-XXXXXXX-X) so I can pull up your housing file."
            ),
            draft_ar=(
                "لم أتمكن من التحقق من هويتك الإماراتية. يرجى مشاركة رقم هوية صحيح "
                "(الصيغة: 784-YYYY-XXXXXXX-X) لأتمكن من فتح ملفك."
            ),
            decision=None,
            tool_calls=tool_calls,
            needs_more_info=["emirates_id_verified"],
        )

    if case is None:
        en, ar = _ask_for_missing(missing, language)
        return HousingWorkerResult(
            draft_en=en,
            draft_ar=ar,
            decision=None,
            tool_calls=tool_calls + [{"tool": "needs_more_info", "args": {"fields": missing}}],
            needs_more_info=missing,
        )

    # We have a real case — run the rules engine + risk scorer.
    decision = szhp_rules_engine(case)
    risk = risk_score(
        months_in_arrears=case.months_in_arrears,
        dti=(case.monthly_installment_aed / max(case.monthly_income_aed, 1.0)),
        employment_status=case.employment_status,
        dependents=case.dependents,
        prior_reschedule=case.has_prior_reschedule,
    )
    tool_calls += [
        {"tool": "szhp_rules_engine", "args": {"case_id": case.emirates_id}, "result": decision.recommendation},
        {"tool": "risk_score", "args": {"case_id": case.emirates_id}, "result": {"p_default": round(risk.p_default, 3), "band": risk.band}},
    ]

    citation_block = "; ".join(f"{h.rule_id}: {h.description}" for h in decision.rule_hits[:3])

    draft_en = (
        f"{decision.summary_en}\n\n"
        f"Risk band: {risk.band} (probability of default {risk.p_default:.0%}). "
        f"Rules consulted: {citation_block}."
    )
    draft_ar = (
        f"{decision.summary_ar}\n\n"
        f"درجة المخاطر: {risk.band} (احتمالية التعثر {risk.p_default:.0%}). "
        f"القواعد المطبقة: {citation_block}."
    )

    logger.info(
        f"housing_agent: rec={decision.recommendation} conf={decision.confidence:.2f} "
        f"risk={risk.band} months={case.months_in_arrears} income={case.monthly_income_aed:.0f} "
        f"balance={case.outstanding_balance_aed:.0f}"
    )
    return HousingWorkerResult(
        draft_en=draft_en,
        draft_ar=draft_ar,
        decision=decision,
        tool_calls=tool_calls,
        needs_more_info=[],
    )
