"""Load the official MOEI Omnichannel hackathon dataset into Postgres as the source of truth.

Reads the five-sheet workbook and loads:
  • CRM — Customer Profiles      → citizens   (unified profile, challenge Q9)
  • Service Requests & Cases     → cases       (rich case fields + SLA + reopen)
  • WhatsApp / Voice / Web logs  → interactions (unified cross-channel history, Q8/Q10/Q20)

Everything is linked by Customer ID (e.g. UAE-001046) so any channel can retrieve the full
profile + history instantly. Idempotent — wipes prior dataset rows before reload.

  uv run python scripts/import_dataset.py
  uv run python scripts/import_dataset.py --file "/path/to/MOEI_..._Hackathon.xlsx"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.core.db import db_cursor  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[1]
# Prefer the clean in-repo copy; fall back to the original download name at the repo root.
_CANDIDATES = [
    ROOT / "data" / "moei" / "MOEI_Omnichannel_AI_Dataset.xlsx",
    ROOT / "MOEI_Omnichannel_AI_Dataset_Hackathon (1) (2).xlsx",
]
DEFAULT_FILE = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])

# ── enum normalisation to the app's vocabulary ──────────────────────────────
CHANNEL_MAP = {
    "whatsapp": "whatsapp", "voice": "voice", "website": "web", "web": "web",
    "mobile app": "mobile", "mobile": "mobile", "app": "mobile",
}
SERVICE_MAP = {
    "housing services": "housing", "housing": "housing",
    "land & real estate": "land", "land": "land",
    "maritime services": "maritime", "maritime": "maritime",
    "transport & vehicles": "transport", "transport": "transport",
    "energy": "energy", "infrastructure": "infrastructure",
}
STATUS_MAP = {
    "pending": "open", "open": "open", "new": "open",
    "in progress": "in_progress", "in-progress": "in_progress",
    "escalated": "escalated", "resolved": "resolved",
    "closed – no action": "closed", "closed - no action": "closed", "closed": "closed",
}
INTENT_MAP = {
    "new application": "service_request", "renewal request": "service_request",
    "status inquiry": "status_check", "complaint": "complaint",
    "appeal / objection": "complaint", "document submission": "document_upload",
    "emergency report": "complaint", "fee payment inquiry": "status_check",
    "general information": "inquiry", "appointment booking": "service_request",
}


# ── tiny cleaning helpers ────────────────────────────────────────────────────
def _s(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip()
    return s or None


def _norm(v, mapping, default=None):
    s = _s(v)
    if s is None:
        return default
    return mapping.get(s.lower(), default if default is not None else s.lower())


def _yesbool(v):
    s = _s(v)
    return None if s is None else s.lower() in ("yes", "true", "1", "y")


def _int(v):
    s = _s(v)
    if s is None:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _num(v):
    s = _s(v)
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _csat_to_unit(csat):
    """1..5 CSAT → 0..1 sentiment proxy used by the cases.sentiment column."""
    n = _int(csat)
    return round((n - 1) / 4.0, 2) if n else None


def _dt(*parts):
    """Combine date + optional time cells into a timestamp; tolerant of many formats."""
    vals = [p for p in parts if _s(p) is not None]
    if not vals:
        return None
    for v in vals:
        if isinstance(v, (datetime, pd.Timestamp)):
            return pd.Timestamp(v).to_pydatetime()
    txt = " ".join(str(v) for v in vals)
    try:
        ts = pd.to_datetime(txt, errors="coerce", dayfirst=False)
        return None if pd.isna(ts) else ts.to_pydatetime()
    except Exception:
        return None


def _date(v):
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(v).date()
    s = _s(v)
    if not s:
        return None
    ts = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def _jsonable(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        if isinstance(v, (datetime, date, pd.Timestamp)):
            out[str(k)] = str(v)
        else:
            out[str(k)] = v if isinstance(v, (str, int, float, bool)) else str(v)
    return out


def load_sheet(path: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, header=3)
    df = df.dropna(how="all")
    df = df[df[df.columns[0]].notna()]  # drop trailing footnote rows
    return df


# ── loaders ──────────────────────────────────────────────────────────────────
def import_crm(path: Path) -> int:
    df = load_sheet(path, "CRM — Customer Profiles")
    n = 0
    with db_cursor() as cur:
        cur.execute("DELETE FROM citizens WHERE customer_id IS NOT NULL")
        for _, r in df.iterrows():
            cid = _s(r.get("Customer ID"))
            if not cid:
                continue
            cur.execute(
                """
                INSERT INTO citizens (
                    user_id, customer_id, full_name_en, full_name_ar, mobile, email,
                    emirate, area, nationality, customer_type, account_status,
                    registered_since, last_interaction_date, total_interactions,
                    whatsapp_interactions, voice_interactions, web_sessions,
                    open_cases, resolved_cases, escalated_cases, preferred_channel,
                    avg_csat, avg_nps, lifetime_sentiment, risk_flag, vip_tier,
                    smart_meter, renewable_customer, num_properties, last_service,
                    crm_agent, tags, preferred_language, verified, channels_used,
                    first_seen_at, last_seen_at
                ) VALUES (
                    %(uid)s, %(cid)s, %(en)s, %(ar)s, %(mob)s, %(email)s,
                    %(emirate)s, %(area)s, %(nat)s, %(ctype)s, %(astatus)s,
                    %(reg)s, %(lastint)s, %(tot)s,
                    %(wa)s, %(vo)s, %(web)s,
                    %(oc)s, %(rc)s, %(ec)s, %(pref)s,
                    %(csat)s, %(nps)s, %(life)s, %(risk)s, %(vip)s,
                    %(meter)s, %(renew)s, %(props)s, %(lastsvc)s,
                    %(agent)s, %(tags)s, %(lang)s, TRUE, %(channels)s,
                    NOW(), NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    customer_id = EXCLUDED.customer_id, full_name_en = EXCLUDED.full_name_en,
                    full_name_ar = EXCLUDED.full_name_ar, mobile = EXCLUDED.mobile,
                    vip_tier = EXCLUDED.vip_tier, risk_flag = EXCLUDED.risk_flag,
                    preferred_channel = EXCLUDED.preferred_channel
                """,
                {
                    "uid": cid, "cid": cid,
                    "en": _s(r.get("Full Name (EN)")), "ar": _s(r.get("Full Name (AR)")),
                    "mob": _s(r.get("Phone Number")), "email": _s(r.get("Email")),
                    "emirate": _s(r.get("Emirate")), "area": _s(r.get("Area / District")),
                    "nat": _s(r.get("Nationality")), "ctype": _s(r.get("Customer Type")),
                    "astatus": _s(r.get("Account Status")),
                    "reg": _date(r.get("Registered Since")),
                    "lastint": _date(r.get("Last Interaction Date")),
                    "tot": _int(r.get("Total Interactions")),
                    "wa": _int(r.get("WhatsApp Interactions")),
                    "vo": _int(r.get("Voice Interactions")),
                    "web": _int(r.get("Web / App Sessions")),
                    "oc": _int(r.get("Open Cases")), "rc": _int(r.get("Resolved Cases")),
                    "ec": _int(r.get("Escalated Cases")),
                    "pref": _norm(r.get("Preferred Channel"), CHANNEL_MAP),
                    "csat": _num(r.get("Avg CSAT Score")), "nps": _num(r.get("Avg NPS Score")),
                    "life": _num(r.get("Lifetime Sentiment Score")),
                    "risk": _s(r.get("Risk Flag")), "vip": _s(r.get("VIP Tier")),
                    "meter": _yesbool(r.get("Smart Meter Installed")),
                    "renew": _yesbool(r.get("Renewable Energy Customer")),
                    "props": _int(r.get("Number of Properties")),
                    "lastsvc": _s(r.get("Last Service Requested")),
                    "agent": _s(r.get("CRM Agent Assigned")), "tags": _s(r.get("Notes / Tags")),
                    "lang": (_s(r.get("Language Preference")) or "en")[:2].lower(),
                    "channels": json.dumps([]),
                },
            )
            n += 1
    return n


def import_cases(path: Path) -> int:
    df = load_sheet(path, "Service Requests & Cases")
    n = 0
    with db_cursor() as cur:
        cur.execute("DELETE FROM cases WHERE case_number LIKE 'MOEI-CASE-%'")
        for _, r in df.iterrows():
            cnum = _s(r.get("Case ID"))
            if not cnum:
                continue
            escalated = _yesbool(r.get("Escalated")) or False
            status = _norm(r.get("Status"), STATUS_MAP, "open")
            opened = _dt(r.get("Date Opened"))
            closed = _dt(r.get("Date Closed"))
            cur.execute(
                """
                INSERT INTO cases (
                    case_number, user_id, customer_id, user_name, channel, intent, service,
                    service_category, sub_service, case_type, title, description, description_ar,
                    priority, status, sentiment, csat, assigned_to, assigned_team,
                    channels_used, cross_channel_flag, escalated, escalation_reason,
                    supervisor_involved, ai_auto_classified, ai_suggested_resolution,
                    agent_override, sla_target_hrs, sla_met, resolution_time_hrs, reopen_count,
                    root_cause, linked_case_id, emirate, date_opened, date_closed,
                    created_at, updated_at, resolved_at
                ) VALUES (
                    %(cnum)s, %(uid)s, %(uid)s, %(name)s, %(chan)s, %(intent)s, %(svc)s,
                    %(svccat)s, %(sub)s, %(ctype)s, %(title)s, %(desc)s, %(descar)s,
                    %(prio)s, %(status)s, %(sent)s, %(csat)s, %(agent)s, %(team)s,
                    %(channels)s, %(xchan)s, %(esc)s, %(escr)s,
                    %(sup)s, %(aiclass)s, %(aires)s,
                    %(override)s, %(slatgt)s, %(slamet)s, %(restime)s, %(reopen)s,
                    %(root)s, %(linked)s, %(emirate)s, %(opened)s, %(closed)s,
                    COALESCE(%(opened)s, NOW()), COALESCE(%(updated)s, NOW()), %(closed)s
                )
                ON CONFLICT (case_number) DO UPDATE SET
                    status = EXCLUDED.status, sla_met = EXCLUDED.sla_met,
                    reopen_count = EXCLUDED.reopen_count
                """,
                {
                    "cnum": cnum, "uid": _s(r.get("Customer ID")),
                    "name": _s(r.get("Customer Name (EN)")),
                    "chan": _norm(r.get("Channel Created"), CHANNEL_MAP, "web"),
                    "intent": "service_request",
                    "svc": _norm(r.get("Service Category"), SERVICE_MAP, "general"),
                    "svccat": _s(r.get("Service Category")), "sub": _s(r.get("Sub-Service")),
                    "ctype": _s(r.get("Case Type")),
                    "title": (_s(r.get("Sub-Service")) or _s(r.get("Service Category")) or "Case"),
                    "desc": _s(r.get("Issue Description (EN)")),
                    "descar": _s(r.get("Issue Description (AR)")),
                    "prio": (_s(r.get("Priority")) or "medium").lower(),
                    "status": status, "sent": _csat_to_unit(r.get("Customer Satisfaction (1-5)")),
                    "csat": _int(r.get("Customer Satisfaction (1-5)")),
                    "agent": _s(r.get("Assigned Agent")), "team": _s(r.get("Assigned Team")),
                    "channels": json.dumps([c.strip() for c in (_s(r.get("Channels Used")) or "").replace("/", ",").split(",") if c.strip()]),
                    "xchan": _yesbool(r.get("Cross-Channel Flag")),
                    "esc": escalated, "escr": _s(r.get("Escalation Reason")),
                    "sup": _s(r.get("Supervisor Involved")),
                    "aiclass": _yesbool(r.get("AI Auto-Classified")),
                    "aires": _s(r.get("AI Suggested Resolution")),
                    "override": _yesbool(r.get("Agent Override")),
                    "slatgt": _num(r.get("SLA Target (hrs)")), "slamet": _s(r.get("SLA Met")),
                    "restime": _num(r.get("Resolution Time (hrs)")),
                    "reopen": _int(r.get("Reopen Count")) or 0,
                    "root": _s(r.get("Root Cause")), "linked": _s(r.get("Linked Case ID")),
                    "emirate": None,
                    "opened": opened, "closed": closed,
                    "updated": _dt(r.get("Date Last Updated")),
                },
            )
            n += 1
    return n


def import_interactions(path: Path) -> int:
    total = 0
    with db_cursor() as cur:
        cur.execute("TRUNCATE interactions")

    def insert(rows):
        with db_cursor() as cur:
            for p in rows:
                cur.execute(
                    """
                    INSERT INTO interactions (
                        interaction_id, customer_id, customer_name_en, customer_name_ar,
                        channel, occurred_at, language, emirate, intent, service_category,
                        sub_service, message_sample, sentiment_label, sentiment_score, csat,
                        escalated, resolution_status, case_id, raw
                    ) VALUES (
                        %(iid)s, %(cid)s, %(en)s, %(ar)s, %(chan)s, %(at)s, %(lang)s, %(emirate)s,
                        %(intent)s, %(svc)s, %(sub)s, %(msg)s, %(slabel)s, %(sscore)s, %(csat)s,
                        %(esc)s, %(res)s, %(case)s, %(raw)s
                    )
                    """,
                    p,
                )

    # WhatsApp
    df = load_sheet(path, "WhatsApp Logs")
    batch = []
    for _, r in df.iterrows():
        cid = _s(r.get("Customer ID"))
        if not cid:
            continue
        batch.append({
            "iid": _s(r.get("Session ID")), "cid": cid,
            "en": _s(r.get("Customer Name (EN)")), "ar": _s(r.get("Customer Name (AR)")),
            "chan": "whatsapp", "at": _dt(r.get("Date"), r.get("Time")),
            "lang": (_s(r.get("Language")) or "en")[:2].lower(), "emirate": _s(r.get("Emirate")),
            "intent": _norm(r.get("Bot Intent Detected"), INTENT_MAP, _s(r.get("Bot Intent Detected"))),
            "svc": _s(r.get("Service Category")), "sub": _s(r.get("Sub-Service")),
            "msg": _s(r.get("Customer Message (Sample)")) or _s(r.get("First Message")),
            "slabel": _s(r.get("Sentiment Label")), "sscore": _num(r.get("Sentiment Score (-1 to 1)")),
            "csat": _int(r.get("CSAT Score (1-5)")), "esc": _yesbool(r.get("Escalated to Human")),
            "res": _s(r.get("Resolution Status")), "case": _s(r.get("Case ID Created")),
            "raw": json.dumps(_jsonable(r.to_dict())),
        })
    insert(batch); total += len(batch)

    # Voice
    df = load_sheet(path, "Voice Contact Center")
    batch = []
    for _, r in df.iterrows():
        cid = _s(r.get("Customer ID"))
        if not cid:
            continue
        batch.append({
            "iid": _s(r.get("Call ID")), "cid": cid,
            "en": _s(r.get("Customer Name (EN)")), "ar": _s(r.get("Customer Name (AR)")),
            "chan": "voice", "at": _dt(r.get("Call Date"), r.get("Call Start Time")),
            "lang": (_s(r.get("Language")) or "en")[:2].lower(), "emirate": _s(r.get("Emirate")),
            "intent": _norm(r.get("Intent at IVR"), INTENT_MAP, _s(r.get("Intent at IVR"))),
            "svc": _s(r.get("Service Category")), "sub": _s(r.get("Sub-Service")),
            "msg": _s(r.get("Notes")),
            "slabel": _s(r.get("Overall Sentiment Label")), "sscore": _num(r.get("Sentiment — Closing")),
            "csat": _int(r.get("CSAT Score (1-5)")), "esc": _yesbool(r.get("Escalated to Supervisor")),
            "res": _s(r.get("Call Outcome")), "case": _s(r.get("Case ID Created")),
            "raw": json.dumps(_jsonable(r.to_dict())),
        })
    insert(batch); total += len(batch)

    # Website & Mobile App
    df = load_sheet(path, "Website & Mobile App")
    batch = []
    for _, r in df.iterrows():
        cid = _s(r.get("Customer ID"))
        if not cid:
            continue
        batch.append({
            "iid": _s(r.get("Session ID")), "cid": cid,
            "en": _s(r.get("Customer Name (EN)")), "ar": _s(r.get("Customer Name (AR)")),
            "chan": _norm(r.get("Platform"), CHANNEL_MAP, "web"),
            "at": _dt(r.get("Session Date"), r.get("Session Start Time")),
            "lang": (_s(r.get("Language")) or "en")[:2].lower(), "emirate": _s(r.get("Emirate")),
            "intent": _norm(r.get("Chatbot Intent Detected"), INTENT_MAP, _s(r.get("Chatbot Intent Detected"))),
            "svc": _s(r.get("Service Accessed")), "sub": _s(r.get("Transaction Type")),
            "msg": _s(r.get("Search Query (if any)")) or _s(r.get("Feedback Text (Sample)")),
            "slabel": _s(r.get("Sentiment Label")), "sscore": None,
            "csat": _int(r.get("CSAT Score (1-5)")), "esc": False,
            "res": _s(r.get("Chatbot Resolution")), "case": _s(r.get("Case ID Linked")),
            "raw": json.dumps(_jsonable(r.to_dict())),
        })
    insert(batch); total += len(batch)
    return total


# Two dataset customers are surfaced as the UAE PASS demo identities so that signing in lands
# on a real, rich cross-channel profile. We re-key their records to the demo Emirates IDs that
# the mock UAE PASS issues (see apps/api/app/routes/mock_uaepass.py).
DEMO_PERSONAS = {
    "UAE-001102": "784-2002-1102000-2",  # Ali Al Rumaithi (Gold, 3 channels)
    "UAE-001181": "784-1990-1181000-4",  # Fatima Al Mansouri (repeat escalator)
}
# Old developer test identities to purge (kept out of the demo).
_OLD_TEST_IDS = ("784-2004-6541442-1", "784-1998-1234567-5")


def finalize_demo() -> None:
    with db_cursor() as cur:
        # 1) remove old developer test personas
        cur.execute("DELETE FROM citizens WHERE user_id = ANY(%s)", (list(_OLD_TEST_IDS),))
        cur.execute("DELETE FROM cases WHERE user_id = ANY(%s)", (list(_OLD_TEST_IDS),))

        # 2) re-key the two demo customers to their UAE PASS Emirates IDs so login → real profile
        for cust, eid in DEMO_PERSONAS.items():
            cur.execute("DELETE FROM citizens WHERE user_id = %s", (eid,))
            cur.execute("UPDATE citizens SET user_id=%s, customer_id=%s WHERE customer_id=%s", (eid, eid, cust))
            cur.execute("UPDATE cases SET user_id=%s, customer_id=%s WHERE customer_id=%s", (eid, eid, cust))
            cur.execute("UPDATE interactions SET customer_id=%s WHERE customer_id=%s", (eid, cust))

        # 3) Compress all dataset dates into the last WINDOW_DAYS so the time-windowed dashboards
        #    (today / 7d / 30d) are densely populated for the demo. A single monotonic linear map
        #    over every timestamp preserves ordering (created < resolved stays true).
        WINDOW_DAYS = 30
        cur.execute(
            """SELECT LEAST(
                   (SELECT MIN(created_at) FROM cases WHERE case_number LIKE 'MOEI-CASE-%%'),
                   (SELECT MIN(occurred_at) FROM interactions)) AS gmin,
                 GREATEST(
                   (SELECT MAX(created_at) FROM cases WHERE case_number LIKE 'MOEI-CASE-%%'),
                   (SELECT MAX(occurred_at) FROM interactions)) AS gmax"""
        )
        b = cur.fetchone() or {}
        gmin, gmax = b.get("gmin"), b.get("gmax")
        if gmin and gmax and gmax > gmin:
            span = (gmax - gmin).total_seconds()
            win = WINDOW_DAYS * 86400.0
            p = {"gmin": gmin, "span": span, "win": win}
            # map t -> (now - WINDOW) + ((t - gmin)/span) * WINDOW
            expr = ("(NOW() - INTERVAL '%d days') + "
                    "((EXTRACT(EPOCH FROM ({col} - %%(gmin)s)) / %%(span)s) * %%(win)s) * INTERVAL '1 second'") % WINDOW_DAYS
            cur.execute(
                f"""UPDATE cases SET
                      created_at  = {expr.format(col='created_at')},
                      updated_at  = {expr.format(col='updated_at')},
                      date_opened = {expr.format(col='date_opened')},
                      date_closed = {expr.format(col='date_closed')},
                      resolved_at = {expr.format(col='resolved_at')}
                    WHERE case_number LIKE 'MOEI-CASE-%%'""",
                p,
            )
            cur.execute(f"UPDATE interactions SET occurred_at = {expr.format(col='occurred_at')}", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"Dataset not found: {path}")

    print(f"Loading dataset: {path.name}")
    c = import_crm(path)
    print(f"  ✓ CRM profiles → citizens:   {c}")
    k = import_cases(path)
    print(f"  ✓ Service cases → cases:      {k}")
    i = import_interactions(path)
    print(f"  ✓ Channel logs → interactions: {i}")
    finalize_demo()
    print("  ✓ Rebased dates to now + linked demo personas (Ali, Fatima); purged old test IDs")
    print("Done.")


if __name__ == "__main__":
    main()
