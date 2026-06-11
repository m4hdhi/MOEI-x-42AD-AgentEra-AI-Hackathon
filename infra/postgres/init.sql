-- Two databases: one for Agent42 (LangGraph checkpoints + audit), one for Langfuse.
CREATE DATABASE langfuse;

-- (pgvector is the production memory story but requires the pgvector/pgvector image.
--  For local dev we use Qdrant for vectors; switch the postgres image to pgvector/pgvector:pg16
--  on the production deploy to enable the federal-friendly in-Postgres path.)
\connect hassan
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Audit trail surface. LangGraph writes checkpoints; this is the human-readable audit view.
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_id  TEXT            NOT NULL,
    user_id         TEXT            NOT NULL,
    channel         TEXT            NOT NULL,
    node            TEXT            NOT NULL,
    payload         JSONB           NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS audit_corr_idx ON audit_log (correlation_id);
CREATE INDEX IF NOT EXISTS audit_user_idx ON audit_log (user_id);
