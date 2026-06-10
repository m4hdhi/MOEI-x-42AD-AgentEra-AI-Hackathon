"""Tests for the dataset-grounded escalation logic (FAQ Q12/Q13).

Exercises the two layers of `escalation_node`: the immediate triggers and the >= 2-signal
fusion rule. No database is required — with no `user_id` the node uses only the live-turn
signals (emotion + sentiment), which is exactly the path these tests drive.
"""

from hassan.supervisor.nodes import escalation_node


def _state(**overrides):
    base = dict(intent="service_request", confidence=0.9, critic_score=1.0, urgency="low")
    base.update(overrides)
    return base


def test_explicit_request_escalates():
    out = escalation_node(_state(intent="escalate_to_human"))
    assert out["escalated"] is True
    assert out["escalation_signals"] == ["explicit_request"]


def test_high_urgency_escalates():
    out = escalation_node(_state(urgency="high", emotion="anxious"))
    assert out["escalated"] is True


def test_critic_flagged_escalates():
    out = escalation_node(_state(critic_score=0.5, critic_notes="ungrounded claim"))
    assert out["escalated"] is True
    assert out["escalation_signals"] == ["critic_flagged"]


def test_single_negative_signal_does_not_escalate():
    # A lone very-negative sentiment is not enough (FAQ Q13 best practice).
    out = escalation_node(_state(sentiment=0.1))
    assert out["escalated"] is False
    assert out["escalation_signals"] == ["very_negative_sentiment"]


def test_two_live_signals_escalate():
    # Anger + very-negative sentiment = two signals fired -> handoff.
    out = escalation_node(_state(emotion="angry", sentiment=0.05))
    assert out["escalated"] is True
    assert set(out["escalation_signals"]) == {"anger_flag", "very_negative_sentiment"}


def test_neutral_turn_stays_self_service():
    out = escalation_node(_state(emotion="neutral", sentiment=0.7))
    assert out["escalated"] is False
    assert out["escalation_signals"] == []
