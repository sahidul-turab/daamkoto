# DaamKoto (দাম কত?) — PC Component Price Comparison, Bangladesh

> **Agent operating manual.** This file holds the rules, workflows and traps.
> Companion docs:
> | Doc | Read it for |
> |---|---|
> | [README.md](README.md) | What this is, quickstart |
> | [PRD.md](PRD.md) | Product scope, features, roadmap, known gaps |
> | [ARCHITECTURE.md](ARCHITECTURE.md) | How every stage/module/table works |
> | [IMPROVEMENTS.md](IMPROVEMENTS.md) | Why decisions were made (decision log) |
> | [DEPLOY.md](DEPLOY.md) | Shipping changes, free-tier budget |

## Vision
A website where Bangladeshi PC buyers can search for a component (e.g. RAM, GPU, SSD) and instantly see its price compared across multiple local retailers (StarTech, Ryans, Techland, and others). The user finds the cheapest source in one place instead of tab-hopping.

**Edge over PCPartPickerBD**: an AI chatbot layer — users can ask in plain language ("find me 16GB DDR4 RAM under 4000 taka") and the bot translates that into a structured database query. The LLM understands; the database answers; the bot never invents prices.

Also stores price history (append-only timestamps) so users can see how prices changed over time.

**Live:** frontend on Vercel (https://daamkoto.vercel.app), API on Render
(https://daamkoto-api.onrender.com), database on Neon. Scrapers run daily from
GitHub Actions. Everything is free tier.

**Scale today:** ~35,150 canonical products · ~146,000 price rows · 15 retailers
· 24 live categories.

---

## User / collaborator profile
- Data science student, Bangladesh
- Knows Python at a basic level; has hands-on Playwright experience
- Weak on web frontend — React frontend is now the primary UI
- Wants explanations of decisions, not just code drops

---

## Retailers in scope (15 total)
1. **StarTech** — `startech.com.bd`
2. **Ryans** — `ryans.com`
3. **Techland BD** — `techlandbd.com`
4. **PotakaIT** — `potakait.com`
5. **UCC** — `ucc.com.bd`
6. **UltraTech** — `ultratech.com.bd`
7. **BinaryLogic** — `binarylogic.com.bd`
8. **Skyland** — `skyland.com.bd`
9. **Creatus** — `creatus.com.bd`
10. **SellTech** — `selltech.com.bd` (GPU + peripherals only — 10 scrapers)
11. **ComputerSource** — `computersource.com.bd`
12. **TrustTech** — `trusttechbd.com`
13. **PCHouse** — `pchouse.com.bd` (GPU + peripherals only — 10 scrapers)
14. **EZGadgets** — `ggezgadgets.com` (WooCommerce; peripherals-led — 14 scrapers)
15. **VibeGaming** — `vibegaming.com.bd` (WooCommerce; 21 scrapers — no laptop
    RAM, portable SSD or portable HDD listing)

Coverage per retailer is uneven by design. The full `Y`/`.` matrix lives in
[ARCHITECTURE.md](ARCHITECTURE.md#scraper-coverage-matrix).

---

## Categories in scope (24 live)

**Core components (13):** `ram` (RAM Desktop), `laptop_ram`, `gpu`, `processor`,
`motherboard`, `ssd`, `portable_ssd`, `hdd`, `portable_hdd`, `psu`,
`cooler` (CPU Cooler), `casing_cooler`, `casing`

**Peripherals & lifestyle (11):** `monitor`, `keyboard`, `mouse`,
`headset` (shown as "Headphone"), `ups`, `speaker`, `webcam`, `gaming_chair`,
`printer`, `mousepad`, `gamepad`

> `odd` (optical drives) is still a `--category` choice in `run_pipeline.py` but
> has **zero scrapers**. It is dead — don't treat it as a category.

Note the slug/label mismatches: `ram` → "RAM DESKTOP", `cooler` → "CPU COOLER",
`headset` → "HEADSET" (UI label "Headphone"), `mousepad` → "MOUSE PAD".

---

## Architecture (6 stages)

### Stage 1 — Scrapers (`scrapers/`)
One Python file per retailer per category. Uses **Playwright** (JS-rendered pages).

Rules:
- Polite crawling: 2–3 second sleep between page requests
- Respect robots.txt
- Extract raw data only: name, price, model number, specs, stock status, product URL
- No cleaning/normalization here — that's Stage 2's job

### Stage 2 — Clean & Match (`cleaning/`)
- Normalize strings: "16GB" / "16 GB" → "16GB", strip ৳/BDT, remove whitespace
- Match by **brand + model number** first (exact key)
- Fall back to **rapidfuzz** fuzzy matching on product names
- Output: canonical `products` table entry per unique physical product

### Stage 3 — Database (`database/`)
**PostgreSQL** only. Schema is append-only for prices.

Key design decision: `prices` rows are never updated — each scrape run inserts new rows
with a timestamp. Use `scraped_at DESC` (via `mv_current_prices` materialized view) to
get current prices.

See `database/schema.sql` for the full schema. All migrations are run manually.

### Stage 4 — Backend (`backend/`)
**FastAPI** + Uvicorn. All data access goes through `backend/queries.py`.

Endpoints:
- `GET /health` — liveness
- `GET /categories`, `/brands`, `/retailers`, `/specs/values` — metadata
- `GET /products` — search/filter (20+ params, JSONB specs)
- `GET /products/{id}` — single product with all listings
- `GET /products/{id}/seller-specs` — per-retailer raw spec comparison
- `GET /products/{id}/history` — full price history
- `POST /chat` — Agentic AI assistant (multi-tool: search, compat, build, history, deals)
- `GET /deals` — biggest recent price drops across all retailers
- `POST /build/plan` — AI build-from-budget
- `POST /build/check` — compatibility check for a set of part IDs
- `POST /alerts` — create a price-drop alert; `GET /alerts` — list; `DELETE /alerts/{id}`
- `GET /alerts/triggered` — alerts whose target price was hit
- `GET /scrapers/status` — freshness, run history, log tail
- `POST /scrapers/run` — trigger a background pipeline run (concurrency-safe)

19 endpoints total, plus a `/media` StaticFiles mount for locally-served cutouts.

**AI providers** (`backend/llm.py`) — Groq `llama-3.3-70b-versatile` (fast lane)
and Google Gemini `gemini-2.0-flash` (reasoning lane), both free tier, with
automatic fallback. **This project does not use the Anthropic API.**

The agent (`backend/agent.py`) may only speak through six tools in
`backend/tools.py`: `search_products`, `get_product_details`, `get_price_history`,
`check_compatibility`, `plan_build`, `get_deals`. Add a *tool* to add a
capability — never loosen the prompt. A hallucinated price is a P0 bug.

### Stage 5 — Frontend (`frontend-react/`)
**React 18 + Vite 6 + Tailwind CSS v4** premium dark UI. Four views
(`browse | build | deals | scraper`):
- **Browse** — category tabs, filter sidebar, product grid with price-age badges
- **Build** — PC parts assembly studio, compatibility check, wattage gauge, 3D rig preview
- **Deals** — biggest recent price drops, computed from price history
- **Scraper** — health dashboard (freshness grid, run history, manual trigger, log console)

Plus overlays: product drawer, chatbot, ⌘K command palette, watchlist panel — all
lazy-loaded.

> The old Streamlit frontend has been **removed**. `frontend-react/` is the only
> frontend. Ignore any doc that calls Streamlit a "fallback".

### Stage 6 — Product images (`scripts/`)
Retailer photos have a white background baked in, which looks broken on the dark
UI. `scripts/remove_backgrounds.py` runs **rembg** → transparent PNG → uploads to
**Cloudflare R2** → serves via a Worker, recording source URL → cutout path in the
`image_cutouts` table. `run_pipeline.py` calls it automatically after load
(non-fatal); skip with `--no-cutouts`.

> ⚠️ **rembg OOMs above 6 workers on this machine and fails silently.** Keep `--workers 6`.

> ⚠️ **Never serve from `r2.dev`** — aggressively rate-limited. Always use the
> Worker (`scripts/r2_image_worker.js`).

---

## Performance architecture (read before touching the hot path)

The goal is that a product list is on screen fast for **every** visitor, including
someone arriving cold on mobile data in Bangladesh. Five things make that work;
each is easy to break by accident.

### 1. Nothing heavy on the first paint
`frontend-react/src/App.tsx` lazy-loads every view except Browse, and every
overlay (drawer, chatbot, palette, watchlist). Those are the only consumers of
**framer-motion**, and the product drawer is the only path to **recharts** —
so both stay out of the entry chunk. Critical-path JS is ~68.5 kB gzipped.

> ⚠️ **Do not add `manualChunks` back to `vite.config.ts`.** Forcing `recharts` /
> `framer-motion` into named chunks makes Vite emit `<link rel="modulepreload">`
> for them in `index.html`, so every first-time visitor downloaded ~190 kB gzip
> of chart and animation code before a single price rendered. Let Rollup derive
> chunks from the real import graph.

> ⚠️ **Do not statically import a lazy component into the Browse path.** One
> `import { ProductDrawer }` at the top of `App.tsx` pulls framer-motion back
> onto the critical path. Check with:
> `npm run build && grep modulepreload dist/index.html` — the entry should
> preload nothing large.

### 2. Backend response cache — `backend/cache.py`
A `TTLCache` per endpoint family, with two properties beyond a plain TTL dict:
- **stale-while-revalidate** — an expired entry is still returned *immediately*
  while it refreshes on a background thread. Users never wait on a timer.
- **single-flight** — N concurrent misses on the same key run one query, not N.

Use `cache.get_or_load(key, loader)` in routes. The loader must open its own
connection (`with database.get_db() as conn`), because it may run on a
background thread after the request has returned.

### 3. Startup warmup — `_warm_caches()` in `backend/main.py`
Pre-loads page 1 of every category in `_WARM_CATEGORIES` at boot, so the first
visitor after a deploy gets a cache hit (~4 ms) instead of a cold aggregation.
(The list mirrors all 24 live categories.)

> ⚠️ The warm keys must match what the frontend actually requests. If you change
> `PAGE_SIZE` in `frontend-react/src/config.ts` or `sort` in
> `src/lib/filterDefaults.ts`, update `_WARM_PAGE_SIZE` / `_WARM_SORTS` to match
> — otherwise the warmup fills keys nobody asks for and every visitor is slow
> again. Verify with `GET /health?deep=1` (`cache_warm` should be non-zero) and
> by timing a first request after a restart.

`cache_warm` is `len(_WARM_CATEGORIES) × len(_WARM_SORTS)` — 48 product-list
entries after a complete warmup.

### 4. Client cache — `frontend-react/src/lib/swr.ts`
Memory + `sessionStorage`, keyed by request URL, with in-flight de-duplication.
Revisiting a category issues **zero** network requests. `useProductSearch` seeds
state from this during render, so a cached view paints with real products on the
first frame rather than showing a skeleton.

Prefetching (`src/lib/prefetch.ts`): the next page loads while you read the
current one, category tabs prefetch on pointer-enter, and remaining categories
warm on idle — skipped entirely when the browser reports Save-Data or 2G.

### 5. Edge bootstrap snapshots — R2 / Worker
`scripts/export_bootstrap_snapshots.py` queries PostgreSQL directly after the
daily scrape and publishes page 1 for every category and both default sorts.
`useProductSearch` races the snapshot with the API, paints the first result, and
lets the live API replace it. This is the guaranteed first-paint path when
Render/Neon are cold; the LLM is not involved and every value is still a DB row.

### 6. Keep-warm — `.github/workflows/keep-warm.yml`
Render free spins down after ~15 min idle (30–50 s cold start) and Neon suspends
an idle database. A cron pings `/health?deep=1` during Bangladesh waking hours
(00:00–20:00 UTC), which touches Postgres too. GitHub schedules are best-effort
and have been delayed by hours, so first paint must never depend on this job.

### Query rules
- `search_products` returns its total via `COUNT(*) OVER ()` in the same query —
  do not reintroduce a second `COUNT(*)` round trip.
- A `/products` call with **neither `category` nor `search`** aggregates the whole
  catalogue and is by far the slowest thing the API does. `useProductSearch`
  refuses to issue it; keep that guard.

### Measuring
```bash
# Backend: warm state + a first-request timing after restart
curl -s "http://127.0.0.1:8000/health?deep=1"

# Frontend: what the browser must download before first paint
cd frontend-react && npm run build
grep -E "modulepreload|<script" dist/index.html
```

---

### Stage 5b — Scraper Automation (`scheduler.py` + GitHub Actions)
`scheduler.py` is a background daemon that cycles through all **24** categories
in round-robin order.
- Logs to `logs/scheduler.log` (also readable from the Scraper dashboard)
- Records every run in the `scraper_runs` PostgreSQL table
- FastAPI backend can also trigger runs via `POST /scrapers/run`

**In production the daily refresh runs on GitHub Actions, not on a local machine:**

| Workflow | Schedule | Purpose |
|---|---|---|
| `.github/workflows/daily-scrape.yml` | 20:00 UTC (02:00 Dhaka) | Full sweep → Neon + publish R2 fast-start snapshots |
| `.github/workflows/keep-warm.yml` | Every 10 min, 00:00–20:00 UTC | Keep Render + Neon awake |
| `.github/workflows/weekly-backup.yml` | Sun 21:00 UTC | `pg_dump` → 90-day artifact |

> ⚠️ **Do not raise `max-parallel: 4` in `daily-scrape.yml` to speed it up.**
> Every category hits the same 15 shops, so N parallel jobs is N× the request
> rate at each retailer. The scrapers sleep 2–3 s between pages precisely to stay
> polite; four keeps a sweep near an hour while no shop sees more than four
> concurrent crawlers. (Sequentially a sweep measured 4 h 02 m against GitHub's
> 6 h job ceiling — that's why parallelism exists at all.)

---

## Stack
| Purpose | Tool |
|---|---|
| Scraping | Python + Playwright |
| Fuzzy matching | rapidfuzz |
| Database | PostgreSQL |
| ORM / queries | psycopg2 (raw SQL, RealDictCursor) |
| Backend API | FastAPI + Uvicorn |
| Frontend | React 18 + Vite 6 + Tailwind CSS v4 |
| Charts | Recharts |
| Animations | Framer Motion |
| AI agent | Groq llama-3.3-70b (fast) + Gemini 2.0 Flash (reasoning) — both free |
| 3D rig preview | three.js + @react-three/fiber + drei |
| Icons | lucide-react |
| Background removal | rembg (product image cutouts) |
| Image hosting | Cloudflare R2 + Worker |
| Hosting | Vercel (web) · Render (API) · Neon (Postgres) · GitHub Actions (cron) |
| Env config | python-dotenv |
| Virtual env | `venv/` (always activate before running Python) |

---

## How to run locally

```bash
# 1. Activate the virtual environment (every new terminal)
.\venv\Scripts\Activate.ps1

# 2. Start the FastAPI backend (Terminal 1)
python -m uvicorn backend.main:app --reload --port 8000

# 3. Start the React frontend (Terminal 2)
cd frontend-react
npm run dev
# → opens at http://localhost:5173
```

The API docs (Swagger UI) are at `http://localhost:8000/docs`.

---

## Database migrations (run once manually)

There is a helper — no need for `psql` on PATH:

```bash
python scripts/apply_migration.py database/migration_v10_image_cutouts.sql
```

Migration files (apply in order):
1. `database/schema.sql` — base schema (already applied)
2. `database/perf_indexes.sql`, `perf_indexes_v2.sql` — performance indexes
3. `database/migration_v3_stock_status.sql` — in_stock / out_of_stock / upcoming / bundle_only
4. `database/migration_v4_pc_bundle_only.sql` — "only with PC build" flag
5. `database/migration_v5_scraper_runs.sql` — scraper run history table
6. `database/migration_v6_alerts.sql` — price-drop alerts ⚠️ *verify applied to prod Neon*
7. `database/migration_v7_cheapest_listing.sql` — pick cheapest when a retailer duplicates a product
8. `database/migration_v8_expire_dead_listings.sql` — stop counting listings a retailer dropped
9. `database/migration_v9_product_image.sql` — per-listing `image_url`
10. `database/migration_v10_image_cutouts.sql` — `image_cutouts` (source URL → cutout path)

Nothing auto-migrates at startup. After any load, refresh the materialized view:
`python database/refresh_mv.py`.

---

## Scraper automation

```bash
# Run all categories once (good for testing):
python scheduler.py --once

# Run specific categories / retailers:
python scheduler.py --once --categories ram gpu --retailers startech ryans

# Full daemon mode (sweeps all 24 categories every 12 hours):
python scheduler.py

# Custom interval:
python scheduler.py --interval-hours 6
```

Or trigger a single run from the **Scraper** tab in the React frontend UI.

---

## Build order — completed ✓ and remaining

- [x] Project structure + requirements.txt
- [x] database/schema.sql — base schema
- [x] scrapers/startech/scrape_ram.py — 408 products, 21 pages
- [x] scrapers/startech/enrich.py — MPN + full spec table from detail pages
- [x] cleaning/normalize.py — brand/capacity/gen/speed, match_key, MPN normalisation
- [x] cleaning/matcher.py — MPN-exact + rapidfuzz, union-find, canonical products
- [x] Full pipeline verified end-to-end on StarTech RAM data
- [x] database/load.py — upserts products, appends prices, idempotent
- [x] .env.example — DB credentials template
- [x] run_pipeline.py — chains scrape→enrich→normalize→match→load
- [x] PostgreSQL install + CREATE DATABASE pc_comparison
- [x] database/load.py verified — 408 products, 121 prices
- [x] FastAPI backend — 9 endpoints, connection pool, CORS, Swagger UI
- [x] React frontend (frontend-react/) — Browse, Build, Scraper views; dark premium UI
- [x] AI chatbot layer (Groq/Gemini — both free) — translates NL → query params
- [x] Agentic AI assistant (multi-tool: search, price history, compat, build-from-budget, deals)
- [x] Ryans scraper — 154 products, 8 pages, Cloudflare bypass
- [x] Rich category-specific specs: JSONB specs dict; GIN index; 20+ filter params
- [x] Expanded to 13 categories (RAM Desktop, RAM Laptop, GPU, Processor, Motherboard, SSD, Portable SSD, HDD, Portable HDD, PSU, CPU Cooler, Casing Cooler, Casing)
- [x] New scrapers: Ryans, Techland, UCC, UltraTech, BinaryLogic, PotakaIT (all categories)
- [x] 6 new retailers: Skyland, Creatus, SellTech, ComputerSource, TrustTech, PCHouse
- [x] VibeGaming (`vibegaming.com.bd`) — 15th retailer, 21 categories; first
      WooCommerce shop with a generator of its own
      (`scrapers/gen_vibegaming_scrapers.py`)
- [x] database/load.py + run_pipeline.py updated for 13 retailers
- [x] GPU segmentation bug fixed — AMD RX 500-series 3-digit chipsets
- [x] Full category scrapers for Skyland + Creatus (gen_opencart_scrapers.py)
- [x] Full category scrapers for TrustTech + ComputerSource
- [x] Price-age staleness badges on product cards (green/amber/red)
- [x] Scraper Health Dashboard in React (freshness grid, run history, manual trigger, log)
- [x] scheduler.py daemon — round-robin categories, 12h cycle, DB run tracking
- [x] database/migration_v5_scraper_runs.sql — scraper_runs table
- [x] Streamlit frontend removed — React is the sole frontend
- [x] Agent system: backend/agent.py + tools.py + llm.py + compat.py
- [x] Deals feed: GET /deals + DealsView.tsx
- [x] Build-from-budget: POST /build/plan
- [x] Compatibility advisor: POST /build/check
- [x] Price-drop alerts: database/migration_v6_alerts.sql + alert endpoints
- [x] Deals view added to Header navigation
- [x] Chatbot rebuilt to render rich blocks + execute UI actions
- [x] Performance pass: SWR + single-flight response cache, startup warmup,
      gzip + Cache-Control, single-query product search, client SWR cache +
      prefetching, code splitting (225 kB → 64 kB gzip critical path),
      keep-warm cron against Render/Neon cold starts
- [x] Rebrand to DaamKoto; deployed live (Vercel + Render + Neon), all free tier
- [x] Data-correctness fixes: dead-listing expiry (v8), cheapest-of-duplicates (v7),
      freshness scoped to the retailers a run actually covered
- [x] Automated daily refresh on GitHub Actions (matrix, max-parallel 4) → Neon
- [x] Weekly database backup workflow (history cannot be re-scraped)
- [x] Expanded 13 → 24 categories (monitor, keyboard, mouse, headphone, UPS,
      speaker, webcam, gaming chair, printer, mouse pad, gamepad)
- [x] Product images: rembg cutouts → Cloudflare R2 → Worker; automated in pipeline
      (migrations v9 + v10)
- [x] Multi-select filters, numeric-sorted options, previously-dead spec keys wired up
- [x] Ryans URL fix (extract from card anchor) + self-driving backfill script
- [x] Pipeline UTF-8 safe on Windows; loaders DSN/Neon aware
- [x] 3D rig preview in Build studio (three.js / react-three-fiber)
- [x] `_WARM_CATEGORIES` mirrors all 24 categories; 48 default product pages warm
- [x] Edge bootstrap snapshots make first paint independent of Render/Neon cold starts
- [x] Verified migration_v6_alerts.sql **is** applied to production Neon
      (2026-08-03): `alerts` table present with the full column set, and
      `GET /alerts` / `GET /alerts/triggered` both return 200 against it.
      Alerts are live, not inert — 0 rows only because nobody has created one.
- [ ] Fill scraper coverage gaps: `gamepad` (6 retailers), `mousepad` (6), `webcam` (4)
- [ ] Remove or implement the dead `odd` category choice in run_pipeline.py
- [ ] Move root-level one-off scripts (`probe_*.py`, `wipe_gpu.py`, `check_*.py`,
      17 MB `daamkoto_db_dump.sql`) into `scripts/archive/` or delete
- [x] First automated tests — `tests/test_normalize.py` (167 tests: match_key
      identity, GPU chipset regressions, dispatcher coverage, cleaner output
      contracts). Run with `python -m pytest tests/ -q`
- [ ] Extend tests beyond `normalize.py` — `matcher.py` (union-find folding) and
      `backend/queries.py` (the `_ALLOWED_SPEC_KEYS` allowlist) are next

> Full roadmap with reasoning lives in [PRD.md §8](PRD.md#8-known-gaps--roadmap).

---

---

## Workflow: Adding a new category (across existing retailers)

Example: adding **"monitor"** as a new category for StarTech, Ryans, etc.

Every single file that must be touched — in order:

### 1. Create scraper(s) — `scrapers/{retailer}/scrape_{category}.py`
One file per retailer. Follow an existing scraper as a template (e.g. `scrapers/startech/scrape_ram.py`).
Output format must match what `cleaning/normalize.py` expects:
```python
{"name": ..., "price_bdt": ..., "in_stock": ..., "product_url": ..., "scraped_at": ..., "specs": {...}}
```

### 2. Add a cleaner — `cleaning/normalize.py`
Add a new `clean_{category}_record(raw: dict) -> dict` function.
Look at `clean_monitor_record` or `clean_psu_record` for the pattern.
Must output a `specs` dict with all filterable fields as flat keys.
Wire it into the `clean_record()` dispatcher at the bottom of the file.

### 3. Register the category slug → DB name — `run_pipeline.py`
Two places in `main()`:
```python
# 1. Add to --category choices (line ~126):
choices=["ram", ..., "monitor", "YOUR_NEW_CATEGORY"]

# 2. Add to db_category dict (line ~154):
"your_new_category": "YOUR NEW CATEGORY DB NAME",
```

### 4. Add to the scheduler — `scheduler.py`
```python
CATEGORIES = [
    "ram", ..., "casing",
    "your_new_category",   # ← add here
]
```

### 5. Add spec keys — `backend/queries.py`
Add every filterable spec key from your cleaner to `_ALLOWED_SPEC_KEYS` (currently
**71 keys**). These are the keys the API will accept as filter params.

> ⚠️ **This is the step that gets forgotten.** A key missing from the allowlist is
> **silently ignored** — the filter renders, the user clicks it, and nothing
> changes. A dead filter looks identical to a filter with no matches. This has
> already happened once (fixed 2026-07-26).

```python
_ALLOWED_SPEC_KEYS = {
    ...,
    "your_spec_key",   # e.g. "panel_type", "refresh_rate"
}
```

### 6. Add filter params — `backend/main.py`
Add `Query` params to `GET /products` for each new spec key (follow the existing pattern):
```python
your_spec: str | None = Query(None, description="[YourCategory] description"),
```
Then add it to the `specs_filter` builder loop below the params section.
Also add it to the `_SPEC_KEYS` set in `POST /chat` so the chatbot can extract it.

### 7. Add category to the React frontend — `frontend-react/src/config.ts`
Add a `CategoryDef` entry to the `CATEGORIES` array:
```typescript
{
  label: "Your Category",
  db: "YOUR NEW CATEGORY DB NAME",   // must match run_pipeline.py db_category value
  icon: "Monitor",                   // lucide-react component name — NOT an emoji
  filters: [
    { kind: "select", param: "spec_key", label: "Label", specKey: "spec_key", fallback: ["Val1","Val2"] },
    { kind: "bool",   param: "has_feature", label: "Has Feature" },
  ],
},
```
`icon` is a **lucide-react component name** (`"MemoryStick"`, `"Gamepad2"`,
`"BatteryCharging"`…), resolved by `components/Icon.tsx`. Emoji will not render.

Also add a color to `RETAILER_COLORS` if this doesn't already exist (it's per retailer, not category — skip if the retailers are already there).

### 8. Add to dashboard trigger list — `frontend-react/src/components/ScraperDashboard.tsx`
```typescript
const ALL_CATEGORIES = [
  "ram", ..., "casing",
  "your_new_category",   // ← add here
];
```

### 9. Add to the cache warmup — `backend/main.py`
```python
_WARM_CATEGORIES = [
    "RAM DESKTOP", ..., "CASING",
    "YOUR NEW CATEGORY DB NAME",   # ← add here (DB name, not slug)
]
```
Skip this and the category's first visitor after every deploy pays a full cold
aggregation. This step was missed for all 11 peripheral categories — see the
Known gap note in the Performance section.

### 10. Add to the daily scrape workflow — `.github/workflows/daily-scrape.yml`
The matrix reads the category list; confirm the new slug is included so the
nightly refresh actually covers it.

### 11. Update the docs
- `CLAUDE.md` — categories list + build order
- `PRD.md` — scope (§5.2) if it changes what the product covers
- `ARCHITECTURE.md` — the scraper coverage matrix

### Quick checklist for a new category
```
[ ] scrapers/{retailer}/scrape_{category}.py  — one per retailer
[ ] cleaning/normalize.py                     — clean_{category}_record() + dispatcher
[ ] run_pipeline.py                           — choices list + db_category dict
[ ] scheduler.py                              — CATEGORIES list
[ ] backend/queries.py                        — _ALLOWED_SPEC_KEYS  ← silently breaks filters if missed
[ ] backend/main.py                           — Query params in GET /products + _SPEC_KEYS in /chat
[ ] backend/main.py                           — _WARM_CATEGORIES    ← silently costs cold starts if missed
[ ] frontend-react/src/config.ts              — CATEGORIES array (CategoryDef, lucide icon name)
[ ] frontend-react/src/components/ScraperDashboard.tsx — ALL_CATEGORIES list
[ ] .github/workflows/daily-scrape.yml        — matrix category list
[ ] CLAUDE.md + PRD.md + ARCHITECTURE.md      — docs
```

---

## Workflow: Adding a new retailer (for existing categories)

Example: adding **"PriceHunterBD"** that sells RAM, GPU, SSD.

### 1. Create the scraper directory + files
```
scrapers/pricehunterbd/
    scrape_ram.py
    scrape_gpu.py
    scrape_ssd.py
    ...
```
Check if the retailer's site is OpenCart (most BD shops are).
If yes: use `gen_opencart_scrapers.py` to generate the boilerplate, then edit the category URLs.
If no: copy the closest existing scraper and adapt the CSS selectors / JSON parsing.

The scraper slug (directory name) must be lowercase, no spaces, no hyphens — e.g. `pricehunterbd`.

### 2. Register the retailer in the loader — `database/load.py`
```python
KNOWN_RETAILERS = {
    ...,
    "PriceHunterBD": "https://www.pricehunterbd.com",   # ← add here
}
```
The key (`"PriceHunterBD"`) is the display name shown in the UI.
It must match the `source` field that your scraper writes into each listing.

### 3. Add to the pipeline — `run_pipeline.py`
```python
ALL_RETAILERS = [
    "startech", ..., "pchouse",
    "pricehunterbd",   # ← add here (slug, matches scrapers/ directory name)
]
```

### 4. Add to the backend API — `backend/main.py`
```python
_ALL_RETAILERS = [
    "startech", ..., "pchouse",
    "pricehunterbd",   # ← add here (same slug)
]
```

### 5. Add to the scheduler — `scheduler.py`
```python
ALL_RETAILERS = [
    "startech", ..., "pchouse",
    "pricehunterbd",   # ← add here
]
```

### 6. Add retailer color — `frontend-react/src/config.ts`
```typescript
export const RETAILER_COLORS: Record<string, string> = {
  StarTech: "#f43f4b",
  ...,
  PriceHunterBD: "#your_hex_color",   // ← add here (display name, not slug)
};
```
This color appears in the price history chart, price spread bar, and price card dots.
Pick a color not already used. If omitted, it falls back to grey (`#8a8a99`).

### 7. Add to dashboard trigger list — `frontend-react/src/components/ScraperDashboard.tsx`
```typescript
const ALL_RETAILERS = [
  "startech", ..., "pchouse",
  "pricehunterbd",   // ← add here (slug)
];
```

### 8. Run the pipeline once to seed the DB
```bash
python run_pipeline.py --category ram --retailers pricehunterbd
```
This will: scrape → normalize → match → load → refresh the materialized view.
Check the Scraper Health dashboard to confirm the new retailer appears in the freshness grid.

### 9. Update CLAUDE.md
- Add to **Retailers in scope** list with URL
- Update **Build order checklist**

### Quick checklist for a new retailer
```
[ ] scrapers/{retailer}/scrape_{category}.py  — one per category you want to cover
[ ] database/load.py                          — KNOWN_RETAILERS dict (display name → URL)
[ ] run_pipeline.py                           — ALL_RETAILERS list (slug)
[ ] backend/main.py                           — _ALL_RETAILERS list (slug)
[ ] scheduler.py                              — ALL_RETAILERS list (slug)
[ ] frontend-react/src/config.ts              — RETAILER_COLORS (display name → hex)
[ ] frontend-react/src/components/ScraperDashboard.tsx — ALL_RETAILERS list (slug)
[ ] CLAUDE.md                                 — retailers list + build order
```

### Important: slug vs display name
| Where | Format | Example |
|---|---|---|
| `scrapers/` directory | slug | `pricehunterbd` |
| `run_pipeline.py` ALL_RETAILERS | slug | `pricehunterbd` |
| `backend/main.py` _ALL_RETAILERS | slug | `pricehunterbd` |
| `scheduler.py` ALL_RETAILERS | slug | `pricehunterbd` |
| `ScraperDashboard.tsx` ALL_RETAILERS | slug | `pricehunterbd` |
| `database/load.py` KNOWN_RETAILERS key | display name | `PriceHunterBD` |
| `frontend-react/src/config.ts` RETAILER_COLORS key | display name | `PriceHunterBD` |
| Scraper's `source` field in output JSON | display name | `PriceHunterBD` |

The display name in `load.py` and the scraper's `source` field **must match exactly** — that's how the loader knows which retailer_id to use.

---

## Conventions
- Raw scraped data → `data/raw/` (gitignored)
- Processed data → `data/processed/` (gitignored)
- Scheduler logs → `logs/scheduler.log` (gitignored)
- Never clean data inside a scraper; never scrape inside a cleaning script
- Prices are always in BDT (Bangladeshi Taka), stored as NUMERIC
- All timestamps are UTC
- Always activate `venv/` before running any Python command
- All migrations are applied manually (no auto-migrate at startup)
- Use `127.0.0.1`, never `localhost` — IPv6-first resolution on Windows adds
  ~200 ms per connection
- Prices are **append-only**: never write `UPDATE` or `DELETE` against `prices`

---

## Traps — read before changing these areas

Every one of these has already cost real debugging time. They share a pattern:
**nothing raises an error.**

| Area | Trap |
|---|---|
| **Bundling** | Adding `manualChunks` to `vite.config.ts`, or statically importing a lazy component into the Browse path, silently puts ~190 kB gzip back on the critical path. Verify: `npm run build && grep modulepreload dist/index.html` |
| **Spec filters** | A key missing from `_ALLOWED_SPEC_KEYS` is ignored — the filter renders and does nothing |
| **Cache warmup** | `_WARM_CATEGORIES` / `_WARM_PAGE_SIZE` / `_WARM_SORTS` must mirror the frontend, or the warmup fills keys nobody requests |
| **Cache loaders** | A loader passed to `cache.get_or_load` **must open its own connection** — it can run on a background thread after the request returned |
| **Unbounded query** | `/products` with neither `category` nor `search` scans the whole catalogue. `useProductSearch` refuses it; keep that guard |
| **Ryans / Cloudflare** | Needs a **fresh browser context per page**. Reusing one context re-triggers the challenge. `curl`/`requests` are rate-limited too — backfills must use Playwright |
| **Scraper field loss** | A scraper returning *fewer fields* still "succeeds". Ryans dropped `product_slug` and every URL became NULL with no error |
| **rembg** | OOMs above 6 workers on this machine and fails silently. Keep `--workers 6` |
| **R2** | Never serve from `r2.dev` (rate-limited). Always go through the Worker |
| **Cutout paths** | R2 credentials without `R2_PUBLIC_BASE` store `cutout_path` as a relative `/cutouts/<hash>` that resolves to nothing — and `image_cutouts` is idempotent, so those images are never retried. `remove_backgrounds.py` now refuses to start in that state; keep the guard, and keep the secret set in CI |
| **Cutouts in CI** | They run once in the **report** job, not per category. Only that job holds the R2 secrets — running rembg in a scrape job writes local paths on an ephemeral runner. Scrape jobs pass `--no-cutouts` |
| **Bootstrap snapshots** | Store plain JSON in R2. Pre-gzipping plus `Content-Encoding: gzip` gets double-compressed by Cloudflare and breaks `response.json()` |
| **Crawl rate** | Don't raise `max-parallel: 4` in `daily-scrape.yml`, and don't shorten the 2–3 s page sleep. Getting blocked ends the product |
| **Dead listings** | Migration v8 stops expired listings counting as current. They were winning the headline price on 41% of GPUs. Preserve expiry in any change to "current price" logic |
| **Windows encoding** | The pipeline prints `→ ✓ ৳`; consoles default to cp1252. `run_pipeline.py` forces UTF-8 for itself and children — don't remove that |
| **AI honesty** | The agent may only speak through the six tools in `tools.py`. Add a tool, never loosen the prompt. A hallucinated price is a P0 bug |
