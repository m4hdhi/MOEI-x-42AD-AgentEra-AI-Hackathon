"""LLM-backed service automation planner.

The frontend should not decide which MOEI workflow a citizen needs. This route is the
Automation Agent: it reads the service catalog, asks the configured LLM for a structured
plan, and then executes only safe server-side actions:

- open_workflow: return an app route for workflows we actually built
- create_case: open/update a CRM case for supported service requests or complaints
- ask_clarifying_question: ask for missing information

It never claims a legal service was submitted until the user confirms the real form.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Request
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from hassan.knowledge import all_services, search_services
from hassan.llm.client import LLMRole, get_llm_with_fallback
from hassan.workers.crm import upsert_case

from ..core.language import detect_language
from .auth import get_authenticated_user_id, get_authenticated_user_name

router = APIRouter(prefix="/automation", tags=["automation"])

Intent = Literal[
    "service_request",
    "status_check",
    "complaint",
    "suggestion",
    "document_upload",
    "inquiry",
    "out_of_scope",
]
Action = Literal["open_workflow", "create_case", "ask_clarifying_question", "answer"]

_WORKFLOWS = {
    "szhp-reschedule": {
        "route": "/rescheduling",
        "name": "Loan Arrears Rescheduling",
        "can_prefill": True,
    },
}


class AutomationField(BaseModel):
    key: str
    label: str
    type: Literal["text", "textarea", "tel", "email", "number"] = "text"
    required: bool = True
    placeholder: str = ""


_SERVICE_FIELDS: dict[str, list[AutomationField]] = {
    "renewal-of-pleasure-boat-registration": [
        AutomationField(key="registration_number", label="Boat registration number", placeholder="e.g. DXB-12345"),
        AutomationField(key="boat_name", label="Boat name", required=False, placeholder="If available"),
        AutomationField(key="owner_mobile", label="Owner mobile number", type="tel", placeholder="+971..."),
        AutomationField(key="emirate", label="Emirate", placeholder="Dubai, Abu Dhabi, Sharjah..."),
        AutomationField(key="notes", label="Anything the officer should know?", type="textarea", required=False),
    ],
    "issuing-a-national-transportation-vehicle-permit": [
        AutomationField(key="company_name", label="Company name", placeholder="Trade license name"),
        AutomationField(key="trade_license_number", label="Trade license number", placeholder="License number"),
        AutomationField(key="vehicle_plate_number", label="Vehicle plate number", placeholder="Plate number"),
        AutomationField(key="emirate", label="Emirate", placeholder="Issuing emirate"),
        AutomationField(key="contact_mobile", label="Contact mobile number", type="tel", placeholder="+971..."),
    ],
    "housing-assistance-request": [
        AutomationField(key="family_members", label="Number of family members", type="number"),
        AutomationField(key="current_housing_status", label="Current housing status", type="textarea"),
        AutomationField(key="monthly_income", label="Monthly income", type="number", placeholder="AED"),
        AutomationField(key="request_details", label="What support do you need?", type="textarea"),
    ],
}


def _required_fields(service_id: str, intent: str) -> list[AutomationField]:
    if service_id in _SERVICE_FIELDS:
        return _SERVICE_FIELDS[service_id]
    if intent == "complaint":
        return [
            AutomationField(key="complaint_summary", label="Complaint summary", type="textarea"),
            AutomationField(key="related_reference", label="Related application or case number", required=False),
            AutomationField(key="preferred_contact", label="Preferred contact number", type="tel", placeholder="+971..."),
        ]
    return [
        AutomationField(key="request_details", label="Request details", type="textarea"),
        AutomationField(key="preferred_contact", label="Preferred contact number", type="tel", placeholder="+971..."),
    ]


def _missing_required_details(fields: list[AutomationField], details: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        if field.required and not str(details.get(field.key, "")).strip():
            missing.append(field.label)
    return missing


def _details_block(details: dict[str, Any]) -> str:
    clean = {k: v for k, v in details.items() if str(v).strip()}
    if not clean:
        return ""
    return "\n\nCustomer-provided details:\n" + "\n".join(f"- {k}: {v}" for k, v in clean.items())


class AutomationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1500)
    channel: Literal["web", "voice", "mobile", "sign"] = "web"
    session_id: str | None = None
    language: Literal["ar", "en", "auto"] = "auto"
    execute: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class AutomationDecision(BaseModel):
    language: Literal["ar", "en"] = "en"
    intent: Intent = "service_request"
    service_id: str = Field(default="unknown", description="Best matching catalog service id, or unknown.")
    service: str = Field(default="unknown", description="MOEI domain such as housing, maritime, transport.")
    title: str = Field(default="Service request", max_length=120)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    action: Action = "ask_clarifying_question"
    reason: str = Field(default="", max_length=300)
    reply: str = Field(default="", max_length=900)
    missing_information: list[str] = Field(default_factory=list, max_length=6)
    steps: list[str] = Field(default_factory=list, max_length=6)


class AutomationResponse(AutomationDecision):
    ok: bool = True
    executable: bool = False
    route: str | None = None
    external_url: str | None = None
    case_number: str | None = None
    required_documents: list[str] = Field(default_factory=list)
    required_fields: list[AutomationField] = Field(default_factory=list)
    workflow_name: str | None = None


def _catalog_block(text: str) -> str:
    hits = search_services(text, limit=8)
    if len(hits) < 4:
        seen = {s["id"] for s in hits}
        hits.extend([s for s in all_services() if s.get("id") not in seen][: 8 - len(hits)])
    rows = []
    for s in hits[:8]:
        rows.append({
            "id": s.get("id"),
            "domain": s.get("service"),
            "title": s.get("title"),
            "title_ar": s.get("title_ar", ""),
            "audience": s.get("audience", ""),
            "summary": (s.get("summary") or "")[:280],
            "required_documents": s.get("required_documents", []),
            "url": s.get("url"),
        })
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _fallback_decision(text: str, language: str) -> AutomationDecision:
    hits = search_services(text, limit=1)
    service = hits[0] if hits else None
    if not service:
        return AutomationDecision(
            language="ar" if language == "ar" else "en",
            intent="service_request",
            service_id="unknown",
            service="unknown",
            title="Need more information",
            confidence=0.35,
            action="ask_clarifying_question",
            reply="Please tell me which MOEI service you want to automate.",
            missing_information=["service name"],
        )

    sid = service.get("id", "unknown")
    action: Action = "open_workflow" if sid in _WORKFLOWS else "create_case"
    return AutomationDecision(
        language="ar" if language == "ar" else "en",
        intent="service_request",
        service_id=sid,
        service=service.get("service", "unknown"),
        title=service.get("title", "Service request")[:120],
        confidence=0.7,
        action=action,
        reason="Fallback catalog search selected the closest matching service.",
        reply=(
            "I found the closest MOEI service. I can open the workflow if available, "
            "or create a service case for follow-up."
        ),
        steps=["Identify service", "Prepare request", "Ask user to confirm required details"],
    )


async def _llm_decision(text: str, language: str) -> AutomationDecision:
    catalog = _catalog_block(text)
    implemented = json.dumps(_WORKFLOWS, ensure_ascii=False)
    system = f"""You are Agent42's Service Automation Agent for UAE MOEI.

