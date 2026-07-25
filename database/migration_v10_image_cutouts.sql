-- Migration v10: background-removed product cutouts
--
-- Retailer photos have a solid white background baked into the JPEG. To show a
-- product floating on the dark UI we remove that background (rembg) into a
-- transparent PNG and self-host it. This table maps a source image URL to the
-- served cutout path.
--
-- Decoupled by design: it keys on the source image URL that already lives in
-- prices/mv_current_prices, so the scraper -> normalize -> match -> load chain
-- needs no changes. The processor (scripts/remove_backgrounds.py) fills it in,
-- and queries LEFT JOIN it on image_url to expose `image_cutout`.
--
-- Apply with:
--   python scripts/apply_migration.py database/migration_v10_image_cutouts.sql

CREATE TABLE IF NOT EXISTS image_cutouts (
    source_url  TEXT PRIMARY KEY,       -- the retailer image URL (== prices.image_url)
    cutout_path TEXT NOT NULL,          -- served path, e.g. /media/cutouts/<hash>.png
    width       INTEGER,
    height      INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
