# PC Component Price Comparison — Bangladesh

## Vision
A website where Bangladeshi PC buyers can search for a component (e.g. RAM, GPU, SSD) and instantly see its price compared across multiple local retailers (StarTech, Ryans, Techland, and others). The user finds the cheapest source in one place instead of tab-hopping.

**Edge over PCPartPickerBD**: an AI chatbot layer — users can ask in plain language ("find me 16GB DDR4 RAM under 4000 taka") and the bot translates that into a structured database query. The LLM understands; the database answers; the bot never invents prices.

Also stores price history (append-only timestamps) so users can see how prices changed over time.

---

## User / collaborator profile
- Data science student, Bangladesh
- Knows Python at a basic level; has hands-on Playwright experience
- Weak on web frontend — React frontend is now the primary UI
- Wants explanations of decisions, not just code drops

---

## Retailers in scope (13 total)
1. **StarTech** — `startech.com.bd`
2. **Ryans** — `ryans.com`
3. **Techland BD** — `techlandbd.com`
4. **PotakaIT** — `potakait.com`
5. **UCC** — `ucc.com.bd`
6. **UltraTech** — `ultratech.com.bd`
7. **BinaryLogic** — `binarylogic.com.bd`
8. **Skyland** — `skyland.com.bd`
9. **Creatus** — `creatus.com.bd`
10. **SellTech** — `selltech.com.bd` (GPU only)
11. **ComputerSource** — `computersource.com.bd`
12. **TrustTech** — `trusttechbd.com`
13. **PCHouse** — `pchouse.com.bd` (GPU only)

---

## Architecture (5 stages)

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
- `POST /chat` — Claude AI chatbot (translates NL → query params)
- `GET /scrapers/status` — freshness, run history, log tail
- `POST /scrapers/run` — trigger a background pipeline run (concurrency-safe)

### Stage 5 — Frontend (`frontend-react/`)
**React + Vite + Tailwind CSS v4** premium dark UI. Three views:
- **Browse** — category tabs, filter sidebar, product grid with price-age badges
- **Build** — PC parts assembly studio with compatibility check and cost estimate
- **Scraper** — health dashboard (freshness grid, run history, manual trigger, log console)

> The old Streamlit frontend has been removed. `frontend-react/` is the only frontend.

### Stage 5b — Scraper Automation (`scheduler.py`)
Background daemon that cycles through all 13 categories in round-robin order.
- Logs to `logs/scheduler.log` (also readable from the Scraper dashboard)
- Records every run in `scraper_runs` PostgreSQL table
- FastAPI backend can also trigger runs via `POST /scrapers/run`

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
| AI chatbot | Anthropic Claude API |
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

```bash
# Use the Python helper (psql not required in PATH):
python -c "
import os; from dotenv import load_dotenv; import psycopg2
load_dotenv()
conn = psycopg2.connect(host=os.getenv('DB_HOST','localhost'), port=int(os.getenv('DB_PORT','5432')), dbname=os.getenv('DB_NAME','pc_comparison'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD',''))
conn.autocommit = True
cur = conn.cursor()
cur.execute(open('database/migration_v5_scraper_runs.sql').read())
print('Done!')
conn.close()
"
```

Migration files (apply in order):
1. `database/schema.sql` — base schema (already applied)
2. `database/migration_v3_stock_status.sql`
3. `database/migration_v4_pc_bundle_only.sql`
4. `database/migration_v5_scraper_runs.sql` — scraper run history table

---

## Scraper automation

```bash
# Run all categories once (good for testing):
python scheduler.py --once

# Run specific categories / retailers:
python scheduler.py --once --categories ram gpu --retailers startech ryans

# Full daemon mode (sweeps all 13 categories every 12 hours):
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
- [x] AI chatbot layer (Claude API) — translates NL → query params
- [x] Ryans scraper — 154 products, 8 pages, Cloudflare bypass
- [x] Rich category-specific specs: JSONB specs dict; GIN index; 20+ filter params
- [x] Expanded to 13 categories (RAM Desktop, RAM Laptop, GPU, Processor, Motherboard, SSD, Portable SSD, HDD, Portable HDD, PSU, CPU Cooler, Casing Cooler, Casing)
- [x] New scrapers: Ryans, Techland, UCC, UltraTech, BinaryLogic, PotakaIT (all categories)
- [x] 6 new retailers: Skyland, Creatus, SellTech, ComputerSource, TrustTech, PCHouse
- [x] database/load.py + run_pipeline.py updated for 13 retailers
- [x] GPU segmentation bug fixed — AMD RX 500-series 3-digit chipsets
- [x] Full category scrapers for Skyland + Creatus (gen_opencart_scrapers.py)
- [x] Full category scrapers for TrustTech + ComputerSource
- [x] Price-age staleness badges on product cards (green/amber/red)
- [x] Scraper Health Dashboard in React (freshness grid, run history, manual trigger, log)
- [x] scheduler.py daemon — round-robin categories, 12h cycle, DB run tracking
- [x] database/migration_v5_scraper_runs.sql — scraper_runs table
- [x] Streamlit frontend removed — React is the sole frontend
- [ ] Run pipeline for all categories across all 13 retailers to fully populate DB
- [ ] Techland scrapers for remaining categories (casing, laptop_ram, portable_hdd, portable_ssd)
- [ ] StarTech scrapers for new categories (laptop_ram, casing_cooler, portable_hdd, portable_ssd)

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
Add every filterable spec key from your cleaner to `_ALLOWED_SPEC_KEYS` (line ~22).
These are the keys the API will accept as filter params. Omitting them silently blocks filtering.
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
  icon: "🖥️",
  filters: [
    { kind: "select", param: "spec_key", label: "Label", specKey: "spec_key", fallback: ["Val1","Val2"] },
    { kind: "bool",   param: "has_feature", label: "Has Feature" },
  ],
},
```
Also add a color to `RETAILER_COLORS` if this doesn't already exist (it's per retailer, not category — skip if the retailers are already there).

### 8. Add to dashboard trigger list — `frontend-react/src/components/ScraperDashboard.tsx`
```typescript
const ALL_CATEGORIES = [
  "ram", ..., "casing",
  "your_new_category",   // ← add here
];
```

### 9. Update CLAUDE.md
- Add to **Retailers in scope** (if categories were limited per retailer)
- Add to **Build order checklist**
- Mark incomplete scrapers under remaining items

### Quick checklist for a new category
```
[ ] scrapers/{retailer}/scrape_{category}.py  — one per retailer
[ ] cleaning/normalize.py                     — clean_{category}_record() + dispatcher
[ ] run_pipeline.py                           — choices list + db_category dict
[ ] scheduler.py                              — CATEGORIES list
[ ] backend/queries.py                        — _ALLOWED_SPEC_KEYS
[ ] backend/main.py                           — Query params in GET /products + _SPEC_KEYS in /chat
[ ] frontend-react/src/config.ts              — CATEGORIES array (CategoryDef)
[ ] frontend-react/src/components/ScraperDashboard.tsx — ALL_CATEGORIES list
[ ] CLAUDE.md                                 — build order + notes
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