You understand all available MOEI catalog services and decide what automation should happen.

Available tools:
1. open_workflow: use ONLY when the requested catalog service has an implemented workflow in IMPLEMENTED_WORKFLOWS.
2. create_case: use for complaints, suggestions, or service requests where no implemented workflow exists yet.
3. ask_clarifying_question: use when the request is ambiguous or missing the target service.
4. answer: use when the user is only asking information, not asking the agent to do a task.

Rules:
- Never claim the final government request was submitted unless a real workflow confirms it.
- For forms with declarations, uploads, signatures, or legal confirmation, the user must do the final confirmation.
- Prefer Arabic replies for Arabic user text.
- Choose the most specific catalog service id.
- If the user asks to automate/apply/request/renew/register/submit/file something, prefer open_workflow or create_case.

IMPLEMENTED_WORKFLOWS:
{implemented}

CATALOG_CANDIDATES:
{catalog}
"""
    human = f"Language hint: {language}\nCitizen request: {text}"
    llm = get_llm_with_fallback(LLMRole.REASONER, temperature=0.0)
    structured = llm.with_structured_output(AutomationDecision)
    return await structured.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])


@router.post("/plan", response_model=AutomationResponse)
async def plan(req: AutomationRequest, request: Request) -> AutomationResponse:
    """Return and optionally execute an automation plan for a citizen task request."""
    text = req.text.strip()
    language = detect_language(text) if req.language == "auto" else req.language
    try:
        decision = await _llm_decision(text, language)
    except Exception as e:
        logger.warning(f"automation_agent_llm_failed: {type(e).__name__}: {e}")
        decision = _fallback_decision(text, language)

    service = next((s for s in all_services() if s.get("id") == decision.service_id), None)
    workflow = _WORKFLOWS.get(decision.service_id)

    # Guardrail: the LLM may understand the service but it must not invent tools/pages.
    # If we have not implemented a workflow route, downgrade execution to a tracked case.
    if decision.action == "open_workflow" and not workflow:
        if decision.intent in ("service_request", "complaint", "suggestion", "document_upload"):
            decision.action = "create_case"
            decision.reason = "No implemented workflow route exists yet, so the agent will create a tracked case instead."
            decision.reply = (
                f"I found the right service: {decision.title}. I can create a tracked case for this request "
                "and link you to the official service page."
            )
        else:
            decision.action = "answer"

    route = None
    if decision.action == "open_workflow" and workflow:
        from urllib.parse import urlencode

        qs = urlencode({
            "from": "automation",
            "mode": req.channel,
            "intent": decision.service_id,
            "utterance": text,
        })
        route = f"{workflow['route']}?{qs}"

    case_number = None
    required_fields = _required_fields(decision.service_id, decision.intent) if decision.action == "create_case" else []
    if req.execute and decision.action == "create_case" and decision.confidence >= 0.6:
        missing = _missing_required_details(required_fields, req.details)
        if missing:
            decision.action = "ask_clarifying_question"
            decision.missing_information = missing
            decision.reply = (
                "I found the right service. Please provide the missing details so I can prepare "
                "the request: " + ", ".join(missing)
            )
        else:
            user_id = get_authenticated_user_id(request) or "anonymous"
            user_name = get_authenticated_user_name(request)
            case = upsert_case(
                user_id=user_id,
                user_name=user_name,
                channel=req.channel,
                intent=decision.intent if decision.intent != "inquiry" else "service_request",
                service=decision.service if decision.service != "unknown" else "general",
                user_text=text + _details_block(req.details),
                sentiment=None,
                escalated=decision.intent == "complaint",
                correlation_id=getattr(request.state, "correlation_id", None),
                escalation_reason=decision.reason if decision.intent == "complaint" else None,
            )
            if case:
                case_number = case.get("case_number")
                decision.reply = (
                    f"I prepared the request and created a tracked case: {case_number}. "
                    "Use the official service page to complete any final government submission, signature, or payment."
                )

    reply = decision.reply
    if not reply:
        if route:
            reply = "I found the right workflow and can open it now."
        elif case_number:
            reply = f"I created a service case for follow-up: {case_number}."
        else:
            reply = "I found the likely service. Please confirm the missing details so I can continue."

    return AutomationResponse(
        **decision.model_dump(exclude={"reply"}),
        reply=reply,
        executable=bool(route or case_number),
        route=route,
        external_url=service.get("url") if service else None,
        case_number=case_number,
        required_documents=service.get("required_documents", []) if service else [],
        required_fields=required_fields,
        workflow_name=workflow.get("name") if workflow else None,
    )
