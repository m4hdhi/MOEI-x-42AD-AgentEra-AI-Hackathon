"""Seed the scripted-demo citizen so `make smoke-demo` has a rich unified profile to show.

  uv run python scripts/seed_demo_citizen.py

Idempotent — upserts (never duplicates). Re-run as often as you like; it always lands the
same fixed state:

  Citizen   DEMO-001 · Ahmed Al Mansouri · +971501234567 · preferred channel WhatsApp · VIP Silver
  Case 1    resolved Housing Maintenance case from ~3 months ago   (channel: whatsapp)
  Case 2    open Vehicle Registration renewal from last week        (channel: web)
  + matching cross-channel interaction rows so the 360° profile shows WhatsApp ⇄ Web history.

The Customer ID (DEMO-001) is the single cross-channel key — the same value the demo posts as
`user_id` on every channel, which is what lets one conversation span WhatsApp / web / mobile
without ever asking Ahmed to identify himself again.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import the API's DB helper (same pattern as scripts/seed_omnichannel.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.core.db import db_cursor  # type: ignore[import-not-found]  # noqa: E402

NOW = datetime.now(timezone.utc)

CUSTOMER_ID = "DEMO-001"
NAME_EN = "Ahmed Al Mansouri"
NAME_AR = "أحمد المنصوري"
PHONE = "+971501234567"

# ── The two past cases (fixed numbers so re-runs upsert, not insert) ────────────────────
HOUSING_CASE = "MOEI-CASE-DEMO-0001"  # resolved, ~3 months ago, WhatsApp
VEHICLE_CASE = "MOEI-CASE-DEMO-0002"  # open, last week, web

_housing_opened = NOW - timedelta(days=92)
_housing_closed = NOW - timedelta(days=89)
_vehicle_opened = NOW - timedelta(days=7)


def _upsert_citizen(cur) -> None:
    cur.execute(
        """
        INSERT INTO citizens (
            user_id, customer_id, full_name_en, full_name_ar, mobile, email,
            preferred_language, preferred_channel, vip_tier, verified, user_type,
            emirate, customer_type, account_status, nationality_en,
            channels_used, registered_since, last_interaction_date, last_seen_at,
            total_interactions, whatsapp_interactions, web_sessions,
            open_cases, resolved_cases, last_service
        ) VALUES (
            %(uid)s, %(uid)s, %(name_en)s, %(name_ar)s, %(phone)s, %(email)s,
            'en', 'whatsapp', 'Silver', TRUE, 'SOP2',
            'Abu Dhabi', 'Residential', 'Active', 'UAE',
            %(channels)s::jsonb, %(registered)s, %(last_date)s, NOW(),
            2, 1, 1,
            1, 1, 'Vehicle Registration'
        )
        ON CONFLICT (user_id) DO UPDATE SET
            customer_id          = EXCLUDED.customer_id,
            full_name_en         = EXCLUDED.full_name_en,
            full_name_ar         = EXCLUDED.full_name_ar,
            mobile               = EXCLUDED.mobile,
            email                = EXCLUDED.email,
            preferred_channel    = EXCLUDED.preferred_channel,
            vip_tier             = EXCLUDED.vip_tier,
            verified             = EXCLUDED.verified,
            emirate              = EXCLUDED.emirate,
            customer_type        = EXCLUDED.customer_type,
            account_status       = EXCLUDED.account_status,
            channels_used        = EXCLUDED.channels_used,
            total_interactions   = EXCLUDED.total_interactions,
            whatsapp_interactions= EXCLUDED.whatsapp_interactions,
            web_sessions         = EXCLUDED.web_sessions,
            open_cases           = EXCLUDED.open_cases,
            resolved_cases       = EXCLUDED.resolved_cases,
            last_service         = EXCLUDED.last_service,
            last_seen_at         = NOW()
        """,
        {
            "uid": CUSTOMER_ID,
            "name_en": NAME_EN,
            "name_ar": NAME_AR,
            "phone": PHONE,
            "email": "ahmed.almansouri@example.ae",
            "channels": json.dumps(["whatsapp", "web"]),
            "registered": (NOW - timedelta(days=720)).date(),
            "last_date": _vehicle_opened.date(),
        },
    )


def _upsert_case(cur, **f) -> None:
    """Upsert one case by its (unique) case_number."""
    cur.execute(
        """
        INSERT INTO cases (
            case_number, user_id, customer_id, user_name, channel, intent, service,
            service_category, sub_service, title, description, priority, priority_tier,
            status, resolution_type, sentiment, assigned_team,
            sla_target_hrs, sla_met, sla_deadline, resolution_time_hrs,
            created_at, date_opened, updated_at, resolved_at, date_closed
        ) VALUES (
            %(case_number)s, %(uid)s, %(uid)s, %(name)s, %(channel)s, %(intent)s, %(service)s,
            %(service_category)s, %(sub_service)s, %(title)s, %(description)s,
            %(priority)s, %(priority_tier)s,
            %(status)s, %(resolution_type)s, %(sentiment)s, %(assigned_team)s,
            %(sla_target_hrs)s, %(sla_met)s, %(sla_deadline)s, %(resolution_time_hrs)s,
            %(created_at)s, %(created_at)s, NOW(), %(resolved_at)s, %(date_closed)s
        )
        ON CONFLICT (case_number) DO UPDATE SET
            user_id          = EXCLUDED.user_id,
            customer_id      = EXCLUDED.customer_id,
            user_name        = EXCLUDED.user_name,
            channel          = EXCLUDED.channel,
            service          = EXCLUDED.service,
            service_category = EXCLUDED.service_category,
            sub_service      = EXCLUDED.sub_service,
            title            = EXCLUDED.title,
            description      = EXCLUDED.description,
            priority         = EXCLUDED.priority,
            priority_tier    = EXCLUDED.priority_tier,
            status           = EXCLUDED.status,
            resolution_type  = EXCLUDED.resolution_type,
            sentiment        = EXCLUDED.sentiment,
            assigned_team    = EXCLUDED.assigned_team,
            sla_target_hrs   = EXCLUDED.sla_target_hrs,
            sla_met          = EXCLUDED.sla_met,
            sla_deadline     = EXCLUDED.sla_deadline,
            resolution_time_hrs = EXCLUDED.resolution_time_hrs,
            created_at       = EXCLUDED.created_at,
            date_opened      = EXCLUDED.date_opened,
            updated_at       = NOW(),
            resolved_at      = EXCLUDED.resolved_at,
            date_closed      = EXCLUDED.date_closed
        """,
        f,
    )


def _upsert_interaction(cur, interaction_id: str, **f) -> None:
    """Upsert one cross-channel interaction row (delete-then-insert keyed by interaction_id)."""
    cur.execute("DELETE FROM interactions WHERE interaction_id = %s", (interaction_id,))
    cur.execute(
        """
        INSERT INTO interactions (
            interaction_id, customer_id, customer_name_en, channel, occurred_at, language,
            emirate, intent, service_category, sub_service, message_sample,
            sentiment_label, sentiment_score, escalated, resolution_status, case_id
        ) VALUES (
            %(interaction_id)s, %(uid)s, %(name)s, %(channel)s, %(occurred_at)s, %(language)s,
            'Abu Dhabi', %(intent)s, %(service_category)s, %(sub_service)s, %(message_sample)s,
            %(sentiment_label)s, %(sentiment_score)s, %(escalated)s,
            %(resolution_status)s, %(case_id)s
        )
        """,
        {"interaction_id": interaction_id, "uid": CUSTOMER_ID, "name": NAME_EN, **f},
    )


def main() -> None:
    with db_cursor() as cur:
        _upsert_citizen(cur)

        _upsert_case(
            cur,
            case_number=HOUSING_CASE,
            uid=CUSTOMER_ID,
            name=NAME_EN,
            channel="whatsapp",
            intent="service_request",
            service="housing",
            service_category="Housing Maintenance",
            sub_service="Plumbing / water leak repair",
            title="Housing maintenance — water leak under kitchen sink",
            description="Reported a water leak under the kitchen sink in his Sheikh Zayed "
            "Housing Programme unit. Field technician dispatched and repair completed.",
            priority="medium",
            priority_tier="normal",
            status="resolved",
            resolution_type="agent_resolved",
            sentiment=0.82,
            assigned_team="Housing Maintenance — Abu Dhabi",
            sla_target_hrs=72.0,
            sla_met="Yes",
            sla_deadline=_housing_opened + timedelta(hours=72),
            resolution_time_hrs=round(
                (_housing_closed - _housing_opened).total_seconds() / 3600, 2
            ),
            created_at=_housing_opened,
            resolved_at=_housing_closed,
            date_closed=_housing_closed,
        )

        _upsert_case(
            cur,
            case_number=VEHICLE_CASE,
            uid=CUSTOMER_ID,
            name=NAME_EN,
            channel="web",
            intent="service_request",
            service="transport",
            service_category="Vehicle Registration",
            sub_service="Registration renewal",
            title="Vehicle registration renewal — pending payment",
            description="Started a federal vehicle registration renewal online; awaiting "
            "fee payment to complete.",
            priority="medium",
            priority_tier="normal",
            status="open",
            resolution_type="pending",
            sentiment=0.66,
            assigned_team="Vehicle Services",
            sla_target_hrs=120.0,
            sla_met="Pending",
            sla_deadline=_vehicle_opened + timedelta(hours=120),
            resolution_time_hrs=None,
            created_at=_vehicle_opened,
            resolved_at=None,
            date_closed=None,
        )

        _upsert_interaction(
            cur,
            "DEMO-IX-0001",
            channel="whatsapp",
            occurred_at=_housing_opened,
            language="ar",
            intent="service_request",
            service_category="Housing Maintenance",
            sub_service="Plumbing / water leak repair",
            message_sample="يوجد تسريب مياه تحت حوض المطبخ في وحدتي السكنية",
            sentiment_label="neutral",
            sentiment_score=0.55,
            escalated=False,
            resolution_status="resolved",
            case_id=HOUSING_CASE,
        )
        _upsert_interaction(
            cur,
            "DEMO-IX-0002",
            channel="web",
            occurred_at=_vehicle_opened,
            language="en",
            intent="service_request",
            service_category="Vehicle Registration",
            sub_service="Registration renewal",
            message_sample="I need to renew my vehicle registration",
            sentiment_label="positive",
            sentiment_score=0.66,
            escalated=False,
            resolution_status="open",
            case_id=VEHICLE_CASE,
        )

    print("✅ Seeded demo citizen:")
    print(f"   Customer ID   : {CUSTOMER_ID}")
    print(f"   Name          : {NAME_EN} ({NAME_AR})")
    print(f"   Phone         : {PHONE}  ·  preferred channel: whatsapp  ·  VIP: Silver")
    print(
        f"   Past cases    : {HOUSING_CASE} (housing, resolved) · {VEHICLE_CASE} (transport, open)"
    )
    print("   Interactions  : 2 (whatsapp + web) — cross-channel history ready.")
    print("\nRe-runnable: this upserts, so running it again is a no-op (no duplicates).")


if __name__ == "__main__":
    main()
