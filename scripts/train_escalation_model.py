"""Train the escalation / complaint-risk predictor.

A lightweight, genuine ML model (logistic regression) that predicts the probability a given
interaction will end up escalated to a human. Trained on the cases table using features
available at intake (sentiment, intent, service, channel, message length) and saved to
agents/hassan/models/escalation_clf.joblib.

The supervisor loads it (agents/hassan/workers/escalation_model.py) to show a live
"escalation risk" gauge on the co-pilot and to power Predictive Complaint Prevention.

Usage:
    uv run python scripts/train_escalation_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

_API = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from app.core.db import db_cursor  # type: ignore

MODEL_DIR = Path(__file__).resolve().parents[1] / "agents" / "hassan" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "escalation_clf.joblib"


def _featurize(intent: str, service: str, channel: str, sentiment: float, msg_len: int) -> dict:
    """Feature dict. DictVectorizer one-hot-encodes the string fields and keeps numerics."""
    return {
        "intent": intent or "unknown",
        "service": service or "unknown",
        "channel": channel or "web",
        "sentiment": float(sentiment if sentiment is not None else 0.5),
        "low_sentiment": 1.0 if (sentiment is not None and sentiment < 0.4) else 0.0,
        "msg_len": float(min(msg_len or 0, 2000)),
    }


def load_xy() -> tuple[list[dict], np.ndarray]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(intent,'unknown') AS intent,
                   COALESCE(service,'unknown') AS service,
                   COALESCE(channel,'web') AS channel,
                   COALESCE(sentiment,0.5) AS sentiment,
                   COALESCE(length(description),0) AS msg_len,
                   CASE WHEN status='escalated' THEN 1 ELSE 0 END AS escalated
            FROM cases
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    X = [_featurize(r["intent"], r["service"], r["channel"], float(r["sentiment"]), int(r["msg_len"])) for r in rows]
    y = np.array([r["escalated"] for r in rows])
    return X, y


def main() -> None:
    X, y = load_xy()
    if len(X) < 30:
        print(f"Not enough data ({len(X)} rows).", file=sys.stderr)
        sys.exit(1)
    pos = int(y.sum())
    print(f"Training on {len(X)} cases · {pos} escalated ({pos/len(X)*100:.0f}% positive)")

    model = Pipeline([
        ("vec", DictVectorizer(sparse=False)),
        ("lr", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    if pos >= 8 and (len(X) - pos) >= 8:
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
        model.fit(Xtr, ytr)
        try:
            auc = roc_auc_score(yte, model.predict_proba(Xte)[:, 1])
            print(f"Hold-out ROC-AUC: {auc:.3f}")
        except Exception as e:
            print(f"(AUC skipped: {e})")
    model.fit(X, y)  # final fit on all data

    joblib.dump({"pipeline": model, "featurize": "intent,service,channel,sentiment,low_sentiment,msg_len"}, MODEL_PATH)
    print(f"Saved model → {MODEL_PATH}")


if __name__ == "__main__":
    main()
