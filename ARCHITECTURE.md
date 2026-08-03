# DaamKoto — Architecture

**How the system is actually built.** For *what it's meant to be*, see [PRD.md](PRD.md).
For *why things changed*, see [IMPROVEMENTS.md](IMPROVEMENTS.md).

---

## 1. Data flow, end to end

```
 13 retailer websites
        │  Playwright, 2–3 s between pages
        ▼
 scrapers/{retailer}/scrape_{category}.py   ──▶  data/raw/{retailer}_{cat}_{ts}.json
        │                                          (raw, unnormalized, gitignored)
        ▼
 cleaning/normalize.py   --input <raw> --category <cat>
        │  regex spec extraction → flat `specs` dict + match_key
        ▼
 data/processed/normalized_{retailer}_{cat}.json
        │
        ▼
 cleaning/matcher.py --category <cat>
        │  MPN-exact first, then rapidfuzz on names, folded with union-find
        ▼
 data/processed/matched_{cat}_products.json   (one entry per canonical product)
        │
        ▼
 database/load.py --category "GPU" --input <matched>
        │  UPSERT products · APPEND prices (never UPDATE)
        ▼
 PostgreSQL  ──▶  database/refresh_mv.py  (REFRESH MATERIALIZED VIEW mv_current_prices)
        │
        ▼
 scripts/remove_backgrounds.py --category "GPU"
        │  rembg → transparent PNG → Cloudflare R2 → image_cutouts table
        ▼
 backend/  FastAPI  ──▶  frontend-react/  React
```

`run_pipeline.py` chains all of this for one category. `scheduler.py` loops
`run_pipeline` over every category. The **daily GitHub Actions workflow** runs
`scheduler`-equivalent work as a parallel matrix straight against Neon.

**The cardinal rule:** never clean inside a scraper, never scrape inside a
cleaner. Each stage reads files and writes files.

---

## 2. Stage 1 — Scrapers (`scrapers/`)

One file per retailer per category: `scrapers/{retailer}/scrape_{category}.py`.
Engine is **Playwright** because most of these sites render prices with JS.

Each scraper emits a list of records shaped like:

```python
{
  "name":        "Kingston Fury Beast 16GB DDR5 5600MHz",
  "price_bdt":   6300,
  "in_stock":    True,
  "product_url": "https://...",
  "image_url":   "https://...",
  "scraped_at":  "2026-08-01T12:00:00Z",
  "source":      "StarTech",        # display name — must match load.py exactly
  "specs":       {...},             # raw spec table, unnormalized
}
```

### File counts per retailer

| Retailer | Scrapers | Notes |
|---|---|---|
| Skyland | 24 | full coverage |
| Creatus | 24 | full coverage |
| UltraTech | 24 | full coverage |
| Ryans | 23 | Cloudflare-protected |
| PotakaIT | 23 | |
| StarTech | 22 | also has `enrich.py` for detail-page specs |
| Techland | 21 | |
| TrustTech | 21 | |
| BinaryLogic | 19 | |
| UCC | 18 | |
| ComputerSource | 18 | |
| VibeGaming | 21 | WooCommerce; no laptop RAM / portable SSD / portable HDD listing |
| EZGadgets | 14 | WooCommerce; peripherals-led, thin on core components |
| SellTech | 10 | GPU + peripherals only, by design |
| PCHouse | 10 | GPU + peripherals only, by design |

### Scraper coverage matrix

`Y` = scraper exists, `.` = no scraper.

| Category | star | ryan | tech | pota | ucc | ultr | bina | skyl | crea | sell | comp | trus | pcho | ezga | vibe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ram | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | Y | Y |
| laptop_ram | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | . | . |
| gpu | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| processor | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | Y | Y |
| motherboard | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | Y | Y |
| ssd | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | Y | Y |
| portable_ssd | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | . | . |
| hdd | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | . | Y |
| portable_hdd | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | . | . |
| psu | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | Y | Y |
| cooler | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | Y | Y |
| casing_cooler | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | . | Y |
| casing | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | . | . | Y |
| monitor | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | . | Y | Y | Y | Y |
| keyboard | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| mouse | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| headset | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| ups | Y | Y | Y | Y | . | Y | . | Y | Y | Y | . | Y | Y | . | Y |
| speaker | . | Y | Y | Y | . | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| webcam | Y | Y | Y | Y | . | Y | . | Y | Y | Y | . | . | . | . | Y |
| gaming_chair | Y | Y | . | Y | Y | Y | . | Y | Y | . | . | Y | Y | . | Y |
| printer | Y | Y | Y | Y | . | Y | Y | Y | Y | Y | . | Y | . | . | Y |
| mousepad | Y | Y | . | . | . | Y | . | Y | Y | Y | . | . | Y | Y | Y |
| gamepad | . | . | . | Y | . | Y | . | Y | Y | . | Y | . | Y | Y | Y |

