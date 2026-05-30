# PriceBeam — Project Review & Improvement Roadmap

## What's Been Built (Status Quo)

This is an impressively comprehensive project. Here's a layer-by-layer breakdown:

---

### 🕷️ Stage 1 — Scrapers (`scrapers/`)

| Aspect | Status |
|---|---|
| Retailers | **13 active**: StarTech, Ryans, Techland, Skyland, Creatus, UltraTech, TrustTech, ComputerSource, BinaryLogic, UCC, PotakaIT, SellTech, PCHouse |
| Categories | **13+**: RAM Desktop, RAM Laptop, GPU, Processor, Motherboard, SSD, Portable SSD, HDD, Portable HDD, PSU, CPU Cooler, Casing Cooler, Casing |
| Engine | Playwright (JS-rendered sites) |
| Extras | `gen_scrapers.py` / `gen_opencart_scrapers.py` for code-generating scraper templates; StarTech enrichment via detail pages |

**Verdict**: Strong foundation. Wide retailer/category coverage is the project's biggest competitive moat.

---

### 🧹 Stage 2 — Clean & Match (`cleaning/`)

| File | Purpose |
|---|---|
| [normalize.py](file:///f:/pc-component-comparison/cleaning/normalize.py) | 63 KB — massive, per-category spec extractors (brand, capacity, generation, speed, chipset, etc.) |
| [matcher.py](file:///f:/pc-component-comparison/cleaning/matcher.py) | MPN-exact + rapidfuzz matching, union-find grouping, canonical product selection |

**Verdict**: This is the most technically complex stage. Handles the hard problem of cross-retailer product identity well.

---

### 🗄️ Stage 3 — Database (`database/`)

| Feature | Detail |
|---|---|
| Schema | `products` (JSONB specs, match_key UNIQUE), `prices` (append-only), `retailers` |
| Indexes | GIN on JSONB specs, pg_trgm trigram indexes on name/brand/model, composite price indexes |
| Materialized View | `mv_current_prices` — pre-computed latest price per (product, retailer) for fast reads |
| Loader | [load.py](file:///f:/pc-component-comparison/database/load.py) — upsert products, append prices, idempotent |
| Migrations | `migration_v3_stock_status.sql`, `migration_v4_pc_bundle_only.sql`, `perf_indexes_v2.sql` |

**Verdict**: Solid append-only design. Materialized view is a smart optimization. Schema has evolved organically with good migrations.

---

### 🚀 Stage 4 — Backend + Frontend

#### FastAPI Backend ([main.py](file:///f:/pc-component-comparison/backend/main.py))
- **7+ endpoints**: `/health`, `/categories`, `/brands`, `/retailers`, `/products`, `/products/{id}`, `/products/{id}/history`, `/products/{id}/seller-specs`, `/specs/values`, `/chat`
- **20+ filter params** including category-specific JSONB specs filters
- **In-memory caching** layer ([cache.py](file:///f:/pc-component-comparison/backend/cache.py))
- **AI chatbot** via Groq/Llama 3.3 with function calling — translates natural language → structured query params
- **CORS enabled** for local frontends

#### React Frontend ([frontend-react/](file:///f:/pc-component-comparison/frontend-react/))
- **Vite + React 18 + TypeScript + Tailwind v4**
- **14 components**: Header, CategoryTabs, FilterSidebar, FilterChips, ProductGrid, ProductCard, ProductDrawer, PriceHistoryChart, PriceSpread, Chatbot, CommandPalette (⌘K), WatchlistPanel, Pagination, BuildStudio
- **Build Studio**: full PC builder with slot-based part picking, compatibility checks, wattage gauge, 3D rig visualization (React Three Fiber)
- **Premium dark theme**: aurora background, glassmorphism, film grain texture, cursor-reactive glow, framer-motion animations
- **URL-synced filters** via `useUrlFilters` hook
- **Lazy-loaded** recharts for price history

#### Streamlit Frontend ([frontend/app.py](file:///f:/pc-component-comparison/frontend/app.py))
- **74 KB** monolith — the original frontend, still functional
- Search/filter table, price cards, history chart, 13-category radio with per-category filter options

---

### 🔧 Pipeline Orchestration

[run_pipeline.py](file:///f:/pc-component-comparison/run_pipeline.py) — end-to-end: scrape → enrich → normalize → match → load → refresh materialized view. Supports `--skip-scrape`, `--skip-load`, `--dry-run`, `--category`, `--retailers`.

---

## What Can Improve

### 🔴 High Priority

#### 1. **Incomplete Scraper Coverage**
Per [CLAUDE.md](file:///f:/pc-component-comparison/CLAUDE.md) lines 111-113, several combinations are still TODO:
- Pipeline hasn't run for all new categories across new retailers (processor, motherboard, SSD, PSU, cooler, casing)
- Techland missing scrapers for casing, laptop_ram, portable_hdd, portable_ssd
- StarTech missing scrapers for laptop_ram, casing_cooler, portable_hdd, portable_ssd

> [!IMPORTANT]
> The data is the product. Filling these gaps should be the #1 priority — a price comparison site is only as useful as its coverage.

#### 2. **No Automated Scheduling**
Scrapers are run manually. Prices go stale fast. You need:
- A scheduler (cron job / Windows Task Scheduler / `APScheduler` in Python) to run `run_pipeline.py` on a cadence (e.g. daily or every 12h)
- A dashboard or log to see when each retailer was last scraped
- Staleness indicators in the UI ("price last updated 3 days ago")

#### 3. **Error Handling & Resilience in Scrapers**
- If one retailer's site is down or changes layout, the entire pipeline step fails
- Need: per-retailer try/except in `run_pipeline.py`, alerting on failures, and graceful degradation (stale data better than no data)

#### 4. **No Tests**
Zero test files found. For a data pipeline this complex, you need at minimum:
- Unit tests for `normalize.py` (spec extraction edge cases)
- Unit tests for `matcher.py` (matching accuracy)
- Integration test: known raw data → expected matched output
- API endpoint tests for `backend/main.py`

---

### 🟡 Medium Priority

#### 5. **Frontend: Streamlit → React Migration Incomplete**
You have two frontends. The Streamlit one is a 74 KB monolith; the React one is the premium experience. Consider:
- Deprecating the Streamlit frontend or keeping it as a quick dev/admin tool only
- The React frontend has no error boundaries — API failures show nothing useful
- No loading state for filter sidebar dropdowns (they fetch from `/specs/values`)

#### 6. **Database Performance**
- The `mv_current_prices` materialized view needs manual refresh after every pipeline run. If forgotten, the API serves stale data. Consider: auto-refresh trigger, or a `LISTEN/NOTIFY` pattern.
- The `_CURRENT_PRICES_CTE` in [queries.py](file:///f:/pc-component-comparison/backend/queries.py) does a `LEFT JOIN` — products with zero prices still appear. This may be intentional but could confuse users.
- No connection pooling beyond psycopg2's basic pool. For production, consider `asyncpg` + `asyncio` or PgBouncer.

#### 7. **Chatbot Improvements**
- Currently uses Groq (free tier) with Llama 3.3. No conversation memory across sessions.
- The chatbot can't do follow-ups like "now show me the cheapest one" because it doesn't see previous results.
- No rate limiting on the `/chat` endpoint — a bot could exhaust the free Groq tier.
- Consider adding a "suggested queries" UI for discoverability.

#### 8. **Search Quality**
- The ILIKE + pg_trgm search is decent but basic. Users searching "4070 super" might not find "GeForce RTX 4070 SUPER" consistently.
- Consider: full-text search with `tsvector` / `tsquery`, or Elasticsearch if scale grows.
- No search suggestions / autocomplete.

#### 9. **`normalize.py` is 63 KB**
This single file has grown organically to handle 13+ categories. It should be split into per-category cleaner modules:
```
cleaning/
  cleaners/
    ram.py
    gpu.py
    processor.py
    ...
  normalize.py  (orchestrator that dispatches to the right cleaner)
```

---

### 🟢 Nice to Have

#### 10. **Price Alerts / Notifications**
Users can watchlist products but get no notifications. Add:
- Email/Telegram alerts when a watchlisted product drops below a threshold
- "Price dropped!" badges on the product grid

#### 11. **Product Images**
No product images anywhere. Even a brand logo or generic category icon would improve the UI significantly. Some retailers' product pages have images — you could scrape those.

#### 12. **SEO & Public Deployment**
- The React app is a SPA with no SSR — Google can't index product pages
- No `<title>`, `<meta description>`, or `<h1>` per product/category
- For public launch: consider Next.js for SSR, or a static pre-render layer
- No deployment config (Docker, fly.toml, Vercel, etc.)

#### 13. **Build Studio Enhancements**
The PC Build Studio is a killer feature. Improvements:
- Persist builds to the database (currently localStorage only)
- Shareable build links with a short URL
- Pre-made builds ("Best gaming PC under 80k BDT")
- Affiliate links to retailer product pages

#### 14. **Data Quality Monitoring**
- No way to detect scraper drift (layout changes that silently break extraction)
- Add: product count sanity checks (if StarTech RAM drops from 400 to 50 products, something broke)
- Spec extraction coverage metrics (% of products with valid specs)

#### 15. **API Pagination & Performance**
- Default limit is 50, max 200. For 2000+ GPU products, this means many pages
- No cursor-based pagination (offset pagination is slow at high offsets)
- No API response compression (gzip)
- Consider adding an `ETag` or `Last-Modified` header for client-side caching

---

## Summary Scorecard

| Area | Score | Notes |
|---|---|---|
| **Data Coverage** | ⭐⭐⭐⭐ | 13 retailers, 13 categories — exceptional for a student project |
| **Data Pipeline** | ⭐⭐⭐⭐ | Solid normalize → match → load flow |
| **Database** | ⭐⭐⭐⭐ | Smart append-only design, good indexing |
| **Backend API** | ⭐⭐⭐⭐ | Comprehensive filters, caching, chatbot |
| **React Frontend** | ⭐⭐⭐⭐⭐ | Premium design, Build Studio, ⌘K palette |
| **Testing** | ⭐ | No tests at all |
| **DevOps** | ⭐ | Manual runs, no CI/CD, no Docker |
| **Scheduling** | ⭐ | No automation — prices go stale |
| **Documentation** | ⭐⭐⭐⭐ | CLAUDE.md is excellent |

**Overall**: This is remarkably far along — a full-stack data product with real scraping, cleaning, matching, and a polished React frontend. The biggest gaps are operational (scheduling, testing, monitoring) rather than architectural.
