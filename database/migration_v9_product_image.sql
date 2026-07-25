-- Migration v9: product thumbnail images
--
-- Adds a per-listing image URL. Like product_url, an image is a per-retailer
-- attribute (each shop hosts its own product photo), so it lives on the prices
-- table and flows up through mv_current_prices into the listings JSON.
--
-- We store only the retailer's image URL (hotlinked), never the image bytes.
-- Column is nullable: every existing row stays valid with image_url = NULL, and
-- the frontend falls back to its text-only card until a re-scrape fills it in.
--
-- Apply with:
--   python scripts/apply_migration.py database/migration_v9_product_image.sql

-- 1. New column (nullable, no backfill needed).
ALTER TABLE prices ADD COLUMN IF NOT EXISTS image_url TEXT;

-- 2. Recreate mv_current_prices to carry image_url through every stage.
--    (Identical to v8 apart from the added column.)
DROP INDEX IF EXISTS idx_mv_cp_instock;
DROP INDEX IF EXISTS idx_mv_cp_product;
DROP INDEX IF EXISTS idx_mv_cp_unique;
DROP MATERIALIZED VIEW IF EXISTS mv_current_prices;

CREATE MATERIALIZED VIEW mv_current_prices AS
WITH per_listing AS (
    -- Newest observation of each individual listing URL.
    SELECT DISTINCT ON (pr.product_id, pr.retailer_id, pr.product_url)
        pr.product_id,
        pr.retailer_id,
        pr.product_url,
        pr.image_url,
        pr.price_bdt,
        pr.in_stock,
        pr.stock_status,
        pr.pc_bundle_only,
        pr.scraped_at
    FROM prices pr
    WHERE pr.price_bdt > 0
    ORDER BY pr.product_id, pr.retailer_id, pr.product_url, pr.scraped_at DESC
),
crawl AS (
    -- When each retailer was last seen crawling each category.
    SELECT p.retailer_id, pd.category, max(p.scraped_at) AS latest
    FROM prices p
    JOIN products pd ON pd.id = p.product_id
    GROUP BY p.retailer_id, pd.category
),
live AS (
    SELECT l.*
    FROM per_listing l
    JOIN products pd ON pd.id = l.product_id
    JOIN crawl   cr ON cr.retailer_id = l.retailer_id
                   AND cr.category    = pd.category
    WHERE l.scraped_at >= cr.latest - INTERVAL '2 days'
)
-- Cheapest surviving listing represents the retailer; newest breaks ties so the
-- result is stable across refreshes.
SELECT DISTINCT ON (l.product_id, l.retailer_id)
    l.product_id,
    r.name AS retailer,
    l.price_bdt,
    l.in_stock,
    l.stock_status,
    l.pc_bundle_only,
    l.product_url,
    l.image_url,
    l.scraped_at
FROM live l
JOIN retailers r ON r.id = l.retailer_id
ORDER BY l.product_id, l.retailer_id, l.price_bdt ASC, l.scraped_at DESC;

CREATE UNIQUE INDEX idx_mv_cp_unique  ON mv_current_prices (product_id, retailer);
CREATE INDEX        idx_mv_cp_product ON mv_current_prices (product_id);
CREATE INDEX        idx_mv_cp_instock ON mv_current_prices (product_id)
    WHERE stock_status = 'in_stock';

COMMENT ON MATERIALIZED VIEW mv_current_prices IS
    'Current price per (product, retailer): cheapest surviving listing from the '
    'retailer''s latest crawl of that category. Carries product_url + image_url.';