Biggest real gaps (excluding SellTech/PCHouse/EZGadgets/VibeGaming, whose
narrower coverage is intentional): `gamepad` missing at 6 retailers, `mousepad`
at 6, `webcam` at 4. Vibe Gaming closed one of each when it was added.

### Scraper helpers

| File | Purpose |
|---|---|
| `scrapers/gen_opencart_scrapers.py` | Code-generate scrapers for OpenCart shops (most BD sites are OpenCart) |
| `scrapers/gen_category_scrapers.py` | Generate a category across retailers |
| `scrapers/gen_ezgadgets_scrapers.py` | Generate the EZ Gadgets scrapers (WooCommerce Store API, DOM fallback) |
| `scrapers/category_urls.py` | Verified category URLs + card CSS selectors per retailer |
| `scrapers/probe_categories.py`, `probe_trusttech.py` | Exploration tools for finding URLs/selectors |
| `scrapers/startech/enrich.py` | Second pass over StarTech detail pages for MPN + full spec table |
| `scrapers/enrich_bundle.py` | Detects "Only With PC Build" bundle-only listings |
| `gen_scrapers.py` (root) | Original generator, superseded by the two above |

### Ryans / Cloudflare

Ryans sits behind a Cloudflare challenge. The working approach is a **fresh
browser context per page** — reusing one context across pages makes Cloudflare
re-issue the challenge and the scrape dies. This is slower but reliable. The same
protection rate-limits plain `curl`/`requests`, so backfill scripts must also go
through Playwright.

---

## 3. Stage 2 — Clean & match (`cleaning/`)

### `normalize.py` (84 KB — the most breakage-prone file in the repo)

Per-category `clean_{category}_record(raw) -> dict` functions, dispatched by
`clean_record()` at the bottom of the file. Each returns a flat `specs` dict
whose keys become the API's filter parameters.

Shared extractors: `normalize_name`, `extract_brand`, `extract_capacity`,
`extract_generation`, `extract_speed`, `extract_latency`, `extract_form_factor`,
`extract_kit`, `detect_rgb`, `detect_heatsink`, `detect_ecc`, `build_match_key`.

Normalization rules: `"16 GB"` → `"16GB"`, strip `৳`/`BDT`/commas, collapse
whitespace, uppercase MPNs. MPN is taken from an explicit field, else from a
`#MODEL-123` pattern in the product name.

`match_key` is `brand_capacity_generation_speed`, e.g.
`kingston_16gb_ddr5_5600mhz`.

### `matcher.py`

1. **Exact pass** — group by normalized MPN. Highest confidence.
2. **Fuzzy pass** — `rapidfuzz` on product names within the same `match_key`.
3. **Union-find** — transitively fold groups, so A≈B and B≈C put all three on
   one canonical product.
4. Elect a canonical name and write `matched_{cat}_products.json`.

The known failure modes are **false merges** (two real SKUs collapsed) and
**false splits** (one SKU appearing repeatedly). GPU segmentation once broke on
AMD RX 500-series 3-digit chipsets — fixed, but the class of bug recurs whenever
a new naming convention appears.

---

## 4. Stage 3 — Database (`database/`)

PostgreSQL only. Local for development, **Neon** in production. Migrations are
**always applied manually** — nothing auto-migrates at startup.

### Core tables

