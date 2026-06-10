"""Sheikh Zayed Housing Programme — Loan Arrears Rescheduling (officer-grade AI agent).

The agent performs the role of a Programme officer end-to-end:
  retrieve loan + arrears  →  validate documents  →  analyse income/family/capacity  →
  apply policy rules (20% cap, period ≤ original, active-request reject)  →
  produce an explainable recommendation with confidence  →  refer only the hard cases.

Endpoints:
  GET  /szhp/loan                         retrieve the signed-in beneficiary's loan (auto retrieval)
  POST /szhp/assess                       run the assessment, persist + audit, return the decision
  GET  /szhp/queue                        officer review queue
  GET  /szhp/assessment/{reference}       full structured assessment
  POST /szhp/assessment/{reference}/action  officer approve / override / refer
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

from ..core.db import db_cursor
from .auth import get_authenticated_user_id, get_authenticated_user_name

# import the deterministic engine from the agents package
_AGENTS = Path(__file__).resolve().parents[3] / "agents"
if str(_AGENTS) not in sys.path:
    sys.path.insert(0, str(_AGENTS))
from hassan.tools.arrears_engine import ArrearsCase, assess_rescheduling  # type: ignore

router = APIRouter(prefix="/szhp", tags=["szhp-rescheduling"])


def _loan_for(user_id: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM szhp_loans WHERE user_id = %s ORDER BY id LIMIT 1", (user_id,))
        return cur.fetchone()


def _f(v) -> float:
    return float(v) if v is not None else 0.0


@router.get("/loan")
def get_loan(request: Request, user_id: str | None = None) -> dict:
    """Auto-retrieve the beneficiary's loan & arrears — no manual data entry."""
    uid = get_authenticated_user_id(request) or user_id
    if not uid:
        raise HTTPException(401, "sign in required")
    loan = _loan_for(uid)
    if not loan:
        return {"found": False, "user_id": uid}
    return {
        "found": True,
        "applicant": loan.get("applicant") or get_authenticated_user_name(request),
        "application_id": loan.get("application_id"),
        "customer_id": loan.get("edb_customer_id"),
        "current_salary": _f(loan.get("current_salary")),
        "arrears": _f(loan.get("over_due_amt")),
        "overdue_months": _f(loan.get("over_due_months")),
        "current_emi": _f(loan.get("current_emi_amt")),
        "original_term_months": loan.get("original_term_months"),
        "remaining_term_months": loan.get("remaining_term_months"),
        "family_size": loan.get("family_size"),
        "dependents": loan.get("dependents"),
        "has_active_request": bool(loan.get("has_active_request")),
    }


class AssessBody(BaseModel):
    user_id: str | None = None
    declaration_accepted: bool = False     # mandatory authenticity declaration
    salary_cert_provided: bool = True       # a certificate was uploaded
    declared_salary: float | None = None    # salary stated on the certificate (fraud cross-check)
    income_stable: bool = True
    temporary_hardship: bool = False
    obligations_ratio: float | None = None
    reason: str | None = None


def _next_reference(cur) -> str:
    year = datetime.now(timezone.utc).year
    cur.execute("SELECT COUNT(*) AS n FROM szhp_assessments WHERE reference LIKE %s", (f"SZHP-RS-{year}-%",))
    n = (cur.fetchone() or {}).get("n", 0) + 1
    return f"SZHP-RS-{year}-{n:05d}"


