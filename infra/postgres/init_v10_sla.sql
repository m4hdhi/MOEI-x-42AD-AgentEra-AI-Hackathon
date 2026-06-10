-- v10: 3-tier SLA engine + self-service auto-close on the cases table.
--
-- Feature A — priority tiers drive an SLA deadline computed at case-open time:
--   urgent → NOW() + 1 day, medium → NOW() + 3 days, normal → NOW() + 5 days.
-- Feature B — resolution_type records HOW a case was closed, so the dashboard can
--   distinguish citizen self-service (FAQ/knowledge answers) from agent/escalation work.
--
-- Idempotent. Apply:  PGPASSWORD=hassan_dev psql -h 127.0.0.1 -U hassan -d hassan -f infra/postgres/init_v10_sla.sql
-- (named v10 because init_v9_whatsapp.sql already claims the v9 slot.)

\connect hassan

-- Feature A — 3-tier SLA
ALTER TABLE cases ADD COLUMN IF NOT EXISTS priority_tier VARCHAR(10)  NOT NULL DEFAULT 'normal';  -- urgent | medium | normal
ALTER TABLE cases ADD COLUMN IF NOT EXISTS sla_deadline  TIMESTAMPTZ;                              -- NOW() + tier interval, set at open

-- Feature B — self-service auto-close
ALTER TABLE cases ADD COLUMN IF NOT EXISTS resolution_type VARCHAR(20) NOT NULL DEFAULT 'pending'; -- self_served | agent_resolved | escalated | pending

-- Dashboard queries: "what's breaching soon?" and "how was this closed?"
CREATE INDEX IF NOT EXISTS cases_sla_deadline_idx   ON cases (sla_deadline);
CREATE INDEX IF NOT EXISTS cases_resolution_type_idx ON cases (resolution_type);