```sql
retailers (id, name UNIQUE, base_url)

products  (id, match_key, name, brand, model_number, category,
           specs JSONB, created_at,
           UNIQUE (match_key, name))

prices    (id, product_id → products, retailer_id → retailers,
           price_bdt NUMERIC(10,2), in_stock BOOLEAN,
           product_url, image_url, scraped_at TIMESTAMPTZ,
           seller_specs JSONB, stock_status, pc_bundle_only,
           UNIQUE (product_id, retailer_id, scraped_at))
```

`UNIQUE (match_key, name)` on products is deliberate: Team Vulcan Z and Team
Delta RGB share `team_8gb_ddr4_3200mhz` but are different products.

`UNIQUE (product_id, retailer_id, scraped_at)` on prices makes the loader
idempotent — re-running it on the same data inserts nothing.

**Prices are append-only. Never write an `UPDATE` or `DELETE` against them.**

### Indexes

| Index | Why |
|---|---|
| `idx_prices_current (product_id, retailer_id, scraped_at DESC)` | The hot path — resolves "current price per retailer" |
| `idx_prices_product_scraped` | Range scans on history |
| `idx_products_category`, `idx_products_brand` | Common filters |
| `idx_products_specs` GIN | Makes `specs->>'key' = value` fast |
| trigram GIN on `name`, `brand`, `model_number` | Fast `ILIKE '%kw%'` search (needs `pg_trgm`) |

### `mv_current_prices` (materialized view)

Pre-computes the current price per product per retailer. Every read path uses it
instead of re-deriving `DISTINCT ON ... ORDER BY scraped_at DESC`. It must be
refreshed after every load — `run_pipeline.py` calls `database/refresh_mv.py`
automatically.

### Migrations, in order

| File | What it adds |
|---|---|
| `schema.sql` | Base tables, indexes, `seller_specs` |
| `perf_indexes.sql`, `perf_indexes_v2.sql` | Additional performance indexes |
| `migration_v3_stock_status.sql` | Richer status: `in_stock` / `out_of_stock` / `upcoming` / `bundle_only` |
| `migration_v4_pc_bundle_only.sql` | Boolean flag — retailer sells it only inside a full PC build |
| `migration_v5_scraper_runs.sql` | `scraper_runs` table: category, retailers[], timings, status, counts |
| `migration_v6_alerts.sql` | Price-drop alerts (**verify this is applied to prod**) |
| `migration_v7_cheapest_listing.sql` | When a retailer lists one product twice, take the cheaper row |
| `migration_v8_expire_dead_listings.sql` | A listing stops counting once the retailer stops carrying it |
| `migration_v9_product_image.sql` | `image_url` on prices (hotlinked, per-retailer) |
| `migration_v10_image_cutouts.sql` | `image_cutouts` table: source URL → served cutout path |

Apply one with:

```powershell
python scripts/apply_migration.py database/migration_v10_image_cutouts.sql
```

---

## 5. Stage 4 — Backend (`backend/`)

FastAPI + Uvicorn. **All SQL lives in `queries.py`** — routes never build SQL.

| File | Size | Role |
|---|---|---|
| `main.py` | 47 KB | Routes, Pydantic models, filter params, warmup, background runs |
| `queries.py` | 33 KB | Every SQL query |
| `tools.py` | 21 KB | The 6 AI agent tools + dispatcher |
| `agent.py` | 14 KB | Agent loop — tool calling, iteration, response assembly |
| `chatbot.py` | 13 KB | Legacy NL → query-params path |
| `compat.py` | 12 KB | Compatibility rules + wattage model |
| `llm.py` | 9 KB | Groq / Gemini provider abstraction |
| `cache.py` | 8 KB | TTL cache with stale-while-revalidate + single-flight |
| `database.py` | 2 KB | Connection pool; prefers `DATABASE_URL`, falls back to `DB_*` |

