-- Customer document registry.
-- Files are stored outside Postgres; this table keeps the customer link, extracted metadata,
-- and private storage pointer for later officer/customer access.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS customer_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    case_number     TEXT,
    document_type   TEXT NOT NULL DEFAULT 'other',
    status          TEXT NOT NULL DEFAULT 'uploaded',
    original_name   TEXT,
    content_type    TEXT,
    file_size       BIGINT,
    storage_path    TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    confidence      NUMERIC(4,2),
    extracted_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    signals         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_documents_user_created
    ON customer_documents (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_customer_documents_case
    ON customer_documents (case_number)
    WHERE case_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_customer_documents_type
    ON customer_documents (document_type);
