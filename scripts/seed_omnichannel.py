"""Seed Hassan's Postgres tables with realistic synthetic data so the dashboards have content.

  uv run python scripts/seed_omnichannel.py

Generates:
  - 200 cases spread over the last 28 days, weighted by realistic weekday/hour patterns
  - 30 scheduled + 20 sent notifications
  - 100 activity events (turn / case_created / escalation / channel_switch)

All synthetic — same shape MOEI's real CRM data will have. Re-runnable; clears prior synthetic
rows by case_number prefix.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.core.db import db_cursor   # type: ignore[import-not-found]

random.seed(42)
NOW = datetime.now(timezone.utc)

# ---- Synthetic citizen pool (matches our uaepass_lookup + adds more for variety) -----
CITIZENS = [
    ("784-2004-6541442-1", "Mahdhi Muzammil"),
    ("784-1985-0000002-3", "Ahmed Al Suwaidi"),
    ("784-1998-1234567-5", "Aisha Al Marri"),
    ("784-1972-2233445-2", "Mohammed Al Hashimi"),
    ("784-1988-7766554-6", "Fatima Al Qubaisi"),
    ("784-1995-1122334-0", "Khalid Al Mazrouei"),
    ("784-1980-9988776-4", "Maryam Al Shamsi"),
    ("784-2000-5544332-9", "Salem Al Dhaheri"),
    ("784-1976-3344556-7", "Noura Al Falasi"),
    ("784-1991-6677889-1", "Omar Al Kaabi"),
    ("784-1968-1212343-8", "Rashid Al Nuaimi"),
    ("784-1993-4554667-3", "Hessa Al Ameri"),
    ("784-1986-8899007-5", "Sultan Al Rashidi"),
    ("784-1979-2345112-4", "Latifa Al Maktoum"),
    ("784-2001-7654321-2", "Yousef Al Romaithi"),
]

SERVICES = ["housing", "energy", "maritime", "transport", "infrastructure", "general"]
SERVICE_WEIGHTS = [40, 18, 8, 12, 10, 12]
CHANNELS = ["whatsapp", "voice", "web", "mobile"]
CHANNEL_WEIGHTS = [42, 15, 35, 8]
INTENTS = ["service_request", "status_check", "complaint", "suggestion", "appreciation",
           "document_upload", "escalate_to_human"]
INTENT_WEIGHTS = [40, 22, 12, 6, 8, 8, 4]
PRIORITIES = ["low", "medium", "high", "critical"]
PRIORITY_WEIGHTS = [10, 60, 25, 5]
STATUSES = ["open", "in_progress", "resolved", "escalated", "closed"]
STATUS_WEIGHTS = [25, 20, 35, 10, 10]

TEMPLATES_EN = {
    "housing": [
        "I'm 3 months behind on my SZHP loan, need help with rescheduling",
        "Looking for guidance on the housing assistance application process",
        "Need status update on my SZHP grant application from last month",
        "I want to submit additional documents for my pending housing case",
        "Reconsideration request for housing assistance decision",
    ],
    "energy": [
        "Power outage in my area, need a case reference",
        "Question about tariff for my villa",
        "Petroleum products trading registration help",
        "Water bill seems incorrect this month",
    ],
    "maritime": [
        "How do I renew my pleasure boat registration?",
        "Navigation license for commercial ship — what documents?",
        "Seafarer certificate renewal process",
    ],
    "transport": [
        "Applying for national transportation permit for my fleet",
        "Renew vehicle permit — what is the SLA?",
        "Non-objection certificate for vehicle transfer",
    ],
    "infrastructure": [
        "Need geological survey data for construction project",
        "Infrastructure permit application status",
        "Field visit permit request",
    ],
    "general": [
        "Need help finding the right MOEI department",
        "Question about MOEI services in my area",
        "I want to file a suggestion for service improvement",
    ],
}

APPRECIATIONS_EN = [
    "Thank you so much for the quick response, excellent service!",
    "Great help from your team, very smooth process.",
    "Appreciate the fast resolution, MOEI is doing a fantastic job.",
]

COMPLAINTS_EN = [
    "This is unacceptable, I've been waiting 3 weeks with no response",
    "Frustrated with the lack of communication on my case",
    "My case is stuck, no one is responding to my emails",
]

SUGGESTIONS_EN = [
    "Why don't you allow document upload via WhatsApp directly?",
    "Suggestion: add an Arabic option to the mobile app's notification settings",
    "You should provide a status SMS automatically every 3 days",
]


def gen_text(intent: str, service: str) -> str:
    if intent == "appreciation":
        return random.choice(APPRECIATIONS_EN)
    if intent == "complaint":
        return random.choice(COMPLAINTS_EN)
    if intent == "suggestion":
        return random.choice(SUGGESTIONS_EN)
    return random.choice(TEMPLATES_EN.get(service, TEMPLATES_EN["general"]))


def gen_sentiment(intent: str) -> float:
    base = {
        "appreciation": 0.92, "complaint": 0.22, "suggestion": 0.55,
        "status_check": 0.55, "escalate_to_human": 0.30,
    }.get(intent, 0.62)
    return round(max(0.05, min(0.98, base + random.uniform(-0.12, 0.12))), 2)


def weekday_hour_weight(d: datetime) -> float:
    """Realistic UAE-business demand curve: peak 9-12 + 14-17, Sun-Thu strong, Fri-Sat lower."""
    dow = d.weekday()        # 0=Mon..6=Sun
    if dow >= 5:             # Sat (5), Sun (6) → UAE weekend is Fri+Sat now, but historic Sun = mixed
        base = 0.35 if dow == 5 else 0.6
    elif dow == 4:           # Friday
        base = 0.30
    else:
        base = 1.0
    h = d.hour
    if 9 <= h < 12: hour_w = 1.4
    elif 14 <= h < 17: hour_w = 1.3
    elif 8 <= h < 9 or 12 <= h < 14 or 17 <= h < 19: hour_w = 0.9
    elif 19 <= h < 22: hour_w = 0.5
    else: hour_w = 0.15
    return base * hour_w


def seed_cases(n: int = 200) -> list[str]:
    """Returns the inserted case_numbers + the (id, user_id, channel) tuples."""
    inserted: list[tuple[str, str]] = []
    with db_cursor() as cur:
        cur.execute("DELETE FROM cases WHERE case_number LIKE 'MOEI-CASE-SYN-%'")
        cur.execute("DELETE FROM notifications WHERE payload->>'synthetic' = 'true'")
        cur.execute("DELETE FROM activity_events WHERE payload->>'synthetic' = 'true'")
        per_day_count = 0
        for i in range(n):
            # Random offset within last 28 days, weighted toward business hours
            while True:
                offset_days = random.randint(0, 27)
                base = NOW - timedelta(days=offset_days, hours=random.randint(0, 23), minutes=random.randint(0, 59))
                w = weekday_hour_weight(base)
                if random.random() < w:
                    break
            user_id, user_name = random.choice(CITIZENS)
            service = random.choices(SERVICES, weights=SERVICE_WEIGHTS)[0]
            channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
            intent = random.choices(INTENTS, weights=INTENT_WEIGHTS)[0]
            text = gen_text(intent, service)
            sentiment = gen_sentiment(intent)
            # Priority is correlated with intent + sentiment
            if intent == "complaint" and sentiment < 0.3:
                priority = "critical"
            elif intent in ("complaint", "escalate_to_human"):
                priority = "high"
            elif intent == "appreciation":
                priority = "low"
            else:
                priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0]
            status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
            case_number = f"MOEI-CASE-SYN-{base:%Y%m%d}-{i:04d}"
            resolved_at = base + timedelta(hours=random.randint(2, 72)) if status in ("resolved", "closed") else None

            cur.execute(
                """
                INSERT INTO cases (case_number, user_id, user_name, channel, intent, service,
                                   title, description, priority, status, sentiment,
                                   correlation_id, created_at, updated_at, resolved_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (case_number, user_id, user_name, channel, intent, service,
                 f"{intent.replace('_',' ').title()} — {service} · {text[:60]}", text,
                 priority, status, sentiment,
                 f"syn-{i:04d}", base, base, resolved_at),
            )
            inserted.append((case_number, user_id))
    print(f"  ✓ inserted {len(inserted)} cases")
    return [c for c, _ in inserted]


