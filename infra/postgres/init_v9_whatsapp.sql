-- v9: WhatsApp identity table for Meta Cloud API channel.
--
-- Maps each WhatsApp sender (canonical form: "whatsapp:+<digits>") to a stable user_id
-- (Emirates ID or synthetic demo ID) so the supervisor maintains cross-channel continuity.
-- Auto-onboarding inserts new guests; the route updates last_seen_at on return visits.
--
-- Apply:  PGPASSWORD=hassan_dev psql -h 127.0.0.1 -U hassan -d hassan -f infra/postgres/init_v9_whatsapp.sql

\connect hassan

CREATE TABLE IF NOT EXISTS whatsapp_identities (
    wa_number    TEXT PRIMARY KEY,                       -- e.g. "whatsapp:+971541841533"
    user_id      TEXT NOT NULL,                          -- Emirates ID or synthetic demo ID
    display_name TEXT,                                   -- WhatsApp profile name (≤80 chars)
    is_demo_guest BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reverse-lookup: notifications dispatcher resolves user_id → wa_number.
CREATE INDEX IF NOT EXISTS idx_whatsapp_identities_user_id ON whatsapp_identities (user_id);
