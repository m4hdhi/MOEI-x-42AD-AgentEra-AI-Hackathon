"""LangGraph supervisor.

Graph shape (web / voice — full polish):
  router → memory → guardrails → dispatcher → critic → escalation → composer → persist

Graph shape (whatsapp — fast path, ~half the latency):
  router → memory → guardrails → dispatcher → escalation → fast_compose → persist

The WhatsApp shortcut skips the Critic and Composer LLM calls. Worker drafts are already
grounded in the rules engine / MOEI catalog so they're factually correct; we just strip
markdown and add channel-appropriate suggested replies.
"""

from __future__ import annotations

import asyncio
import os

from langgraph.graph import END, START, StateGraph

from ..observability import get_langfuse_callbacks
from .nodes import (
    composer_node,
    critic_node,
    dispatcher_node,
    escalation_node,
    fast_compose_node,
    memory_loader_node,
    next_best_action_node,
    persist_turn_node,
    policy_guardrails_node,
    router_node,
    sentiment_node,
)
from .state import SupervisorState


def _is_housing_payment_flow(state: SupervisorState) -> bool:
    """True only when the housing rules engine actually ran (housing_decision is set)
    or is in the middle of asking for info (worker_draft includes the follow-up question)."""
    if state.get("service") != "housing":
        return False
    # The dispatcher emits housing_decision only when run_housing_agent ran.
    # If service=housing but no decision (informational query), we already went to general worker.
    if state.get("housing_decision") is not None:
        return True
    return False


def _after_dispatcher(state: SupervisorState) -> str:
    """Critic runs on the housing-rescheduling flow on ALL channels (web + WhatsApp + voice).

    The Critic LLM catches bad rules-engine math. Skipped for catalog-grounded answers
    where there's nothing to invent (general/energy/maritime/transport).
    """
    if _is_housing_payment_flow(state):
        return "critic"
    return "escalation"


def _after_escalation(state: SupervisorState) -> str:
    """Use the full LLM Composer for the housing-rescheduling flow on ALL channels.

    For catalog answers (general/energy/maritime/transport) the worker already returns a
    polished, citation-grounded reply from OpenAI — Composer would just rewrite cosmetic tone.
    Both branches now behave identically across web and WhatsApp; WhatsApp's 15s webhook
    timeout is handled by the background-task path in routes/whatsapp.py.
    """
    if _is_housing_payment_flow(state):
        return "composer"
    return "fast_compose"


def build_graph():
    g = StateGraph(SupervisorState)
    g.add_node("router", router_node)
    g.add_node("sentiment", sentiment_node)
    g.add_node("memory_loader", memory_loader_node)
    g.add_node("policy_guardrails", policy_guardrails_node)
    g.add_node("dispatcher", dispatcher_node)
    g.add_node("critic", critic_node)
    g.add_node("escalation", escalation_node)
    g.add_node("composer", composer_node)
    g.add_node("fast_compose", fast_compose_node)
    g.add_node("next_best_action", next_best_action_node)
    g.add_node("persist_turn", persist_turn_node)

    g.add_edge(START, "router")
    g.add_edge("router", "sentiment")
    g.add_edge("sentiment", "memory_loader")
    g.add_edge("memory_loader", "policy_guardrails")
    g.add_edge("policy_guardrails", "dispatcher")
    g.add_conditional_edges("dispatcher", _after_dispatcher, {
        "critic": "critic",
        "escalation": "escalation",
    })
    g.add_edge("critic", "escalation")
    g.add_conditional_edges("escalation", _after_escalation, {
        "composer": "composer",
        "fast_compose": "fast_compose",
    })
    g.add_edge("composer", "next_best_action")
    g.add_edge("fast_compose", "next_best_action")
    g.add_edge("next_best_action", "persist_turn")
    g.add_edge("persist_turn", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


SUPERVISOR_TIMEOUT_SECONDS = float(os.getenv("HASSAN_SUPERVISOR_TIMEOUT", "60"))


async def run_supervisor(
    *,
    user_id: str,
    channel: str,
    session_id: str,
    language: str,
    text: str,
    user_name: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    graph = get_graph()
    initial: SupervisorState = {
        "user_id": user_id,
        "channel": channel,
        "session_id": session_id,
        "language": language,
        "text": text,
    }
    if user_name:
        initial["user_name"] = user_name
    if correlation_id:
        initial["correlation_id"] = correlation_id
    callbacks = get_langfuse_callbacks(
        session_id=session_id,
        user_id=user_id,
        metadata={"channel": channel, "agent": "hassan"},
    )

    # Hard timeout — never let a stuck LLM call freeze the user's chat forever.
    try:
        final = await asyncio.wait_for(
            graph.ainvoke(
                initial,
                config={"callbacks": callbacks, "run_name": f"hassan.{channel}"},
            ),
            timeout=SUPERVISOR_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        # Graceful timeout reply so the UI shows something useful instead of hanging.
        msg_en = (
            "I'm taking longer than usual to think this through. Please rephrase your "
            "question or call our Customer Happiness Centre on 800 6634 for immediate help."
        )
        msg_ar = (
            "أحتاج إلى وقت أطول من المعتاد للرد. يرجى إعادة صياغة سؤالك أو الاتصال بمركز "
            "سعادة المتعاملين على 800 6634 للمساعدة الفورية."
        )
        return {
            "reply": msg_ar if language == "ar" else msg_en,
            "language": language,
            "service": "unknown",
            "intent": "service_request",
            "confidence": 0.0,
            "escalated": True,
            "trace_url": None,
            "suggested_replies": [],
        }

    # Force-flush so short-lived requests don't lose spans.
    try:
        from hassan.observability import get_langfuse_client

        client = get_langfuse_client()
        if client is not None:
            client.flush()
    except Exception:
        pass
    return {
        "reply": final.get("reply", ""),
        "language": final.get("language", "en"),
        "service": final.get("service", "unknown"),
        "intent": final.get("intent", "service_request"),
        "confidence": final.get("confidence", 0.0),
        "escalated": final.get("escalated", False),
        "trace_url": final.get("trace_url"),
        "suggested_replies": final.get("suggested_replies", []),
        "citations": final.get("citations", []),
        "case_number": final.get("case_number"),
        "sentiment": final.get("sentiment"),
        "next_best_action": final.get("next_best_action"),
        "escalation_risk": final.get("escalation_risk") or {},
    }
