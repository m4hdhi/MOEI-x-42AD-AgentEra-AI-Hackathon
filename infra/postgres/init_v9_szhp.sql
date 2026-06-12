-- v9: Sheikh Zayed Housing Programme — Loan Arrears Rescheduling (officer-grade AI agent).
--
-- Two tables:
--   szhp_loans       — the beneficiary loan + arrears records the agent retrieves automatically
--                      (loaded from the real SZHP rescheduling dataset, 2023–2025).
--   szhp_assessments — the agent's officer-grade decisions: structured recommendation, policy
--                      compliance flags, confidence, reasoning, and audit payload.
--
-- Apply:  docker exec -i hassan-postgres psql -U hassan -d hassan < infra/postgres/init_v9_szhp.sql
-- Load:   uv run python scripts/import_szhp.py

\connect hassan

CREATE TABLE IF NOT EXISTS szhp_loans (
    id                        BIGSERIAL PRIMARY KEY,
    source_year               INT,
    application_id            TEXT,
    agreement_id              TEXT,
    edb_loan_id               TEXT,
    edb_customer_id           TEXT,
    applicant                 TEXT,
    user_id                   TEXT,            -- Emirates ID link (set for demo personas)
    request_type              TEXT,
    approved_request_type     TEXT,            -- UPDATE_INSTALLMENT | TRANSFER_ARREARS (historical outcome)
    current_salary            NUMERIC(14,2),
    over_due_amt              NUMERIC(14,2),   -- arrears
    over_due_months           NUMERIC(8,1),
    deduct_from_salary        NUMERIC(14,2),
    current_emi_amt           NUMERIC(14,2),
    new_emi_amt               NUMERIC(14,2),
    new_emi_applicable_months NUMERIC(8,1),
    original_term_months      INT DEFAULT 300, -- approved repayment period (Rule 2 ceiling)
    remaining_term_months     INT,
    family_size               INT,
    dependents                INT,
    has_active_request        BOOLEAN DEFAULT FALSE,
    created_date              TEXT,
    status                    TEXT,
    approved_date             TEXT,
    created_by                TEXT,
    justifications            TEXT,
    remarks                   TEXT
);
CREATE INDEX IF NOT EXISTS idx_szhp_loans_customer ON szhp_loans (edb_customer_id);
CREATE INDEX IF NOT EXISTS idx_szhp_loans_user     ON szhp_loans (user_id);
CREATE INDEX IF NOT EXISTS idx_szhp_loans_appid    ON szhp_loans (application_id);

CREATE TABLE IF NOT EXISTS szhp_assessments (
    id                    BIGSERIAL PRIMARY KEY,
    reference             TEXT UNIQUE,          -- SZHP-RS-2026-00001
    application_id        TEXT,
    user_id               TEXT,
    customer_id           TEXT,
    applicant             TEXT,
    -- decision
    recommendation        TEXT,                 -- approve | request_documents | refer_to_officer | reject
    approved_request_type TEXT,                 -- UPDATE_INSTALLMENT | TRANSFER_ARREARS | MAINTAIN
    confidence            NUMERIC(4,3),
    -- analysis snapshot
    current_salary        NUMERIC(14,2),
    arrears               NUMERIC(14,2),
    current_emi           NUMERIC(14,2),
    proposed_emi          NUMERIC(14,2),
    proposed_term_months  INT,
    deduction_ratio       NUMERIC(5,4),         -- proposed EMI / salary
    rule_20_pass          BOOLEAN,
    rule_period_pass      BOOLEAN,
    rule_active_pass      BOOLEAN,
    -- governance
    status                TEXT DEFAULT 'in_progress', -- in_progress | approved | rejected | request_documents | human_review
    reasoning             TEXT,
    officer_action        TEXT,                 -- approve | override | refer (set by human)
    officer_note          TEXT,
    payload               JSONB,                -- full structured assessment
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at            TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_szhp_assess_user   ON szhp_assessments (user_id);
CREATE INDEX IF NOT EXISTS idx_szhp_assess_status ON szhp_assessments (status, created_at DESC);
