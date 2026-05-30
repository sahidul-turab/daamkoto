-- Migration v3 — stock_status column
--
-- Adds a richer stock status field to the prices table, capturing:
--   in_stock   — product is available to buy standalone
--   out_of_stock — currently unavailable
--   upcoming   — not yet released / pre-order (e.g. Ryans product_is_upcoming=1)
--   bundle_only — only available bundled with a complete PC (StarTech "Only With PC Build")
--
-- Run once:
--   psql -U postgres -d pc_comparison -f database/migration_v3_stock_status.sql
--
-- Safe to re-run: uses IF NOT EXISTS / IF EXISTS guards.

-- 1. Add column (idempotent via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='prices' AND column_name='stock_status'
    ) THEN
        ALTER TABLE prices ADD COLUMN stock_status TEXT NOT NULL DEFAULT 'in_stock';
    END IF;
END $$;

-- 2. Backfill existing rows from the in_stock boolean
UPDATE prices
SET    stock_status = CASE WHEN in_stock THEN 'in_stock' ELSE 'out_of_stock' END
WHERE  stock_status = 'in_stock' AND NOT in_stock;  -- only fix rows that are actually out_of_stock

-- 3. Add a check constraint (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name='prices' AND constraint_name='chk_prices_stock_status'
    ) THEN
        ALTER TABLE prices
        ADD CONSTRAINT chk_prices_stock_status
        CHECK (stock_status IN ('in_stock', 'out_of_stock', 'upcoming', 'bundle_only'));
    END IF;
END $$;

-- 4. Drop and recreate mv_current_prices to include stock_status.
--    Must drop indexes first (they depend on the view).
DROP INDEX  IF EXISTS idx_mv_cp_instock;
DROP INDEX  IF EXISTS idx_mv_cp_product;
DROP INDEX  IF EXISTS idx_mv_cp_unique;
DROP MATERIALIZED VIEW IF EXISTS mv_current_prices;

CREATE MATERIALIZED VIEW mv_current_prices AS
SELECT DISTINCT ON (pr.product_id, pr.retailer_id)
    pr.product_id,
    r.name        AS retailer,
    pr.price_bdt,
    pr.in_stock,
    pr.stock_status,
    pr.product_url,
    pr.scraped_at
FROM prices pr
JOIN retailers r ON r.id = pr.retailer_id
WHERE pr.price_bdt > 0
ORDER BY pr.product_id, pr.retailer_id, pr.scraped_at DESC;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_mv_cp_unique  ON mv_current_prices (product_id, retailer);
CREATE INDEX        idx_mv_cp_product ON mv_current_prices (product_id);
CREATE INDEX        idx_mv_cp_instock ON mv_current_prices (product_id) WHERE stock_status = 'in_stock';
