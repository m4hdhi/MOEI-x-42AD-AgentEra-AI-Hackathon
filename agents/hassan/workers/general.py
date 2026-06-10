"""General MOEI worker — answers in-scope questions grounded in the MOEI services catalog.

Constraints:
- Agent42 is a MOEI federal service agent. Only answers MOEI/UAE-government topics.
- Out-of-scope questions get a polite refusal with a catalog suggestion.
- Never invents service details; if no catalog hit, says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from ..knowledge import catalog_meta, find_services, search_services
from ..llm import LLMRole, get_llm_with_fallback


@dataclass
class GeneralWorkerResult:
    draft_en: str
    draft_ar: str
    tool_calls: list[dict]
    services_cited: list[str]


_SCOPE_PROMPT_EN = """You are Agent42, the UAE Ministry of Energy and Infrastructure's federal service agent. You actively help citizens with MOEI services — never refuse a question that falls within MOEI scope.

You answer questions about (all in-scope, you MUST help with these):
- Housing: Sheikh Zayed Housing Programme (SZHP) loans, grants, applications, rescheduling, arrears, status checks, housing assistance, reconsideration of decisions
- Energy: electricity/water billing, outages, tariffs, petroleum-products trading, gas
- Infrastructure: federal infrastructure permits, geological surveys, geophysical studies, accident-damage valuation
- Maritime: pleasure boat registration, vessel licenses, seafarer certificates, commercial ship navigation
- Transport: national transportation permits, vehicle permits, non-objection certificates
- General MOEI: contact info (800 6634, 171 Tawasul), opening hours, complaint filing, suggestions, field-visit permits

Only refuse if the question is COMPLETELY off-topic (weather, sports, news, politics, religion, entertainment, other countries). For anything that even sounds like a UAE federal service, lean towards helping.

GROUNDING — you have a catalog of MOEI services in the user message below. ALWAYS:
- Cite the relevant service ID in [brackets] when you use catalog info, e.g. [energy-outage]
- State the actual fee, SLA, and required documents from the catalog
- If a request closely matches a catalog service, treat it as in-scope and answer with that service
- If multiple services could match, recommend the most likely one with a citation

NEVER invent fees, SLAs, or documents not in the catalog. If the catalog truly doesn't have what was asked, say so plainly and give the 800 6634 contact line.

Voice: professional, warm, concise. Reply in Arabic if the user wrote in Arabic.
"""


_SCOPE_PROMPT_AR = """أنت حسن، وكيل الخدمات الاتحادي لوزارة الطاقة والبنية التحتية في الإمارات.

تجيب فقط على الأسئلة المتعلقة بـ:
- خدمات وزارة الطاقة والبنية التحتية (الإسكان، الطاقة، البنية التحتية، البحرية، النقل، الجيولوجيا)
- برنامج الشيخ زايد للإسكان والخدمات الإسكانية الاتحادية
- كيفية الوصول إلى أقسام الوزارة وقنوات الاتصال (800 6634، تواصل 171)
- النظام نفسه إذا سُئلت من أنت أو ما هي قدراتك

