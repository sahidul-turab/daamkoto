-- Migration v7: pick the CHEAPEST listing when a retailer has several
--
-- Problem
-- -------
-- A retailer sometimes sells one product under more than one URL at different
-- prices. Skyland lists the same AITC Kingsman DDR5 kit twice:
--
--   70,200  /aitc-kingsman-vertex-rgb-16gb-ddr5-ram
--   17,500  /aitc-kingsman-vertex-rgb-ddr5-16gb-7200bus-cl34-ram
--
-- The matcher correctly folds both into one canonical product. But the old view
--
--   SELECT DISTINCT ON (product_id, retailer_id) ...
--   ORDER BY product_id, retailer_id, scraped_at DESC
--
-- kept only the most recently scraped row, so whichever listing happened to be
-- scraped microseconds later became that retailer's price. The displayed price
-- flipped between 17,500 and 70,200 from one scrape to the next, which also fed
-- a fake 75% "price drop" into the deals feed.
--
-- Fix
-- ---
-- Two stages: take the newest row per *listing*, then keep the cheapest listing
-- per (product, retailer). Deterministic, and it matches what the site is for -
-- showing the cheapest place to buy.
--
-- Apply with:
--   python scripts/apply_migration.py database/migration_v7_cheapest_listing.sql

DROP INDEX IF EXISTS idx_mv_cp_instock;
DROP INDEX IF EXISTS idx_mv_cp_product;
DROP INDEX IF EXISTS idx_mv_cp_unique;
DROP MATERIALIZED VIEW IF EXISTS mv_current_prices;

CREATE MATERIALIZED VIEW mv_current_prices AS
WITH per_listing AS (
    -- Newest observation of each individual listing.
    SELECT DISTINCT ON (pr.product_id, pr.retailer_id, pr.product_url)
        pr.product_id,
        pr.retailer_id,
        pr.product_url,
        pr.price_bdt,
        pr.in_stock,
        pr.stock_status,
        pr.pc_bundle_only,
        pr.scraped_at
    FROM prices pr
    WHERE pr.price_bdt > 0
    ORDER BY pr.product_id, pr.retailer_id, pr.product_url, pr.scraped_at DESC
)
-- Of those, the cheapest listing represents the retailer. Ties break on the
-- more recent scrape so the result is stable across refreshes.
SELECT DISTINCT ON (l.product_id, l.retailer_id)
    l.product_id,
    r.name AS retailer,
    l.price_bdt,
    l.in_stock,
    l.stock_status,
    l.pc_bundle_only,
    l.product_url,
    l.scraped_at
FROM per_listing l
JOIN retailers r ON r.id = l.retailer_id
ORDER BY l.product_id, l.retailer_id, l.price_bdt ASC, l.scraped_at DESC;

-- Unique index is required for REFRESH ... CONCURRENTLY.
CREATE UNIQUE INDEX idx_mv_cp_unique  ON mv_current_prices (product_id, retailer);
CREATE INDEX        idx_mv_cp_product ON mv_current_prices (product_id);
CREATE INDEX        idx_mv_cp_instock ON mv_current_prices (product_id)
    WHERE stock_status = 'in_stock';

COMMENT ON MATERIALIZED VIEW mv_current_prices IS
    'Current price per (product, retailer): newest row per listing URL, then the '
    'cheapest listing. Replaces last-scraped-wins, which was non-deterministic '
    'when a retailer had duplicate listings for one product.';