@router.post("/assess")
def assess(request: Request, body: AssessBody) -> dict:
    uid = get_authenticated_user_id(request) or body.user_id
    if not uid:
        raise HTTPException(401, "sign in required")
    if not body.declaration_accepted:
        raise HTTPException(400, "The authenticity declaration must be accepted before assessment.")

    loan = _loan_for(uid)
    if not loan:
        raise HTTPException(404, "No housing loan with arrears found for this beneficiary.")

    case = ArrearsCase(
        application_id=loan.get("application_id") or "—",
        customer_id=loan.get("edb_customer_id") or uid,
        applicant=loan.get("applicant") or get_authenticated_user_name(request) or "Beneficiary",
        current_salary=_f(loan.get("current_salary")),
        arrears=_f(loan.get("over_due_amt")),
        overdue_months=_f(loan.get("over_due_months")),
        current_emi=_f(loan.get("current_emi_amt")),
        original_term_months=int(loan.get("original_term_months") or 300),
        remaining_term_months=int(loan.get("remaining_term_months") or 180),
        family_size=loan.get("family_size"),
        dependents=loan.get("dependents"),
        has_active_request=bool(loan.get("has_active_request")),
        income_stable=body.income_stable,
        temporary_hardship=body.temporary_hardship,
        obligations_ratio=body.obligations_ratio,
        salary_cert_provided=body.salary_cert_provided,
        declared_salary=body.declared_salary,
    )
    a = assess_rescheduling(case)
    structured = a.structured(case)

    with db_cursor() as cur:
        ref = _next_reference(cur)
        cur.execute(
            """INSERT INTO szhp_assessments (
                 reference, application_id, user_id, customer_id, applicant,
                 recommendation, approved_request_type, confidence,
                 current_salary, arrears, current_emi, proposed_emi, proposed_term_months,
                 deduction_ratio, rule_20_pass, rule_period_pass, rule_active_pass,
                 status, reasoning, payload
               ) VALUES (
                 %(ref)s,%(app)s,%(uid)s,%(cust)s,%(appl)s,
                 %(rec)s,%(art)s,%(conf)s,
                 %(sal)s,%(arr)s,%(cur)s,%(pemi)s,%(pterm)s,
                 %(dr)s,%(r20)s,%(rp)s,%(ra)s,
                 %(st)s,%(reason)s,%(payload)s
               )""",
            {
                "ref": ref, "app": case.application_id, "uid": uid, "cust": case.customer_id,
                "appl": case.applicant, "rec": a.recommendation, "art": a.approved_request_type,
                "conf": a.confidence, "sal": case.current_salary, "arr": case.arrears,
                "cur": case.current_emi, "pemi": a.proposed_emi, "pterm": a.proposed_term_months,
                "dr": a.deduction_ratio, "r20": a.rule_20_pass, "rp": a.rule_period_pass,
                "ra": a.rule_active_pass, "st": a.status, "reason": " ".join(a.reasons),
                "payload": __import__("json").dumps(structured, ensure_ascii=False),
            },
        )
        # Audit trail — one row per decision step (explainability / governance).
        import json as _json
        events = [
            ("Retrieve", {"application_id": case.application_id, "salary": case.current_salary,
                          "arrears": case.arrears, "current_emi": case.current_emi}),
            ("Validate", {"documents_complete": a.application_complete,
                          "active_request": case.has_active_request, "declaration": body.declaration_accepted}),
            ("Analyse", structured["income_analysis"]),
            ("Policy", {"rule_20": structured["rule_20_compliance"],
                        "rule_period": structured["rule_period_compliance"],
                        "rule_active": structured["rule_active_request"]}),
            ("Decision", {"recommendation": a.recommendation, "type": a.approved_request_type,
                          "confidence": a.confidence, "reasoning": " ".join(a.reasons)}),
        ]
        for node, payload in events:
            cur.execute(
                "INSERT INTO audit_log (correlation_id, user_id, channel, node, payload) VALUES (%s,%s,%s,%s,%s)",
                (ref, uid, "web", node, _json.dumps(payload, ensure_ascii=False)),
            )
        # Activity feed
        cur.execute(
            """INSERT INTO activity_events (user_id, user_name, channel, event_type, summary, payload)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (uid, case.applicant, "web", "rescheduling_decision",
             f"{ref} · {a.recommendation} · {a.approved_request_type or '—'} · conf {a.confidence:.0%}",
             _json.dumps({"reference": ref, "recommendation": a.recommendation}, ensure_ascii=False)),
        )

    # Citizen-facing view: status + clear reason only (no internal calculations).
    citizen = {
        "reference": ref,
        "status": a.status,
        "status_label": _STATUS_LABEL.get(a.status, a.status),
        "headline": _headline(a, case),
        "reason": " ".join(a.reasons),
        "recommendation": a.recommendation,
    }
    return {"citizen": citizen, "assessment": structured, "reference": ref}


_STATUS_LABEL = {
    "approved": "Approved", "rejected": "Rejected", "request_documents": "Additional information required",
    "human_review": "Under officer review", "in_progress": "In progress",
}


def _headline(a, case: ArrearsCase) -> str:
    if a.recommendation == "approve" and a.approved_request_type == "UPDATE_INSTALLMENT":
        return f"Approved — new instalment AED {a.proposed_emi:,.0f}/month for {a.proposed_term_months} months."
    if a.recommendation == "approve" and a.approved_request_type == "TRANSFER_ARREARS":
        return "Approved — your arrears will be moved to the end of your loan; your monthly instalment stays the same."
    if a.recommendation == "request_documents":
        return "We need a valid salary certificate to continue."
    if a.recommendation == "reject":
        return "This request cannot proceed — an active request already exists."
    return "Your case is being reviewed by a Programme officer."


@router.get("/queue")
def queue(status: str | None = None, limit: int = 50) -> dict:
    with db_cursor() as cur:
        if status:
            cur.execute(
                "SELECT * FROM szhp_assessments WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                (status, limit))
        else:
            cur.execute("SELECT * FROM szhp_assessments ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.execute(
            """SELECT
                 COUNT(*) AS total,
                 COUNT(*) FILTER (WHERE status='approved') AS approved,
                 COUNT(*) FILTER (WHERE status='human_review') AS review,
                 COUNT(*) FILTER (WHERE status='rejected') AS rejected,
                 ROUND(AVG(confidence)::numeric,3) AS avg_confidence,
                 ROUND((COUNT(*) FILTER (WHERE status='approved'))::numeric
                       / NULLIF(COUNT(*),0) * 100, 0) AS auto_rate
               FROM szhp_assessments""")
        stats = cur.fetchone() or {}
    return {"stats": stats, "items": [_ser(r) for r in rows]}


@router.get("/assessment/{reference}")
def get_assessment(reference: str) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM szhp_assessments WHERE reference = %s", (reference,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "assessment not found")
        cur.execute(
            "SELECT node, payload, created_at FROM audit_log WHERE correlation_id = %s ORDER BY id",
            (reference,))
        audit = cur.fetchall()
    return {"assessment": _ser(row), "audit": [_ser(a) for a in audit]}


@router.post("/assessment/{reference}/action")
def officer_action(reference: str, payload: dict = Body(...)) -> dict:
    action = (payload.get("action") or "").lower()   # approve | override | refer
    note = payload.get("note")
    new_status = {"approve": "approved", "override": "approved", "refer": "human_review"}.get(action)
    if not new_status:
        raise HTTPException(400, "action must be approve | override | refer")
    with db_cursor() as cur:
        cur.execute(
            """UPDATE szhp_assessments
               SET status=%s, officer_action=%s, officer_note=%s, decided_at=NOW()
               WHERE reference=%s RETURNING reference""",
            (new_status, action, note, reference))
        if not cur.fetchone():
            raise HTTPException(404, "assessment not found")
        cur.execute(
            "INSERT INTO audit_log (correlation_id, user_id, channel, node, payload) VALUES (%s,%s,%s,%s,%s)",
            (reference, "officer", "web", "OfficerDecision",
             __import__("json").dumps({"action": action, "note": note, "status": new_status})))
    return {"reference": reference, "status": new_status, "action": action}


def _ser(row: dict) -> dict:
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "__float__") and not isinstance(v, (bool, int)):
            try:
                out[k] = float(v)
            except Exception:
                out[k] = v
        else:
            out[k] = v
    return out
