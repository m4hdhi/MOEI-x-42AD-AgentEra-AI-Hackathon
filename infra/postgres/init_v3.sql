-- Agent42 v3: case feedback (CSAT + CES + free-text)
\connect hassan

CREATE TABLE IF NOT EXISTS case_feedback (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id         UUID            REFERENCES cases(id) ON DELETE SET NULL,
    case_number     TEXT,
    user_id         TEXT,
    csat            INT             CHECK (csat BETWEEN 1 AND 5),    -- 1=very dissatisfied .. 5=very satisfied
    ces             INT             CHECK (ces BETWEEN 1 AND 5),     -- 1=very easy .. 5=very hard (CES is reverse-coded by convention)
    comment         TEXT,
    submitted_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS feedback_case_idx ON case_feedback (case_id);
CREATE INDEX IF NOT EXISTS feedback_submitted_idx ON case_feedback (submitted_at DESC);
