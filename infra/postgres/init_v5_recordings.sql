-- v5: Voice call recordings + post-call analytics.
--
-- Every browser/voice call is recorded (audio + transcript) and analysed by the
-- Post-Call Analyst agent (agents/hassan/workers/postcall.py). This gives the demo a
-- real contact-centre feel: searchable recordings, AI summaries, sentiment trajectory,
-- first-contact-resolution scoring, and auto-created cases.

CREATE TABLE IF NOT EXISTS call_recordings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id         TEXT NOT NULL,                 -- client session id
    user_id         TEXT,
    user_name       TEXT,
    language        TEXT DEFAULT 'en',
    channel         TEXT NOT NULL DEFAULT 'voice',

    -- Audio
    audio_path      TEXT,                          -- relative path under apps/api/recordings/
    audio_mime      TEXT DEFAULT 'audio/webm',
    duration_seconds INT DEFAULT 0,

    -- Transcript: [{ "role": "agent"|"citizen", "text": "...", "t": 12 }, ...]
    transcript      JSONB NOT NULL DEFAULT '[]'::jsonb,
    turn_count      INT DEFAULT 0,

    -- Post-call analysis (filled by the analyst agent)
    summary         TEXT,
    topics          JSONB DEFAULT '[]'::jsonb,     -- ["power outage", "billing"]
    action_items    JSONB DEFAULT '[]'::jsonb,     -- ["Send technician to Marina"]
    intent          TEXT,
    service         TEXT,
    sentiment_start NUMERIC(3,2),
    sentiment_end   NUMERIC(3,2),
    sentiment_avg   NUMERIC(3,2),
    resolved        BOOLEAN DEFAULT FALSE,          -- first-contact resolution
    qa_score        INT,                            -- 0-100 service-quality score
    escalated       BOOLEAN DEFAULT FALSE,

    -- Links
    case_id         UUID REFERENCES cases(id) ON DELETE SET NULL,
    case_number     TEXT,
    correlation_id  TEXT,

    analysed        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calls_created ON call_recordings (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_user    ON call_recordings (user_id);
CREATE INDEX IF NOT EXISTS idx_calls_service ON call_recordings (service);
