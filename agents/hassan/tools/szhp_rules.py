"""Sheikh Zayed Housing Programme rescheduling rules engine.

DETERMINISTIC. Agent NEVER invents policy. On stage we show this code and say:
"the agent does not hallucinate rules — it calls this Python function".

Behavior:
- Tries the standard 12-month plan first.
- If the DTI is too high, extends to 18, 24, then 36 months until viable.
- If even 36 months can't get DTI under the ceiling: manual_review (genuinely needs human).
- Returns ALL viable plans so the citizen can pick a payment they can afford.
- Returns rule citations for every decision — this is the audit trail content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Recommendation = Literal["approve", "approve_with_conditions", "decline", "manual_review"]


@dataclass
class SzhpCase:
    emirates_id: str
    months_in_arrears: int
    monthly_income_aed: float
    monthly_installment_aed: float
    outstanding_balance_aed: float
    age: int
    employment_status: Literal["employed", "self_employed", "unemployed", "retired"]
    dependents: int = 0
    has_prior_reschedule: bool = False


@dataclass
class PlanOption:
    months: int
    monthly_aed: float
    dti: float
    affordable: bool

    def as_dict(self) -> dict:
        return {
            "months": self.months,
            "monthly_aed": round(self.monthly_aed, 2),
            "dti": round(self.dti, 3),
            "affordable": self.affordable,
        }


@dataclass
class RuleHit:
    rule_id: str
    description: str
    weight: float    # 0..1; positive = supports approval, negative = blocks


@dataclass
class SzhpDecision:
    recommendation: Recommendation
    confidence: float
    proposed_plan_months: int | None
    new_monthly_installment_aed: float | None
    rule_hits: list[RuleHit]
    plan_options: list[PlanOption] = field(default_factory=list)
    summary_en: str = ""
    summary_ar: str = ""

    def as_dict(self) -> dict:
        return {
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 3),
            "proposed_plan_months": self.proposed_plan_months,
            "new_monthly_installment_aed": (
                round(self.new_monthly_installment_aed, 2)
                if self.new_monthly_installment_aed is not None
                else None
            ),
            "plan_options": [p.as_dict() for p in self.plan_options],
            "rule_hits": [
                {"rule_id": r.rule_id, "description": r.description, "weight": r.weight}
                for r in self.rule_hits
            ],
            "summary_en": self.summary_en,
            "summary_ar": self.summary_ar,
        }


# ---- Programme parameters --------------------------------------------------

MAX_DTI = 0.45              # Debt-to-income ceiling for new installment
MIN_INCOME_AED = 8_000
HARDSHIP_THRESHOLD = 3      # months arrears that trigger hardship pathway
PLAN_HORIZONS = (12, 18, 24, 36)   # Try shortest first; longer = lower monthly
SENIOR_PLAN_CAP_MONTHS = 18        # Age >= 60 capped at 18 months


def _plan_for(months: int, balance: float, income: float, max_dti: float) -> PlanOption:
    monthly = balance / months if months > 0 else 0.0
    dti = monthly / max(income, 1.0)
    return PlanOption(months=months, monthly_aed=monthly, dti=dti, affordable=(dti <= max_dti))


def szhp_rules_engine(case: SzhpCase) -> SzhpDecision:
    hits: list[RuleHit] = []

    # R1: Employment status
    if case.employment_status == "unemployed":
        hits.append(RuleHit("SZHP-R1.1", "Unemployed — escalate to social-support pathway", -0.6))
    elif case.employment_status == "retired":
        hits.append(RuleHit("SZHP-R1.2", "Retired — pension-based rescheduling track", 0.2))
    else:
        hits.append(RuleHit("SZHP-R1.0", "Active employment confirmed", 0.3))

    # R2: Income floor
    if case.monthly_income_aed < MIN_INCOME_AED:
        hits.append(RuleHit("SZHP-R2.1", f"Income below AED {MIN_INCOME_AED:,} floor — reduced options", -0.3))
    else:
        hits.append(RuleHit("SZHP-R2.0", "Income above programme floor", 0.2))

    # R3: Hardship pathway eligibility (extends max plan length)
    if case.months_in_arrears >= HARDSHIP_THRESHOLD:
        hits.append(
            RuleHit(
                "SZHP-R3.1",
                f"Arrears ≥ {HARDSHIP_THRESHOLD} months — eligible for hardship pathway (longer terms)",
                0.4,
            )
        )
    else:
        hits.append(RuleHit("SZHP-R3.0", "Arrears below hardship threshold — standard track", 0.1))

    # R4: Prior reschedule penalty
    if case.has_prior_reschedule:
        hits.append(RuleHit("SZHP-R4.1", "Prior reschedule on file — confidence reduced", -0.2))

    # R5: Senior cap
    senior = case.age >= 60
    if senior:
        hits.append(RuleHit("SZHP-R5.1", f"Senior applicant (≥60) — plan capped at {SENIOR_PLAN_CAP_MONTHS} months", -0.1))

    # ---- Compute plan options ----
    horizons = tuple(h for h in PLAN_HORIZONS if not senior or h <= SENIOR_PLAN_CAP_MONTHS)
    if case.outstanding_balance_aed <= 0:
        # No balance to reschedule — already cleared
        return SzhpDecision(
            recommendation="approve",
            confidence=0.95,
            proposed_plan_months=None,
            new_monthly_installment_aed=None,
            rule_hits=hits,
            plan_options=[],
            summary_en="Your file shows no outstanding balance. Nothing to reschedule.",
            summary_ar="ملفك لا يحتوي على رصيد قائم. لا حاجة لإعادة الجدولة.",
        )

    plans = [_plan_for(h, case.outstanding_balance_aed, case.monthly_income_aed, MAX_DTI) for h in horizons]
    affordable = [p for p in plans if p.affordable]

    # Pick the SHORTEST affordable plan (less interest exposure for the citizen)
    best = affordable[0] if affordable else None

    # ---- Recommendation ----
    if case.employment_status == "unemployed" and case.monthly_income_aed < MIN_INCOME_AED:
        recommendation: Recommendation = "manual_review"
        hits.append(RuleHit("SZHP-R6.1", "Unemployed + sub-floor income — social-support pathway needed", -0.5))
    elif best is None:
        # Even 36 months can't bring DTI under the ceiling.
        recommendation = "manual_review"
        worst_dti = max(p.dti for p in plans)
        hits.append(RuleHit(
            "SZHP-R6.2",
            f"Even {horizons[-1]}-month plan keeps DTI at {worst_dti:.0%} (>{MAX_DTI:.0%} ceiling) — manual review",
            -0.4,
        ))
    elif best.months == horizons[0] and case.employment_status == "employed":
        recommendation = "approve"
    else:
        recommendation = "approve_with_conditions"

    score = sum(h.weight for h in hits)
    confidence = max(0.1, min(0.99, 0.5 + score / 2))

    plan_months = best.months if best else None
    new_installment = best.monthly_aed if best else None

    summary_en = _summary_en(case, recommendation, plan_months, new_installment, plans)
    summary_ar = _summary_ar(case, recommendation, plan_months, new_installment, plans)

    return SzhpDecision(
        recommendation=recommendation,
        confidence=confidence,
        proposed_plan_months=plan_months,
        new_monthly_installment_aed=new_installment,
        rule_hits=hits,
        plan_options=plans,
        summary_en=summary_en,
        summary_ar=summary_ar,
    )


def _options_table_en(plans: list[PlanOption]) -> str:
    lines = ["", "Available plan options:"]
    for p in plans:
        marker = "✓" if p.affordable else "✗"
        lines.append(
            f"  {marker} {p.months} months @ AED {p.monthly_aed:,.0f}/month "
            f"(DTI {p.dti:.0%}{' — over ceiling' if not p.affordable else ''})"
        )
    return "\n".join(lines)


def _options_table_ar(plans: list[PlanOption]) -> str:
    lines = ["", "خيارات الجدولة المتاحة:"]
    for p in plans:
        marker = "✓" if p.affordable else "✗"
        lines.append(
            f"  {marker} {p.months} شهر بقسط {p.monthly_aed:,.0f} درهم/شهر "
            f"(نسبة الدين إلى الدخل {p.dti:.0%}{' — تتجاوز الحد' if not p.affordable else ''})"
        )
    return "\n".join(lines)


def _summary_en(c: SzhpCase, rec: Recommendation, plan: int | None, inst: float | None, plans: list[PlanOption]) -> str:
    if rec == "approve":
        return (
            f"Good news — you qualify for rescheduling over **{plan} months** at approximately "
            f"**AED {inst:,.0f} per month**. This keeps your debt-to-income ratio comfortably within "
            f"the {MAX_DTI:.0%} programme ceiling. I'll prepare a formal offer letter for your e-signature."
            f"{_options_table_en(plans)}"
        )
    if rec == "approve_with_conditions":
        return (
            f"You qualify for a conditional rescheduling over **{plan} months** at approximately "
            f"**AED {inst:,.0f} per month** (under the {MAX_DTI:.0%} DTI ceiling). "
            f"Final approval is subject to updated salary documentation."
            f"{_options_table_en(plans)}"
        )
    if rec == "manual_review":
        return (
            "Your case needs a manual review by a Customer Happiness officer — based on your numbers, "
            f"no standard plan keeps payments under the {MAX_DTI:.0%} DTI ceiling. "
            "I've opened a case file; an officer will reach out within 3 working days, "
            "or you can also visit the nearest service centre."
            f"{_options_table_en(plans)}"
        )
    return "Your application has been declined under the current programme rules."


def _summary_ar(c: SzhpCase, rec: Recommendation, plan: int | None, inst: float | None, plans: list[PlanOption]) -> str:
    if rec == "approve":
        return (
            f"أخبار جيدة — أنت مؤهل لإعادة الجدولة على مدى **{plan} شهر** بقسط شهري حوالي "
            f"**{inst:,.0f} درهم**. هذا يبقي نسبة الدين إلى الدخل ضمن سقف البرنامج البالغ {MAX_DTI:.0%}. "
            f"سأعد خطاب عرض رسمي لتوقيعك الإلكتروني."
            f"{_options_table_ar(plans)}"
        )
    if rec == "approve_with_conditions":
        return (
            f"أنت مؤهل لإعادة جدولة مشروطة على مدى **{plan} شهر** بقسط شهري حوالي "
            f"**{inst:,.0f} درهم** (تحت سقف نسبة الدين إلى الدخل {MAX_DTI:.0%}). "
            f"الموافقة النهائية تتطلب تحديث وثائق الراتب."
            f"{_options_table_ar(plans)}"
        )
    if rec == "manual_review":
        return (
            "قضيتك تتطلب مراجعة يدوية من قبل موظف سعادة المتعاملين — بناءً على أرقامك، "
            f"لا توجد خطة قياسية تبقي القسط تحت سقف نسبة الدين إلى الدخل {MAX_DTI:.0%}. "
            "تم فتح ملف قضية؛ سيتواصل معك موظف خلال 3 أيام عمل، أو يمكنك زيارة أقرب مركز خدمة."
            f"{_options_table_ar(plans)}"
        )
    return "تم رفض طلبك وفقًا لقواعد البرنامج الحالية."
