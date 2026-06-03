"""Structured-output schemas for supervisor nodes. Pydantic v2."""

from typing import Literal

from pydantic import BaseModel, Field

Service = Literal["housing", "energy", "infrastructure", "maritime", "transport", "unknown"]
Intent = Literal[
    "service_request",
    "status_check",
    "complaint",
    "suggestion",
    "appreciation",
    "document_upload",
    "escalate_to_human",
    "smalltalk",
    "out_of_scope",
]


class RouterDecision(BaseModel):
    """Output of the Router node — what the supervisor needs to dispatch."""

    intent: Intent = Field(description="What the citizen wants to do.")
    service: Service = Field(description="Which MOEI business line this belongs to.")
    language: Literal["ar", "en"] = Field(description="Detected user language.")
    confidence: float = Field(ge=0.0, le=1.0, description="Router's self-rated confidence.")
    reasoning: str = Field(
        description="One sentence on why this intent/service was chosen. Shown in audit UI.",
        max_length=240,
    )


class ComposerOutput(BaseModel):
    """Output of the Composer node — channel-aware final reply."""

    reply: str = Field(description="The text to send to the citizen.")
    suggested_replies: list[str] = Field(
        default_factory=list,
        description="2-3 quick-reply chips the citizen can tap. Same language as reply.",
        max_length=3,
    )


class CriticVerdict(BaseModel):
    """Output of the Reflection/Critic node."""

    score: float = Field(ge=0.0, le=1.0, description="Quality score of the draft.")
    accurate: bool
    culturally_appropriate: bool
    complete: bool
    issues: list[str] = Field(default_factory=list, max_length=5)
