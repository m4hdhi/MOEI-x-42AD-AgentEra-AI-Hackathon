from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Channel = Literal["web", "voice", "whatsapp", "mobile"]
Language = Literal["ar", "en", "auto"]


class IncomingMessage(BaseModel):
    """Normalized payload that every channel adapter produces."""

    user_id: str = Field(..., description="UAE PASS correlation id (synthetic for demo)")
    channel: Channel
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    correlation_id: str = Field(default_factory=lambda: uuid4().hex)
    language: Language = "auto"
    text: str
    received_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    text: str
    language: Language
    service: str = "unknown"
    intent: str = "service_request"
    confidence: float = 0.0
    sentiment: float | None = None
    escalated: bool = False
    next_best_action: str | None = None
    trace_url: str | None = None
    suggested_replies: list[str] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    case_number: str | None = None
    escalation_risk: dict = Field(default_factory=dict)
    emotion: str | None = None
    urgency: str | None = None
    life_events: list[str] = Field(default_factory=list)
    autonomous: bool = False
    correlation_id: str