### Endpoints (19)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness; `?deep=1` round-trips Postgres and reports `cache_warm`, `db_ms` |
| GET | `/categories` | Distinct categories |
| GET | `/brands` | Brands, optionally per category |
| GET | `/retailers` | Retailer list |
| GET | `/specs/values` | Live values for one spec key in one category |
| GET | `/products` | Search/filter — 20+ params incl. JSONB specs |
| GET | `/products/{id}` | One product with all listings |
| GET | `/products/{id}/seller-specs` | Per-retailer raw spec comparison |
| GET | `/products/{id}/history` | Full price history |
| GET | `/scrapers/status` | Freshness grid, run history, log tail |
| POST | `/scrapers/run` | Trigger a background pipeline run (concurrency-safe) |
| POST | `/chat` | Agentic assistant |
| GET | `/deals` | Biggest recent price drops |
| POST | `/build/plan` | AI build-from-budget |
| POST | `/build/check` | Compatibility check for a set of part IDs |
| POST | `/alerts` | Create a price-drop alert |
| GET | `/alerts` | List alerts for a device |
| DELETE | `/alerts/{id}` | Delete an alert |
| GET | `/alerts/triggered` | Alerts whose target price was hit |

`/media/*` is a `StaticFiles` mount serving local cutouts when R2 isn't configured.

### Spec filtering — 71 whitelisted keys

`_ALLOWED_SPEC_KEYS` in `queries.py` is a hard allowlist; a key not in it is
**silently ignored**, which is the usual reason a new filter "does nothing":

```
architecture, atx30, autofocus, backup_time, boost_clock, cache, capacity,
channels, chipset, chipset_brand, color, color_output, connectivity, cores,
curved, dpi, duplex, ecc, efficiency, fan_size, footrest, form_factor, fps,
front_usb_c, functions, generation, hdr, headset_form, heatsink, interface, kit,
latency, layout, m2_slots, massage, material, mechanical, memory_type,
microphone, modularity, model, nand_type, noise_cancelling, pad_size,
panel_type, platform, power_output, printer_type, psu_support, radiator_size,
ram_type, refresh_rate, resolution, response_time, rgb, rpm, screen_size,
series, side_panel, socket, speed, stitched_edge, switch_type, type, ups_type,
va_rating, vibration, vram, wattage, webcam_resolution, wifi
```

### AI layer

**Providers** (`llm.py`) — both free tier:
- `GROQ_MODEL = "llama-3.3-70b-versatile"` — fast lane, retrieval-style queries
- `GEMINI_MODEL = "gemini-2.0-flash"` — reasoning lane, multi-step work

`complete(model_tier=...)` routes between them. A `_gemini_auth_ok` flag caches a
failed Gemini auth so the app stops retrying a bad key and falls back to Groq.
**This project does not use the Anthropic API.**

**Agent tools** (`tools.py`) — the model may only call these six:
`search_products`, `get_product_details`, `get_price_history`,
`check_compatibility`, `plan_build`, `get_deals`. Everything the assistant says
about a price comes from one of these returning real rows.

**Compatibility model** (`compat.py`): `SYSTEM_BASE_WATTS = 90`; GPU and CPU
wattages come from regex→TDP lookup tables; `round_to_psu_size()` snaps the total
to a real PSU size from `[450, 500, 550, 650, 750, 850, 1000, 1200, 1300, 1600]`.
`evaluate_build()` returns `CompatResult` holding `CompatIssue` entries (socket
mismatch, RAM generation, clearance, PSU headroom, form factor).

---

## 6. Stage 5 — Frontend (`frontend-react/`)

React 18 · Vite 6 · Tailwind CSS v4 · TypeScript 5.6. Four views:
`browse | build | deals | scraper`.

