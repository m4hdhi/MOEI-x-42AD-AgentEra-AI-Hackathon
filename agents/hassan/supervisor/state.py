from typing import Annotated, Literal, TypedDict
from operator import add

Channel = Literal["web", "voice", "whatsapp", "mobile"]
Language = Literal["ar", "en", "auto"]
Service = Literal["housing", "energy", "infrastructure", "maritime", "transport", "unknown"]


class SupervisorState(TypedDict, total=False):
    # Ingress
    user_id: str
    channel: Channel
    session_id: str
    language: Language
    text: str

    # Router
    intent: str
    service: Service
    confidence: float

    # Memory + RAG
    memory_snippets: list[str]
    rag_snippets: list[str]

    # Knowledge-base retrieval (curated facts + crawled moei.gov.ae pages)
    knowledge_hits: list[dict]
    citations: list[dict]

    # Guardrails
    pii_redacted: bool
    policy_blocked: bool
    block_reason: str | None

    # Worker output
    worker_draft: str
    tool_calls: Annotated[list[dict], add]
    housing_decision: dict | None
    handled_by: str                 # which specialist agent answered (multi-agent ecosystem)

    # Critic
    critic_score: float
    critic_notes: str

    # Escalation
    escalated: bool
    escalation_reason: str | None
    escalation_signals: list[str]   # dataset-grounded triggers that fired (FAQ Q12/Q13)

    # Final
    reply: str
    trace_url: str | None
    suggested_replies: list[str]
    case_number: str | None

    # Cross-cutting metadata used by persist/CRM
    user_name: str
    sentiment: float                # 0..1 (0=very negative, 1=very positive)
    emotion: str                    # angry | anxious | frustrated | satisfied | neutral
    urgency: str                    # low | medium | high
    life_events: list[str]          # detected life events → proactive service recs
    autonomous: bool                # case fully resolved by the agent, no human needed
    self_served: bool               # citizen got a direct FAQ/knowledge answer → auto-close case
    correlation_id: str
    next_best_action: str           # one-line action hint for the human co-pilot
    escalation_risk: dict           # ML-predicted complaint/escalation risk {risk, band, factors}