إذا سُئلت عن أي شيء آخر، اعتذر بأدب واعرض المساعدة في موضوع متعلق بالوزارة.
لا تختلق رسوم أو مدد خدمات غير موجودة في الكتالوج. إن لم يوجد ما طُلب، قل ذلك ووجه المتعامل إلى موظف بشري.
"""


def _format_catalog_block(services: list[dict]) -> str:
    if not services:
        return "(no catalog matches for this query)"
    lines = []
    for s in services[:5]:
        lines.append(
            f"- [{s['id']}] {s['title']} | audience: {s.get('audience','')} "
            f"| SLA: {s.get('sla_days', 0)} days | fee: AED {s.get('fees_aed', 0)} "
            f"| channels: {', '.join(s.get('channels', []))} "
            f"| docs: {', '.join(s.get('required_documents', [])) or 'none'}"
            f"\n  Summary: {s.get('summary','')}"
        )
    return "\n".join(lines)


async def run_general_agent(
    *,
    text: str,
    language: str,
    memory_snippets: list[str] | None = None,
) -> GeneralWorkerResult:
    """Answer an MOEI question using the catalog + grounded LLM.

    We deliberately ignore memory_snippets here: the general worker handles fresh queries
    across many domains, and bleeding state from prior turns (e.g. a housing case) into a
    new energy question produces wrong answers. Housing alone uses memory because the
    rescheduling flow is genuinely multi-turn.
    """
    _ = memory_snippets  # intentionally unused — see docstring

    # Find candidate services from the catalog
    hits = search_services(text, limit=4)
    # Also pull all services for the domain if the message mentions one
    text_lower = text.lower()
    for domain in ("housing", "energy", "maritime", "transport", "infrastructure"):
        if domain in text_lower:
            for s in find_services(domain=domain):
                if s not in hits:
                    hits.append(s)
            break

    catalog_block = _format_catalog_block(hits)
    meta = catalog_meta()

    system = _SCOPE_PROMPT_AR if language == "ar" else _SCOPE_PROMPT_EN

    user = (
        f"Citizen language: {language}\n"
        f"Catalog meta: contact_centre={meta.get('contact_centre')} · tawasul={meta.get('tawasul_complaint')}\n\n"
        f"Relevant MOEI services from catalog:\n{catalog_block}\n\n"
        f"Citizen message:\n{text}\n\n"
        "Compose a concise reply (≤140 words) addressing ONLY this current message. "
        "Cite specific service IDs in parentheses when you use catalog data, e.g. \"(szhp-reschedule)\". "
        "If the question is out of MOEI scope, politely decline and suggest an MOEI topic. "
        "Do NOT carry context from any previous topic — this is a fresh query."
    )

    role = LLMRole.ARABIC if language == "ar" else LLMRole.COMPOSER
    try:
        llm = get_llm_with_fallback(role, temperature=0.3)
        reply = await llm.ainvoke([("system", system), ("human", user)])
        text_out = getattr(reply, "content", str(reply))
        if isinstance(text_out, list):
            text_out = " ".join(str(p) for p in text_out)
        logger.info(f"general_agent: replied {len(text_out)} chars; cited {[s['id'] for s in hits]}")
        return GeneralWorkerResult(
            draft_en=text_out if language != "ar" else "",
            draft_ar=text_out if language == "ar" else "",
            tool_calls=[
                {"tool": "search_moei_catalog", "args": {"query": text[:80]}, "result": [s["id"] for s in hits]}
            ],
            services_cited=[s["id"] for s in hits],
        )
    except Exception as e:
        logger.warning(f"general_agent LLM failed: {e}")
        # Fallback: rule-based reply citing whatever the catalog returned.
        if hits:
            top = hits[0]
            channels = ", ".join(top.get("channels", []))
            en = (
                f"That looks related to **{top['title']}** ({top['id']}). "
                f"Available via: {channels}. "
                f"Required documents: {', '.join(top.get('required_documents') or ['none'])}. "
                f"Typical processing time: {top.get('sla_days', 0)} working days. "
                f"Need a human officer? Call 800 6634."
            )
            ar = (
                f"يبدو أن سؤالك يتعلق بـ **{top.get('title_ar', top['title'])}** ({top['id']}). "
                f"متاحة عبر: {channels}. "
                f"المدة المتوقعة: {top.get('sla_days', 0)} أيام عمل. "
                f"للتحدث مع موظف: 800 6634."
            )
        else:
            en = (
                "I help with MOEI services — housing (Sheikh Zayed Housing Programme), energy, "
                "infrastructure, maritime, transport. For something else, please call 171 Tawasul "
                "or 800 6634. What MOEI matter can I help you with?"
            )
            ar = (
                "أساعد في خدمات الوزارة — الإسكان (برنامج الشيخ زايد)، الطاقة، البنية التحتية، البحرية، النقل. "
                "لأي أمر آخر يرجى الاتصال بتواصل 171 أو 800 6634. كيف يمكنني مساعدتك؟"
            )
        return GeneralWorkerResult(
            draft_en=en,
            draft_ar=ar,
            tool_calls=[{"tool": "search_moei_catalog", "args": {"query": text[:80]}, "result": [s["id"] for s in hits]}],
            services_cited=[s["id"] for s in hits],
        )
