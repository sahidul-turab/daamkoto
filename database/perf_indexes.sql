-- Performance index migration — run once on an existing database.
--
--   psql -U postgres -d pc_comparison -f database/perf_indexes.sql
--
-- Safe to re-run: all statements use IF NOT EXISTS / CONCURRENTLY.
-- CONCURRENTLY builds the index without locking the table, so the app
-- can keep serving requests while this runs.

-- 1. Fix the DISTINCT ON index — the CTE resolves current price per
--    (product_id, retailer_id), so the sort key must include retailer_id.
--    The old (product_id, scraped_at DESC) index can't satisfy this.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_prices_current
    ON prices (product_id, retailer_id, scraped_at DESC);

-- 2. Trigram extension + indexes for fast ILIKE '%...%' full-text search.
--    Without these, every search token forces a sequential scan.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_name_trgm
    ON products USING GIN (name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_brand_trgm
    ON products USING GIN (brand gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_model_trgm
    ON products USING GIN (model_number gin_trgm_ops);
