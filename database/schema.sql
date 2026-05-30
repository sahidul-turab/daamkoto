-- PC Component Price Comparison — PostgreSQL schema
--
-- Design rules:
--   • products  — one row per unique physical product; identity is match_key
--   • retailers — one row per store; seeded at startup
--   • prices    — APPEND-ONLY, never UPDATE; enables free price history
--
-- To reset during development:
--   DROP TABLE IF EXISTS prices, products, retailers CASCADE;

-- -------------------------------------------------------------------------
-- Retailers
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retailers (
    id       SERIAL PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,       -- 'StarTech', 'Ryans', 'Techland'
    base_url TEXT NOT NULL
);

-- -------------------------------------------------------------------------
-- Products
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id           SERIAL PRIMARY KEY,
    match_key    TEXT NOT NULL,          -- brand_capacity_gen_speed, e.g. kingston_8gb_ddr4_3200mhz
    name         TEXT NOT NULL,          -- canonical display name (unique per physical product)
    brand        TEXT,
    model_number TEXT,                   -- best available MPN (may be NULL for some products)
    category     TEXT,                   -- 'RAM', 'GPU', 'CPU', 'SSD', ...
    specs        JSONB,                  -- {capacity, generation, speed, model_series, ...}
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    -- Two products with the same match_key can exist if they have different names
    -- (e.g. Team Vulcan Z and Team Delta RGB both have match_key team_8gb_ddr4_3200mhz)
    UNIQUE (match_key, name)
);

-- -------------------------------------------------------------------------
-- Prices (append-only)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prices (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    retailer_id INTEGER NOT NULL REFERENCES retailers(id),
    price_bdt   NUMERIC(10, 2) NOT NULL,
    in_stock    BOOLEAN DEFAULT TRUE,
    product_url TEXT,
    scraped_at  TIMESTAMPTZ NOT NULL,
    -- Prevents duplicate rows if the loader runs twice on the same data
    UNIQUE (product_id, retailer_id, scraped_at)
);

-- DISTINCT ON (product_id, retailer_id) ORDER BY scraped_at DESC — this is the hot path
-- for resolving "current price per retailer" in the _CURRENT_PRICES_CTE used by every query.
CREATE INDEX IF NOT EXISTS idx_prices_current
    ON prices (product_id, retailer_id, scraped_at DESC);

-- Legacy single-column index (kept for range scans on scraped_at alone)
CREATE INDEX IF NOT EXISTS idx_prices_product_scraped
    ON prices (product_id, scraped_at DESC);

-- Filtering by category, brand (common search patterns)
CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_products_brand     ON products (brand);

-- GIN index on specs JSONB so specs->>'key' = value filters are fast
CREATE INDEX IF NOT EXISTS idx_products_specs ON products USING GIN (specs);

-- Trigram indexes for fast ILIKE '%keyword%' search on name/brand/model_number.
-- Requires pg_trgm extension (ships with standard PostgreSQL).
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_products_name_trgm
    ON products USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_brand_trgm
    ON products USING GIN (brand gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_products_model_trgm
    ON products USING GIN (model_number gin_trgm_ops);

-- -------------------------------------------------------------------------
-- Per-retailer raw spec data (added after initial schema)
-- -------------------------------------------------------------------------
-- Stores the raw spec table scraped from each retailer's product detail page.
-- Used to power the cross-seller spec comparison (shared vs differing specs).
-- Populated by enrich.py (StarTech detail pages) and inline_specs from listing scrapers.
ALTER TABLE prices ADD COLUMN IF NOT EXISTS seller_specs JSONB DEFAULT '{}'::jsonb;