```
src/
  App.tsx                 State orchestration; lazy-loads everything but Browse
  api.ts                  Typed fetch client
  config.ts               24 CATEGORIES + per-category filters + RETAILER_COLORS + PAGE_SIZE
  types.ts                Mirror of the Pydantic models
  index.css               Design tokens, dark theme
  components/
    Header.tsx            Logo, global search, view switcher
    CategoryTabs.tsx      Animated category switcher (prefetches on hover)
    FilterSidebar.tsx     Multi-select spec filters
    FilterChips.tsx       Active-filter pills
    ProductGrid.tsx       Card grid, skeletons, empty state
    ProductCard.tsx       Cutout image, cheapest price, savings + price-age badge
    ProductDrawer.tsx     Listings, spec diff, history chart  (lazy)
    PriceHistoryChart.tsx Recharts multi-retailer line chart
    PriceSpread.tsx       Min→max price bar
    Pagination.tsx        Pager
    Chatbot.tsx           Agent panel; renders rich blocks, drives the UI (lazy)
    CommandPalette.tsx    ⌘K navigation (lazy)
    WatchlistPanel.tsx    Saved products (lazy)
    DealsView.tsx         Price-drop feed (lazy)
    ScraperDashboard.tsx  Freshness, runs, trigger, log console (lazy)
    Icon.tsx              lucide-react icon resolver
    build/
      BuildStudio.tsx     Slot-based assembly (lazy)
      SlotPicker.tsx      Per-slot part chooser
      CompatReport.tsx    Issues from /build/check
      WattageGauge.tsx    Estimated draw → recommended PSU
      Rig3D.tsx           3D rig preview (three.js / react-three-fiber)
  lib/
    swr.ts                Memory + sessionStorage cache, in-flight dedupe
    prefetch.ts           Next page, hovered category, idle warm
    useProductSearch.ts   Seeds from cache during render; guards the unbounded query
    useUrlFilters.ts      Filter state ↔ URL
    useWatchlist.ts       localStorage watchlist
    useBuild.ts           Build state
    filterDefaults.ts     Default sort (must match backend _WARM_SORTS)
    compat.ts, tdp.ts     Client-side compatibility hints
    basket.ts, buildConfig.ts, format.ts, useCountUp.ts
```

`config.ts` is the single file to edit when a category or filter is added.
Category `icon` values are **lucide-react component names** (e.g. `"MemoryStick"`,
`"Gamepad2"`), not emoji.

### Retailer colors

Used by the history chart, price-spread bar and price dots. Missing name → grey
`#8a8a99`.

| Retailer | Hex | Retailer | Hex |
|---|---|---|---|
| StarTech | `#f43f4b` | Creatus | `#ec4899` |
| Ryans | `#22c55e` | SellTech | `#8b5cf6` |
| Techland / Techland BD | `#3b82f6` | ComputerSource | `#0ea5e9` |
| UltraTech | `#a855f7` | TrustTech | `#84cc16` |
| UCC | `#eab308` | PCHouse | `#f59e0b` |
| BinaryLogic | `#06b6d4` | PotakaIT | `#f97316` |
| Skyland | `#14b8a6` | EZGadgets | `#d946ef` |

---

## 7. Performance architecture

The target is a fast first paint for someone arriving cold on mobile data in
Bangladesh. Six mechanisms, each easy to break by accident.

**1. Nothing heavy on first paint.** `App.tsx` lazy-loads every view except
Browse and every overlay. Those are the only importers of **framer-motion**, and
the product drawer is the only path to **recharts** — so neither lands in the
entry chunk. Critical path is **~68.5 kB gzip**, down from 225 kB.

> ⚠️ Do not add `manualChunks` to `vite.config.ts`. Naming those chunks makes
> Vite emit `<link rel="modulepreload">` in `index.html`, so every first-time
> visitor downloads ~190 kB gzip of chart and animation code before a price
> renders. Let Rollup derive chunks from the real import graph.

> ⚠️ Do not statically import a lazy component into the Browse path. One
> top-level `import { ProductDrawer }` drags framer-motion back onto the
> critical path. Verify: `npm run build && grep modulepreload dist/index.html`.

**2. Backend response cache** (`cache.py`) — per-endpoint `TTLCache` with two
properties beyond a plain TTL dict:
- *stale-while-revalidate* — an expired entry is returned immediately while it
  refreshes on a background thread.
- *single-flight* — N concurrent misses on one key run one query, not N.

Use `cache.get_or_load(key, loader)`. **The loader must open its own connection**
(`with database.get_db() as conn`) because it may run on a background thread
after the request returned.

**3. Startup warmup** (`_warm_caches()` in `main.py`) — pre-loads page 1 of each
warm category at boot so the first visitor after a deploy gets a ~4 ms cache hit.

> ⚠️ Warm keys must match what the frontend actually requests. `_WARM_PAGE_SIZE`
> (20) mirrors `PAGE_SIZE` in `config.ts`; `_WARM_SORTS`
> (`store_count_desc`, `price_asc`) mirrors `filterDefaults.ts`. A mismatch warms
> keys nobody asks for and every visitor is slow again.
>
`_WARM_CATEGORIES` mirrors all 24 frontend categories. With two warmed sorts,
`cache_warm` reaches 48 product-list entries once startup warmup completes.

