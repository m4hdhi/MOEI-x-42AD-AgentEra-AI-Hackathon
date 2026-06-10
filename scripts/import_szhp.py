"""Load the real SZHP Loan Arrears Rescheduling dataset (2023-2025) into Postgres.

These become the beneficiary loan + arrears records the rescheduling agent retrieves
automatically — no manual data entry (challenge: 'automated data retrieval'). Two records are
linked to the demo UAE PASS personas so signing in pulls a real loan instantly.

  uv run python scripts/import_szhp.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.core.db import db_cursor  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[1]
_CANDIDATES = [
    ROOT / "data" / "moei" / "SZHP_Reschedule_Arrears_2023-2025.xlsx",
    ROOT / "RescheduleArrears (1).xlsx",
]
FILE = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])

# Link two representative cases to the demo personas (set during a second pass).
ALI = "784-2002-1102000-2"      # clean UPDATE_INSTALLMENT candidate
FATIMA = "784-1990-1181000-4"   # hardship / TRANSFER_ARREARS candidate


def _num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _s(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return str(v).strip() or None


def main():
    if not FILE.exists():
        sys.exit(f"Dataset not found: {FILE}")
    total = 0
    with db_cursor() as cur:
        cur.execute("TRUNCATE szhp_loans")
        for year in ("2023", "2024", "2025"):
            df = pd.read_excel(FILE, sheet_name=year, header=0).dropna(how="all")
            for _, r in df.iterrows():
                appid = _s(r.get("APPLICATION_ID"))
                if not appid:
                    continue
                # remaining term: keep within a notional original 300-month approved period
                applicable = _num(r.get("NEW_EMI_APPLICABLE_MONTHS")) or 0
                cur.execute(
                    """INSERT INTO szhp_loans (
                        source_year, application_id, agreement_id, edb_loan_id, edb_customer_id,
                        applicant, request_type, approved_request_type, current_salary, over_due_amt,
                        over_due_months, deduct_from_salary, current_emi_amt, new_emi_amt,
                        new_emi_applicable_months, original_term_months, remaining_term_months,
                        created_date, status, approved_date, created_by, justifications, remarks
                    ) VALUES (
                        %(yr)s,%(appid)s,%(agr)s,%(loan)s,%(cust)s,%(appl)s,%(rt)s,%(art)s,%(sal)s,%(od)s,
                        %(odm)s,%(ded)s,%(cur)s,%(new)s,%(am)s,300,%(rem)s,%(cd)s,%(st)s,%(ad)s,%(cb)s,%(just)s,%(rem2)s
                    )""",
                    {
                        "yr": int(year), "appid": appid,
                        "agr": _s(r.get("AGREEMENT_ID")), "loan": _s(r.get("EDB_LOAN_ID")),
                        "cust": _s(r.get("EDB_CUSTOMER_ID")), "appl": _s(r.get("APPLICANT")),
                        "rt": _s(r.get("REQUEST_TYPE")), "art": _s(r.get("APPROVED_REQUEST_TYPE")),
                        "sal": _num(r.get("CURRENT_SALARY")), "od": _num(r.get("OVER_DUE_AMT")),
                        "odm": _num(r.get("OVER_DUE_MONTHS")), "ded": _num(r.get("DEDUCT_FROM_SALARY")),
                        "cur": _num(r.get("CURRENT_EMI_AMT")), "new": _num(r.get("NEW_EMI_AMT")),
                        "am": applicable or None,
                        "rem": int(min(240, max(60, 300 - (applicable or 60)))),
                        "cd": _s(r.get("CREATED_DATE")), "st": _s(r.get("STATUS")),
                        "ad": _s(r.get("APPROVED_DATE")), "cb": _s(r.get("CREATED_BY")),
                        "just": _s(r.get("JUSTIFICATIONS")), "rem2": _s(r.get("REMARKS")),
                    },
                )
                total += 1

        # ── link demo personas to clean, illustrative cases ──
        # Ali: healthy salary, moderate arrears → approvable UPDATE_INSTALLMENT within 20%.
        cur.execute(
            """WITH pick AS (
                 SELECT id FROM szhp_loans
                 WHERE current_salary BETWEEN 20000 AND 45000 AND over_due_amt BETWEEN 20000 AND 80000
                   AND current_emi_amt > 0 AND approved_request_type = 'UPDATE_INSTALLMENT'
                 ORDER BY id LIMIT 1)
               UPDATE szhp_loans s SET user_id=%s, applicant='Ali Al Rumaithi', edb_customer_id='UAE-001102',
                      family_size=4, dependents=2, has_active_request=FALSE
               FROM pick WHERE s.id = pick.id""",
            (ALI,),
        )
        # Fatima: tighter salary, heavier arrears → hardship → TRANSFER_ARREARS / refer.
        cur.execute(
            """WITH pick AS (
                 SELECT id FROM szhp_loans
                 WHERE current_salary BETWEEN 8000 AND 16000 AND over_due_amt > 60000
                   AND current_emi_amt > 0
                 ORDER BY over_due_amt DESC LIMIT 1)
               UPDATE szhp_loans s SET user_id=%s, applicant='Fatima Al Mansouri', edb_customer_id='UAE-001181',
                      family_size=6, dependents=4, has_active_request=FALSE
               FROM pick WHERE s.id = pick.id""",
            (FATIMA,),
        )

    print(f"  ✓ szhp_loans loaded: {total} applications (2023-2025)")
    with db_cursor() as cur:
        cur.execute("SELECT user_id, applicant, current_salary, over_due_amt, current_emi_amt FROM szhp_loans WHERE user_id IS NOT NULL")
        for row in cur.fetchall():
            print("    linked:", dict(row))

    seed_assessment_queue(28)


def seed_assessment_queue(n: int) -> None:
    """Pre-run the agent over a sample of real applications so the officer console is populated
    with varied, realistic decisions out of the box."""
    import json
    sys.path.insert(0, str(ROOT / "agents"))
    from hassan.tools.arrears_engine import ArrearsCase, assess_rescheduling  # type: ignore

    with db_cursor() as cur:
        cur.execute("TRUNCATE szhp_assessments")
        cur.execute(
            """SELECT * FROM szhp_loans
               WHERE current_salary > 0 AND current_emi_amt > 0 AND over_due_amt > 0
               ORDER BY random() LIMIT %s""",
            (n,),
        )
        rows = cur.fetchall()
        made = 0
        for i, loan in enumerate(rows, 1):
            sal = float(loan["current_salary"] or 0)
            fam = int(loan["family_size"] or (3 if i % 3 else 6))
            case = ArrearsCase(
                application_id=loan.get("application_id") or f"APP-{i}",
                customer_id=loan.get("edb_customer_id") or "—",
                applicant=(loan.get("applicant") or f"Beneficiary {i}"),
                current_salary=sal, arrears=float(loan["over_due_amt"] or 0),
                overdue_months=float(loan["over_due_months"] or 1),
                current_emi=float(loan["current_emi_amt"] or 0),
                original_term_months=int(loan["original_term_months"] or 300),
                remaining_term_months=int(loan["remaining_term_months"] or 180),
                family_size=fam, dependents=max(0, fam - 2),
                income_stable=(i % 5 != 0),                 # ~20% unstable income
                has_active_request=(i % 13 == 0),           # a few auto-rejects
            )
            a = assess_rescheduling(case)
            s = a.structured(case)
            ref = f"SZHP-RS-2026-{i:05d}"
            cur.execute(
                """INSERT INTO szhp_assessments (
                     reference, application_id, user_id, customer_id, applicant, recommendation,
                     approved_request_type, confidence, current_salary, arrears, current_emi,
                     proposed_emi, proposed_term_months, deduction_ratio, rule_20_pass,
                     rule_period_pass, rule_active_pass, status, reasoning, payload
                   ) VALUES (
                     %(ref)s,%(app)s,NULL,%(cust)s,%(appl)s,%(rec)s,%(art)s,%(conf)s,%(sal)s,%(arr)s,
                     %(cur)s,%(pemi)s,%(pterm)s,%(dr)s,%(r20)s,%(rp)s,%(ra)s,%(st)s,%(reason)s,%(payload)s
                   ) ON CONFLICT (reference) DO NOTHING""",
                {
                    "ref": ref, "app": case.application_id, "cust": case.customer_id, "appl": case.applicant,
                    "rec": a.recommendation, "art": a.approved_request_type, "conf": a.confidence,
                    "sal": case.current_salary, "arr": case.arrears, "cur": case.current_emi,
                    "pemi": a.proposed_emi, "pterm": a.proposed_term_months, "dr": a.deduction_ratio,
                    "r20": a.rule_20_pass, "rp": a.rule_period_pass, "ra": a.rule_active_pass,
                    "st": a.status, "reason": " ".join(a.reasons),
                    "payload": json.dumps(s, ensure_ascii=False),
                },
            )
            made += 1
    print(f"  ✓ officer queue seeded: {made} assessments")


if __name__ == "__main__":
    main()
