-- Scraper run history — tracks every pipeline execution with status + stats.
-- Run once manually: psql -d pc_comparison -f database/migration_v5_scraper_runs.sql

CREATE TABLE IF NOT EXISTS scraper_runs (
    id             SERIAL PRIMARY KEY,
    category       TEXT        NOT NULL,
    retailers      TEXT[]      NOT NULL DEFAULT '{}',
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at    TIMESTAMPTZ,
    status         TEXT        NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    products_count INTEGER     DEFAULT 0,
    prices_count   INTEGER     DEFAULT 0,
    error_message  TEXT
);

-- Most queries are "show recent runs" — this makes them instant.
CREATE INDEX IF NOT EXISTS idx_scraper_runs_started
    ON scraper_runs (started_at DESC);

-- Fast lookup of in-flight runs (used by the 409 concurrency guard).
CREATE INDEX IF NOT EXISTS idx_scraper_runs_running
    ON scraper_runs (category) WHERE status = 'RUNNING';
