-- Migration v8: a listing stops counting once the retailer stops selling it
--
-- Problem
-- -------
-- Nothing ever expired a listing. When UltraTech stopped selling a ZOTAC RTX
-- 5060 at 44,999 in May, that row stayed "current" forever. Prices drift up, so
-- dead listings are systematically the cheapest ones - and they won the headline
-- "FROM" price on 41% of GPUs, showing visitors a price nobody can buy at,
-- stamped "Updated 56d ago".
--
-- Rule
-- ----
-- A listing is current only if it was seen in that retailer's most recent crawl
-- of that category (2-day grace for clock skew and split runs).
--
-- The comparison is per (retailer, category), never global. If a retailer has
-- not been crawled for weeks, its own latest crawl is also weeks old, so its
-- listings stay - a broken scraper must not erase a shop from the site. Only a
-- retailer we *did* crawl can have its missing products treated as delisted.
--
-- Supersedes v7, and keeps v7's rule that the cheapest listing represents a
-- retailer when it has several URLs for one product.
--
-- Apply with:
--   python scripts/apply_migration.py database/migration_v8_expire_dead_listings.sql

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
    l.scraped_at
FROM live l
JOIN retailers r ON r.id = l.retailer_id
ORDER BY l.product_id, l.retailer_id, l.price_bdt ASC, l.scraped_at DESC;

CREATE UNIQUE INDEX idx_mv_cp_unique  ON mv_current_prices (product_id, retailer);
CREATE INDEX        idx_mv_cp_product ON mv_current_prices (product_id);
CREATE INDEX        idx_mv_cp_instock ON mv_current_prices (product_id)
    WHERE stock_status = 'in_stock';

COMMENT ON MATERIALIZED VIEW mv_current_prices IS
    'Current price per (product, retailer). A listing counts only if seen in '
    'that retailer''s latest crawl of the category, so delisted products stop '
    'showing a price nobody can buy at. Cheapest surviving listing wins when a '
    'retailer has duplicate URLs for one product.';