**4. Client cache** (`lib/swr.ts`) — memory + `sessionStorage` keyed by request
URL, with in-flight dedupe. Revisiting a category issues **zero** requests.
`useProductSearch` seeds from it during render, so a cached view paints real
products on the first frame instead of a skeleton. `lib/prefetch.ts` loads the
next page while you read, prefetches a category on pointer-enter, and warms the
rest on idle — all skipped when the browser reports Save-Data or 2G.

**5. Edge bootstrap snapshots** (`scripts/export_bootstrap_snapshots.py`) — after
the daily scrape, page 1 of both default sorts for all 24 categories is queried
directly from PostgreSQL and uploaded to R2. On a client cache miss,
`useProductSearch` races this snapshot against the live API. The snapshot can
paint the grid while Render/Neon are asleep; the API response replaces it when
ready. Snapshots contain only database rows — they are not a second source of
product or price facts.

**6. Keep-warm** (`.github/workflows/keep-warm.yml`) — Render free spins down
after ~15 min idle (30–50 s cold start) and Neon suspends an idle database. A
cron pings `/health?deep=1` during Bangladeshi waking hours, which touches
Postgres too. GitHub scheduled workflows can be delayed by hours, so this is a
best-effort latency optimization; correctness and first paint do not depend on it.

### Query rules

- `search_products` returns its total via `COUNT(*) OVER ()` **in the same
  query**. Do not reintroduce a second `COUNT(*)` round trip.
- A `/products` call with **neither `category` nor `search`** aggregates the
  whole catalogue and is by far the slowest thing the API does.
  `useProductSearch` refuses to issue it — keep that guard.
- Use `127.0.0.1`, never `localhost` — IPv6-first resolution on Windows adds
  ~200 ms per connection.

### Measuring

```powershell
curl -s "http://127.0.0.1:8000/health?deep=1"      # cache_warm + db_ms
cd frontend-react; npm run build
grep -E "modulepreload|<script" dist/index.html    # entry should preload nothing large
```

---

## 8. Images and edge-snapshot pipeline (`scripts/`)

Retailer photos have a white background baked into the JPEG, which looks broken
on a dark UI.

1. `migration_v9` stores the retailer's `image_url` on the prices row (hotlinked
   — the bytes are never copied).
2. `scripts/remove_backgrounds.py` finds current image URLs with no cutout,
   downloads each, runs **rembg** across a `ProcessPoolExecutor`, and produces a
   transparent PNG.
3. If `.env.r2` is configured, the PNG is uploaded to **Cloudflare R2** and the
   public **Worker** URL is stored; otherwise a local `/media/cutouts/...` path is.
4. `migration_v10`'s `image_cutouts` table maps source URL → cutout path. Queries
   `LEFT JOIN` it to expose `image_cutout`.

Design note: it keys on the **source image URL** already present in
`mv_current_prices`, so the scrape→normalize→match→load chain needed no changes.
Idempotent and safe to re-run. `run_pipeline.py` invokes it automatically after
load (`fatal=False`, so a cutout hiccup never blocks a price update); skip with
`--no-cutouts`.

> ⚠️ **rembg OOMs above 6 workers on this machine** and fails silently. Keep
> `--workers 6`.

> ⚠️ **Never serve from `r2.dev`** — it is aggressively rate-limited. Always go
> through the Worker (`scripts/r2_image_worker.js`).

Related: `upload_cutouts_r2.py` (bulk upload), `backfill_neon_images.py`
(populate prod), `sweep_all_images.sh` (full sweep).

The same R2 bucket/Worker serves `snapshots/v1/`. The exporter stores plain JSON
(Cloudflare handles transport compression), and the frontend uses a six-hour URL
version so an old immutable Worker response cannot stick in a browser cache.

---

## 9. Automation

| Workflow | Schedule | Purpose |
|---|---|---|
| `daily-scrape.yml` | 20:00 UTC (02:00 Dhaka) | Full sweep → Neon, then publish R2 fast-start snapshots |
| `keep-warm.yml` | Every 10 min, 00:00–20:00 UTC | Ping `/health?deep=1` so Render + Neon stay awake |
| `weekly-backup.yml` | Sun 21:00 UTC | `pg_dump` → gzip → 90-day build artifact |