def seed_notifications(case_numbers: list[str]) -> None:
    templates = ["status_update", "doc_reminder", "csat_survey", "proactive_tip"]
    n_scheduled = 30
    n_sent = 20
    with db_cursor() as cur:
        # 30 upcoming
        for i in range(n_scheduled):
            cn = random.choice(case_numbers)
            cur.execute("SELECT id, user_id FROM cases WHERE case_number = %s", (cn,))
            row = cur.fetchone()
            if not row: continue
            template = random.choice(templates)
            scheduled = NOW + timedelta(hours=random.randint(1, 96))
            cur.execute(
                """
                INSERT INTO notifications (user_id, case_id, channel, template, payload, scheduled_at, status)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, 'scheduled')
                """,
                (row["user_id"], row["id"], random.choice(["whatsapp", "sms", "email"]),
                 template, json.dumps({"synthetic": "true", "case": cn}), scheduled),
            )
        # 20 already sent
        for i in range(n_sent):
            cn = random.choice(case_numbers)
            cur.execute("SELECT id, user_id FROM cases WHERE case_number = %s", (cn,))
            row = cur.fetchone()
            if not row: continue
            template = random.choice(templates)
            scheduled = NOW - timedelta(hours=random.randint(2, 240))
            cur.execute(
                """
                INSERT INTO notifications (user_id, case_id, channel, template, payload, scheduled_at, sent_at, status)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, 'sent')
                """,
                (row["user_id"], row["id"], random.choice(["whatsapp", "sms", "email"]),
                 template, json.dumps({"synthetic": "true", "case": cn}),
                 scheduled, scheduled + timedelta(minutes=2)),
            )
    print(f"  ✓ inserted {n_scheduled} upcoming + {n_sent} sent notifications")


