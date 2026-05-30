-- Migration v4 — pc_bundle_only column
--
-- Adds a boolean flag to prices indicating that the retailer only sells this
-- product as part of a complete PC bundle — NOT as a standalone purchase.
-- This is independent of stock status: a product can be in_stock AND bundle-only.
--
-- Run once:
--   psql -U postgres -d pc_comparison -f database/migration_v4_pc_bundle_only.sql
--
-- Safe to re-run: all steps are idempotent.

-- 1. Add column
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'prices' AND column_name = 'pc_bundle_only'
    ) THEN
        ALTER TABLE prices ADD COLUMN pc_bundle_only BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

-- 2. Drop + recreate mv_current_prices to include pc_bundle_only.
--    Must drop dependent indexes first.
DROP INDEX  IF EXISTS idx_mv_cp_instock;
DROP INDEX  IF EXISTS idx_mv_cp_product;
DROP INDEX  IF EXISTS idx_mv_cp_unique;
DROP MATERIALIZED VIEW IF EXISTS mv_current_prices;

CREATE MATERIALIZED VIEW mv_current_prices AS
SELECT DISTINCT ON (pr.product_id, pr.retailer_id)
    pr.product_id,
    r.name            AS retailer,
    pr.price_bdt,
    pr.in_stock,
    pr.stock_status,
    pr.pc_bundle_only,
    pr.product_url,
    pr.scraped_at
FROM prices pr
JOIN retailers r ON r.id = pr.retailer_id
WHERE pr.price_bdt > 0
ORDER BY pr.product_id, pr.retailer_id, pr.scraped_at DESC;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_mv_cp_unique  ON mv_current_prices (product_id, retailer);
CREATE INDEX        idx_mv_cp_product ON mv_current_prices (product_id);
CREATE INDEX        idx_mv_cp_instock ON mv_current_prices (product_id)
    WHERE stock_status = 'in_stock';
