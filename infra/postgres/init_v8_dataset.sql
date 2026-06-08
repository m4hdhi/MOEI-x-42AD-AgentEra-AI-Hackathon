-- v8: Load the official MOEI Omnichannel hackathon dataset as the source of truth.
--
-- The five-sheet dataset (CRM profiles, service cases, WhatsApp / Voice / Web logs) is linked
-- by Customer ID — exactly the cross-channel-memory requirement in the challenge FAQ (Q8/Q10/Q20).
-- We extend the existing citizens + cases tables with the dataset's richer fields and add a single
-- unified `interactions` log so any channel can retrieve the full history by Customer ID or phone.
--
-- Apply:  docker exec -i hassan-postgres psql -U hassan -d hassan < infra/postgres/init_v8_dataset.sql
-- Load:   uv run python scripts/import_dataset.py

\connect hassan

-- ── Unified CRM profile fields (challenge Q9) ───────────────────────────────
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS customer_id          TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS emirate              TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS area                 TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS nationality          TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS customer_type        TEXT;   -- Residential | Commercial | Industrial | Government
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS account_status       TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS registered_since     DATE;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS last_interaction_date DATE;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS total_interactions   INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS whatsapp_interactions INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS voice_interactions   INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS web_sessions         INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS open_cases           INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS resolved_cases       INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS escalated_cases      INT DEFAULT 0;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS preferred_channel    TEXT;   -- web | whatsapp | voice | mobile
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS avg_csat             NUMERIC(3,2);
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS avg_nps              NUMERIC(4,1);
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS lifetime_sentiment   NUMERIC(4,3);
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS risk_flag            TEXT;   -- Repeat Escalator | High Churn Risk | Late Payer
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS vip_tier             TEXT;   -- Standard | Silver | Gold | Platinum
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS smart_meter          BOOLEAN;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS renewable_customer   BOOLEAN;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS num_properties       INT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS last_service         TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS crm_agent            TEXT;
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS tags                 TEXT;

CREATE INDEX IF NOT EXISTS idx_citizens_customer_id ON citizens (customer_id);
CREATE INDEX IF NOT EXISTS idx_citizens_mobile      ON citizens (mobile);
CREATE INDEX IF NOT EXISTS idx_citizens_vip         ON citizens (vip_tier);
CREATE INDEX IF NOT EXISTS idx_citizens_risk        ON citizens (risk_flag);

-- ── Richer case fields from the Service Requests & Cases sheet ───────────────
ALTER TABLE cases ADD COLUMN IF NOT EXISTS customer_id            TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS escalated              BOOLEAN DEFAULT FALSE;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS service_category       TEXT;   -- original label
ALTER TABLE cases ADD COLUMN IF NOT EXISTS sub_service            TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_type              TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS assigned_team          TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS channels_used          JSONB;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS cross_channel_flag     BOOLEAN DEFAULT FALSE;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS escalation_reason      TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS supervisor_involved    TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS ai_auto_classified     BOOLEAN;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS ai_suggested_resolution TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS agent_override         BOOLEAN;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS sla_target_hrs         NUMERIC(6,1);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS sla_met                TEXT;    -- Yes | No | Pending
ALTER TABLE cases ADD COLUMN IF NOT EXISTS resolution_time_hrs    NUMERIC(8,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS reopen_count           INT DEFAULT 0;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS root_cause             TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS linked_case_id         TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS date_opened            TIMESTAMPTZ;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS date_closed            TIMESTAMPTZ;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS description_ar         TEXT;
ALTER TABLE cases ADD COLUMN IF NOT EXISTS csat                   INT;

CREATE INDEX IF NOT EXISTS idx_cases_customer_id ON cases (customer_id);
CREATE INDEX IF NOT EXISTS idx_cases_sla_met     ON cases (sla_met);
CREATE INDEX IF NOT EXISTS idx_cases_reopen      ON cases (reopen_count);

-- ── Unified cross-channel interaction log (WhatsApp + Voice + Web/App) ───────
-- This is the heart of cross-channel memory: one row per session/call, all keyed by Customer ID,
-- so retrieving "everything this customer has ever done, on any channel" is a single indexed query.
CREATE TABLE IF NOT EXISTS interactions (
    id                BIGSERIAL    PRIMARY KEY,
    interaction_id    TEXT,                         -- Session ID / Call ID
    customer_id       TEXT         NOT NULL,
    customer_name_en  TEXT,
    customer_name_ar  TEXT,
    channel           TEXT         NOT NULL,        -- whatsapp | voice | web | mobile
    occurred_at       TIMESTAMPTZ,
    language          TEXT,
    emirate           TEXT,
    intent            TEXT,
    service_category  TEXT,
    sub_service       TEXT,
    message_sample    TEXT,
    sentiment_label   TEXT,
    sentiment_score   NUMERIC(4,3),
    csat              INT,
    escalated         BOOLEAN DEFAULT FALSE,
    resolution_status TEXT,
    case_id           TEXT,
    raw               JSONB,                        -- full original row, lossless
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_interactions_customer ON interactions (customer_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_channel  ON interactions (channel);
CREATE INDEX IF NOT EXISTS idx_interactions_case     ON interactions (case_id);