def seed_activity_events() -> None:
    """100 recent activity events for the live ticker (visible history at page load)."""
    EVENT_TYPES = [
        ("turn", "Citizen turn on {channel}"),
        ("case_created", "New {priority} case · {service}"),
        ("escalation", "Escalated to co-pilot · low sentiment"),
        ("channel_switch", "Switched from {prev_channel} → {channel}"),
        ("nba_offered", "Co-pilot offered: {action}"),
        ("sentiment_change", "Sentiment dropped to {sentiment}"),
    ]
    actions = [
        "Acknowledge stress, offer 24-month plan",
        "Confirm complaint, schedule callback",
        "Send document checklist via WhatsApp",
        "Open hardship pathway, route to senior officer",
    ]
    with db_cursor() as cur:
        for i in range(100):
            user_id, user_name = random.choice(CITIZENS)
            channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
            event_type, tmpl = random.choice(EVENT_TYPES)
            service = random.choices(SERVICES, weights=SERVICE_WEIGHTS)[0]
            priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0]
            prev_channel = random.choice([c for c in CHANNELS if c != channel])
            sentiment = round(random.uniform(0.15, 0.45), 2)
            summary = tmpl.format(
                channel=channel, service=service, priority=priority,
                prev_channel=prev_channel, sentiment=sentiment,
                action=random.choice(actions),
            )
            created = NOW - timedelta(minutes=random.randint(1, 600))
            cur.execute(
                """
                INSERT INTO activity_events (user_id, user_name, channel, event_type, summary, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (user_id, user_name, channel, event_type, summary,
                 json.dumps({"synthetic": "true", "service": service, "priority": priority}),
                 created),
            )
    print("  ✓ inserted 100 activity events")


def main() -> None:
    print(f"Seeding Hassan omnichannel demo data at {NOW.isoformat()}")
    case_numbers = seed_cases(200)
    seed_notifications(case_numbers)
    seed_activity_events()
    print("Done.")


if __name__ == "__main__":
    main()
