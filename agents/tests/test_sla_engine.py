"""Tests for the 3-tier SLA engine (Feature A) and self-service auto-close (Feature B).

No live database is required: the SLA-deadline math and the priority/self-served logic are
pure functions, and `auto_resolve_case` is driven against a fake cursor that captures the SQL
it would have run.
"""

from datetime import UTC, datetime, timedelta

from hassan.supervisor.nodes import (
    assign_priority_tier,
    escalation_node,
    fast_compose_node,
)
from hassan.workers import crm
from hassan.workers.crm import sla_deadline_for


def _state(**overrides):
    base = dict(intent="service_request", confidence=0.9, critic_score=1.0, urgency="low")
    base.update(overrides)
    return base


# --- Feature A: 3-tier SLA -----------------------------------------------------

def test_urgent_case_gets_one_day_deadline():
    # An angry, very-negative turn is an urgent tier...
    assert assign_priority_tier(_state(emotion="angry", sentiment=0.05)) == "urgent"

    # ...and an urgent tier's SLA deadline is exactly 1 day out.
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    assert sla_deadline_for("urgent", now=now) == now + timedelta(days=1)


def test_medium_tier_for_reopened_or_breached():
    assert assign_priority_tier(_state(reopen_count=2)) == "medium"
    assert assign_priority_tier(_state(sla_breached=True)) == "medium"
    now = datetime(2026, 6, 10, tzinfo=UTC)
    assert sla_deadline_for("medium", now=now) == now + timedelta(days=3)


def test_normal_tier_default_five_day_deadline():
    assert assign_priority_tier(_state(emotion="neutral", sentiment=0.7)) == "normal"
    now = datetime(2026, 6, 10, tzinfo=UTC)
    assert sla_deadline_for("normal", now=now) == now + timedelta(days=5)
    # Unknown tiers fall back to the normal (5-day) window.
    assert sla_deadline_for("bogus", now=now) == now + timedelta(days=5)


def test_critical_priority_is_urgent():
    assert assign_priority_tier(_state(priority="Critical")) == "urgent"
    # Also via the escalation_signals the escalation node emits.
    assert assign_priority_tier(_state(escalation_signals=["critical_priority"])) == "urgent"


# --- Feature B: self-service auto-close ----------------------------------------

async def test_self_served_inquiry_resolves_without_escalation(monkeypatch):
    # A simple inquiry answered from a grounded knowledge hit, no anger/escalation signals.
    # (Only informational intents self-close — a service_request implies work to be actioned,
    # so it keeps its case open; see fast_compose_node.)
    state = _state(
        intent="inquiry",
        channel="whatsapp",
        worker_draft="The boat registration fee is AED 500.",
        knowledge_hits=[{"title": "Maritime fees", "url": "https://moei.gov.ae/fees",
                         "snippet": "Boat registration fee is AED 500."}],
        emotion="neutral",
        sentiment=0.7,
    )

    composed = await fast_compose_node(state)
    assert composed["self_served"] is True

    # The same turn must NOT escalate.
    state.update(composed)
    assert escalation_node(state)["escalated"] is False

    # auto_resolve_case writes status=resolved + resolution_type=self_served, never escalates.
    captured = {}

    class _FakeCursor:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

    class _FakeCtx:
        def __enter__(self):
            return _FakeCursor()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(crm, "_DB_AVAILABLE", True)
    monkeypatch.setattr(crm, "db_cursor", lambda: _FakeCtx())

    crm.auto_resolve_case("MOEI-CASE-20260610-0001")

    sql = captured["sql"]
    assert "status='resolved'" in sql
    assert "resolution_type='self_served'" in sql
    assert "resolved_at=NOW()" in sql
    # It resolves, it does not escalate; and it refuses to override an escalated case.
    assert "status='escalated'" not in sql
    assert "NOT IN ('resolved', 'escalated', 'closed')" in sql
    assert captured["params"] == ("MOEI-CASE-20260610-0001",)


async def test_complaint_is_not_self_served():
    state = _state(
        intent="complaint",
        channel="whatsapp",
        worker_draft="Sorry to hear that.",
        knowledge_hits=[{"title": "x", "url": "https://moei.gov.ae/x", "snippet": "y"}],
    )
    composed = await fast_compose_node(state)
    assert composed["self_served"] is False


async def test_ungrounded_answer_is_not_self_served():
    # No knowledge hits → no citations → not a self-service resolution.
    state = _state(intent="service_request", channel="whatsapp",
                   worker_draft="Let me help.", knowledge_hits=[])
    composed = await fast_compose_node(state)
    assert composed["self_served"] is False
