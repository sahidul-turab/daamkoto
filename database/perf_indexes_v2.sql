-- Performance migration v2 — run once on the existing database.
--
--   psql -U postgres -d pc_comparison -f database/perf_indexes_v2.sql
--
-- Safe to re-run: all use IF NOT EXISTS / CONCURRENTLY.

-- 1. Partial btree index that matches the CTE's WHERE + ORDER BY exactly.
--    With price_bdt > 0 baked in, the planner can index-scan instead of
--    seq-scan + 2.5 MB quicksort on every request.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_prices_sorted
    ON prices (product_id, retailer_id, scraped_at DESC)
    WHERE price_bdt > 0;

-- 2. Functional index so UPPER(category) = 'RAM DESKTOP' uses an index
--    scan instead of a full table scan through all 20K product rows.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_cat_upper
    ON products (UPPER(category));

-- 3. Materialized view: pre-compute the expensive DISTINCT ON once.
--    Every search query joins against this ~15K-row view instead of
--    re-deriving current prices from 33K append-only rows.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_current_prices AS
SELECT DISTINCT ON (pr.product_id, pr.retailer_id)
    pr.product_id,
    r.name    AS retailer,
    pr.price_bdt,
    pr.in_stock,
    pr.product_url,
    pr.scraped_at
FROM prices pr
JOIN retailers r ON r.id = pr.retailer_id
WHERE pr.price_bdt > 0
ORDER BY pr.product_id, pr.retailer_id, pr.scraped_at DESC;

-- Unique index (required for CONCURRENTLY refresh + fast product_id lookups)
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_cp_unique
    ON mv_current_prices (product_id, retailer);

-- Fast filter: "current in-stock prices for product X"
CREATE INDEX IF NOT EXISTS idx_mv_cp_product
    ON mv_current_prices (product_id);

CREATE INDEX IF NOT EXISTS idx_mv_cp_instock
    ON mv_current_prices (product_id) WHERE in_stock = TRUE;