**Why the scrape is a matrix:** run sequentially, a full sweep measured **4 h 02
m** — no headroom under GitHub's 6 h job ceiling. It now runs categories in
parallel with **`max-parallel: 4`**, deliberately low: every category hits the
same 13 shops, so N parallel jobs is N× the request rate per shop. Four keeps a
sweep near an hour while no retailer sees more than four concurrent crawlers.

**Why keep-warm stops at 20:00 UTC:** Render allows 750 instance-hours/month and
a month is ~730 h, so 24/7 leaves no headroom. Running 00:00–20:00 UTC =
06:00–02:00 Dhaka covers every waking hour in Bangladesh at ~608 h/month.

**Why weekly backup:** prices are append-only and the history is the one thing
that cannot be regenerated. Today's prices can be re-scraped; what a GPU cost on
15 June cannot. Neon's free tier keeps only 6 h of point-in-time restore.

Local equivalents: `scripts/run_daily_scrape.ps1`, `scripts/register_daily_task.ps1`.

---

## 10. Local operations

```powershell
.\venv\Scripts\Activate.ps1                              # always first

python run_pipeline.py --category gpu                     # one category, all retailers
python run_pipeline.py --category ram --retailers startech ryans
python run_pipeline.py --category gpu --skip-scrape       # reuse raw files
python run_pipeline.py --category gpu --dry-run           # no DB writes
python run_pipeline.py --category gpu --no-cutouts        # skip background removal

python scheduler.py --once                                # every category, once
python scheduler.py --once --categories ram gpu --retailers startech
python scheduler.py                                       # daemon, 12 h cycle
python scheduler.py --interval-hours 6

python scripts/apply_migration.py database/migration_vX.sql
python database/refresh_mv.py
python scripts/freshness_report.py
python scripts/db_check.py
```

`run_pipeline.py` forces UTF-8 on its own and its children's stdio, because
Windows consoles default to cp1252 and the pipeline prints `→ ✓ ৳`.

Diagnostic/one-off scripts also live in `scripts/`: `build_matrix.py`,
`backfill_ryans_urls.py` (repairs the NULL-URL incident), `backfill_neon_images.py`.

---

## 11. Environment & configuration

| File | Contents |
|---|---|
| `.env` | `DB_HOST/PORT/NAME/USER/PASSWORD`, optional `DATABASE_URL`, `GROQ_API_KEY`, `GEMINI_API_KEY` |
| `.env.neon` | Neon connection string for pushing local data to production |
| `.env.r2` | Cloudflare R2 credentials + `R2_PUBLIC_BASE` |
| `.env.example` | Template — copy to `.env` |
| `frontend-react/.env` | `VITE_API_BASE` (baked in at **build** time) |

`backend/database.py` prefers `DATABASE_URL` when set and falls back to the
discrete `DB_*` vars, so identical code runs locally and in the cloud.

---

## 12. Conventions

- Raw scraped data → `data/raw/` (gitignored)
- Processed data → `data/processed/` (gitignored)
- Scheduler logs → `logs/scheduler.log` (gitignored)
- Never clean inside a scraper; never scrape inside a cleaner
- Prices are BDT, stored `NUMERIC(10,2)`
- All timestamps UTC
- Always activate `venv/` before any Python command
- All migrations applied manually — nothing auto-migrates at startup
- **Slug vs. display name** matters — see the table in `CLAUDE.md`. The scraper's
  `source` field and the `KNOWN_RETAILERS` key in `database/load.py` must match
  *exactly*; that is how the loader resolves `retailer_id`.

---

## 13. Current scale

| Metric | Value |
|---|---|
| Canonical products | 35,152 |
| Price rows | 146,072 |
| Retailers | 13 |
| Categories with data | 24 |
| Scraper files | ~257 |

Largest categories: Casing 3,946 · Monitor 3,021 · Keyboard 2,906 · SSD 2,847 ·
Motherboard 2,776 · CPU Cooler 2,652 · Mouse 2,622 · GPU 2,577 · RAM Desktop 2,200.

Smallest: Portable HDD 182 · RAM Laptop 185 · Gamepad 195 · HDD 291.
