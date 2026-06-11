-- v10: Global Country Intelligence — a strategic advisor for MOEI leadership.
--
-- countries        — decision-ready country profiles (economy, energy, infrastructure,
--                    sustainability, competitiveness, projects, and UAE bilateral cooperation).
-- country_briefs   — AI-generated executive briefings (summary, talking points, opportunities,
--                    risks, recommended actions) produced for a specific meeting context.
--
-- Apply:  docker exec -i hassan-postgres psql -U hassan -d hassan < infra/postgres/init_v10_intel.sql
-- Load:   uv run python scripts/import_intel.py

\connect hassan

CREATE TABLE IF NOT EXISTS countries (
    code                TEXT PRIMARY KEY,
    flag                TEXT,
    name                TEXT NOT NULL,
    name_ar             TEXT,
    region              TEXT,
    capital             TEXT,
    population_m        NUMERIC(10,1),
    gdp_usd_b           NUMERIC(12,1),
    gdp_per_capita_usd  NUMERIC(12,1),
    gdp_growth_pct      NUMERIC(6,2),
    uae_trade_usd_b     NUMERIC(10,2),
    profile             JSONB NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_countries_region ON countries (region);

CREATE TABLE IF NOT EXISTS country_briefs (
    id                  BIGSERIAL PRIMARY KEY,
    reference           TEXT UNIQUE,
    code                TEXT REFERENCES countries(code) ON DELETE CASCADE,
    country_name        TEXT,
    meeting_context     TEXT,
    language            TEXT DEFAULT 'en',
    summary             TEXT,
    talking_points      JSONB,
    opportunities       JSONB,
    risks               JSONB,
    recommended_actions JSONB,
    questions           JSONB,
    generated_by        TEXT,          -- 'ai' | 'fallback'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_country_briefs_code ON country_briefs (code, created_at DESC);
