-- v6: Citizen master record + identity persistence.
--
-- Until now identity was scattered across cases/activity_events/call_recordings and the
-- UAE PASS session cookie. For a real system we persist a single master record per citizen
-- the moment they authenticate with UAE PASS, so staff can browse a directory of everyone
-- who has interacted and open a 360° profile (details + conversations + cases + activity).

CREATE TABLE IF NOT EXISTS citizens (
    user_id          TEXT PRIMARY KEY,            -- Emirates ID (dashed) — the join key everywhere
    full_name_en     TEXT,
    full_name_ar     TEXT,
    emirates_id      TEXT,
    uae_pass_sub     TEXT,                          -- UAE PASS subject id
    user_type        TEXT,                          -- SOP1 / SOP2 / SOP3 (verified level)
    nationality_en   TEXT,
    gender           TEXT,
    mobile           TEXT,
    email            TEXT,
    preferred_language TEXT DEFAULT 'en',
    channels_used    JSONB NOT NULL DEFAULT '[]'::jsonb,
    verified         BOOLEAN NOT NULL DEFAULT TRUE, -- TRUE = authenticated via UAE PASS
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_citizens_last_seen ON citizens (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_citizens_name      ON citizens (full_name_en);
