-- Agent42 v2 schema additions: CRM cases + notifications + activity events.
-- Idempotent; apply with:  docker exec -i hassan-postgres psql -U hassan -d hassan < infra/postgres/init_v2.sql

\connect hassan

-- CRM cases — created by the case_router worker on every supervisor turn that needs tracking
CREATE TABLE IF NOT EXISTS cases (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_number     TEXT            UNIQUE NOT NULL,             -- human-readable MOEI-CASE-2026-00042
    user_id         TEXT            NOT NULL,                    -- Emirates ID
    user_name       TEXT,
    channel         TEXT            NOT NULL,                    -- web | whatsapp | voice | mobile
    intent          TEXT            NOT NULL,                    -- inquiry | complaint | suggestion | appreciation | service_request | status_check
    service         TEXT            NOT NULL,                    -- housing | energy | maritime | transport | infrastructure | general
    title           TEXT            NOT NULL,
    description     TEXT,
    priority        TEXT            NOT NULL DEFAULT 'medium',   -- low | medium | high | critical
    status          TEXT            NOT NULL DEFAULT 'open',     -- open | in_progress | escalated | resolved | closed
    sentiment       NUMERIC(3,2),                                -- 0.0..1.0  (0=very negative, 1=very positive)
    assigned_to     TEXT,                                        -- agent username (or 'auto')
    correlation_id  TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS cases_user_idx ON cases (user_id);
CREATE INDEX IF NOT EXISTS cases_status_idx ON cases (status);
CREATE INDEX IF NOT EXISTS cases_created_idx ON cases (created_at DESC);

-- Outbound notifications — scheduled follow-ups, status updates, satisfaction surveys
CREATE TABLE IF NOT EXISTS notifications (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         TEXT            NOT NULL,
    case_id         UUID            REFERENCES cases(id) ON DELETE SET NULL,
    channel         TEXT            NOT NULL,                    -- whatsapp | sms | email | push
    template        TEXT            NOT NULL,                    -- 'status_update' | 'doc_reminder' | 'csat_survey' | 'proactive_tip'
    payload         JSONB           NOT NULL,
    scheduled_at    TIMESTAMPTZ     NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          TEXT            NOT NULL DEFAULT 'scheduled', -- scheduled | sent | failed
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications (user_id);
CREATE INDEX IF NOT EXISTS notifications_status_idx ON notifications (status, scheduled_at);

-- Omnichannel activity stream — every meaningful event, for the live dashboard ticker
CREATE TABLE IF NOT EXISTS activity_events (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         TEXT,
    user_name       TEXT,
    channel         TEXT,
    event_type      TEXT            NOT NULL,                    -- turn | channel_switch | sentiment_change | escalation | case_created | nba_offered
    summary         TEXT            NOT NULL,
    payload         JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS activity_created_idx ON activity_events (created_at DESC);
