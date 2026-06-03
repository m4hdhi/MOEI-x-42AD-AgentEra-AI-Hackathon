"""Escalation / complaint-risk predictor (inference).

Loads the scikit-learn model trained by scripts/train_escalation_model.py and returns a
risk probability + the top contributing factors. Powers the live "escalation risk" gauge on
the co-pilot and Predictive Complaint Prevention. Falls back to a transparent heuristic if
the model file is missing, so the platform never hard-fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "escalation_clf.joblib"
_MODEL: Any = None
_LOADED = False


def _load():
    global _MODEL, _LOADED
    if _LOADED:
        return _MODEL
    _LOADED = True
    try:
        import joblib
        _MODEL = joblib.load(_MODEL_PATH)
        logger.info(f"escalation_model: loaded {_MODEL_PATH.name}")
    except Exception as e:
        logger.warning(f"escalation_model: model not available ({e}); using heuristic")
        _MODEL = None
    return _MODEL


def _featurize(intent: str, service: str, channel: str, sentiment: float, msg_len: int) -> dict:
    return {
        "intent": intent or "unknown",
        "service": service or "unknown",
        "channel": channel or "web",
        "sentiment": float(sentiment if sentiment is not None else 0.5),
        "low_sentiment": 1.0 if (sentiment is not None and sentiment < 0.4) else 0.0,
        "msg_len": float(min(msg_len or 0, 2000)),
    }


def _heuristic(intent: str, sentiment: float) -> float:
    risk = 0.15
    if intent == "complaint":
        risk += 0.45
    if sentiment is not None and sentiment < 0.4:
        risk += 0.3
    elif sentiment is not None and sentiment < 0.55:
        risk += 0.1
    return max(0.0, min(1.0, risk))


def predict_escalation(
    *, intent: str, service: str, channel: str, sentiment: float | None, msg_len: int = 0
) -> dict:
    """Return {risk: 0..1, band: low|medium|high, factors: [..], model: name}."""
    s = 0.5 if sentiment is None else float(sentiment)
    model = _load()
    if model is None:
        risk = _heuristic(intent, s)
        source = "heuristic"
    else:
        try:
            feats = _featurize(intent, service, channel, s, msg_len)
            risk = float(model["pipeline"].predict_proba([feats])[0][1])
            source = "ml:logreg"
        except Exception as e:
            logger.warning(f"escalation_model: predict failed ({e}); heuristic")
            risk = _heuristic(intent, s)
            source = "heuristic"

    factors = []
    if intent == "complaint":
        factors.append("Complaint intent")
    if s < 0.4:
        factors.append("Negative sentiment")
    elif s < 0.55:
        factors.append("Lukewarm sentiment")
    if channel == "voice":
        factors.append("Voice channel")
    if not factors:
        factors.append("Routine request")

    band = "high" if risk >= 0.6 else "medium" if risk >= 0.35 else "low"
    return {"risk": round(risk, 3), "band": band, "factors": factors[:3], "model": source}
