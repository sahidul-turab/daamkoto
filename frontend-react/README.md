# DaamKoto — React Frontend

The **only** frontend for DaamKoto, built with **React 18 + TypeScript + Tailwind
CSS v4 + Vite 6**. It talks to the FastAPI backend in `../backend/`.

> The old Streamlit app has been **removed**. Any doc calling it a "fallback" is
> out of date.

Project-wide context lives at the repo root: [README](../README.md) ·
[PRD](../PRD.md) · [ARCHITECTURE](../ARCHITECTURE.md) · [CLAUDE.md](../CLAUDE.md).

## Run it

Two processes.

**1. Backend** (from the project root, venv active):

```bash
uvicorn backend.main:app --reload --port 8000
```

**2. Frontend** (from this folder):

```bash
npm install      # first time only
npm run dev
```

Open **http://127.0.0.1:5173** (prefer `127.0.0.1` over `localhost` — IPv6-first
resolution on Windows adds ~200 ms per connection).

In dev, Vite proxies every `/api/*` request to `http://127.0.0.1:8000`, so there
are no CORS issues and the app uses clean same-origin URLs.

## Build / deploy

```bash
npm run build    # type-checks (tsc -b) then bundles to dist/
npm run preview  # serve the production build locally
```

Deployed on **Vercel** with root directory `frontend-react`. Set `VITE_API_BASE`
(e.g. `https://daamkoto-api.onrender.com`, no trailing slash) — it is baked in at
**build** time, so changing it requires a redeploy.

## Views

`browse | build | deals | scraper`, defined in `components/Header.tsx`.

| View | What it does |
|---|---|
| **Browse** | Category tabs, filter sidebar, product grid, price-age badges |
| **Build** | Slot-based PC assembly, compatibility report, wattage gauge, 3D rig preview |
| **Deals** | Biggest recent price drops, derived from price history |
| **Scraper** | Freshness grid, run history, manual trigger, log console |

Overlays: product drawer, chatbot, ⌘K command palette, watchlist — all lazy-loaded.

## How it maps to the backend

| UI piece | Endpoint |
|---|---|
| Category tabs | `CATEGORIES` in `src/config.ts` (mirrors `run_pipeline.py` db names) |
| Brand dropdown | `GET /brands?category=` |
| Spec filter options | `GET /specs/values?category=&key=` (live, with static fallback) |
| Product grid | `GET /products` (all filters as query params) |
| Drawer listings | `product.listings[]` from the same payload |
| Per-seller spec diff | `GET /products/{id}/seller-specs` |
| Price-history chart | `GET /products/{id}/history` |
| Deals feed | `GET /deals` |
| Chatbot | `POST /chat` |
| Build compatibility | `POST /build/check`, `POST /build/plan` |
| Watchlist / alerts | `POST`/`GET`/`DELETE /alerts` |
| Scraper dashboard | `GET /scrapers/status`, `POST /scrapers/run` |

**`src/config.ts` is the one file to edit** when the backend gains a category or
filter. It holds the 24 `CATEGORIES` (with per-category filters), `RETAILER_COLORS`,
and `PAGE_SIZE`.

> Category `icon` values are **lucide-react component names**
> (`"MemoryStick"`, `"Gamepad2"`, …) resolved by `components/Icon.tsx` — not emoji.

## Project layout

```
src/
  api.ts              Typed fetch client for the FastAPI backend
  config.ts           24 categories, per-category filters, retailer colors, PAGE_SIZE
  types.ts            TypeScript mirror of the Pydantic response models
  index.css           Design tokens + Tailwind theme (dark premium look)
  App.tsx             State orchestration; lazy-loads everything but Browse
  components/
    Header.tsx            Logo, global search, view switcher
    CategoryTabs.tsx      Animated switcher (prefetches on pointer-enter)
    FilterSidebar.tsx     Multi-select spec filters
    FilterChips.tsx       Active-filter pills
    ProductGrid.tsx       Card grid, skeletons, empty state
    ProductCard.tsx       Cutout image, cheapest price, savings + price-age badge
    ProductDrawer.tsx     Listings, spec diff, history chart        (lazy)
    PriceHistoryChart.tsx Recharts multi-retailer line chart
    PriceSpread.tsx       Min→max price bar
    Pagination.tsx        Prev/next pager
    Chatbot.tsx           Agent panel; rich blocks + UI actions     (lazy)
    CommandPalette.tsx    ⌘K navigation                             (lazy)
    WatchlistPanel.tsx    Saved products                            (lazy)
    DealsView.tsx         Price-drop feed                           (lazy)
    ScraperDashboard.tsx  Health dashboard                          (lazy)
    Icon.tsx              lucide-react icon resolver
    build/
      BuildStudio.tsx     Slot-based assembly                       (lazy)
      SlotPicker.tsx      Per-slot part chooser
      CompatReport.tsx    Issues from /build/check
      WattageGauge.tsx    Estimated draw → recommended PSU size
      Rig3D.tsx           3D rig preview (three.js / react-three-fiber)
  lib/
    swr.ts              Memory + sessionStorage cache, in-flight dedupe
    prefetch.ts         Next page, hovered category, idle warm
    useProductSearch.ts Seeds from cache during render; guards the unbounded query
    useUrlFilters.ts    Filter state ↔ URL
    useWatchlist.ts     localStorage watchlist
    useBuild.ts         Build state
    filterDefaults.ts   Default sort — must match backend _WARM_SORTS
    compat.ts, tdp.ts   Client-side compatibility hints
    basket.ts, buildConfig.ts, format.ts, useCountUp.ts
```

## ⚠️ Performance rules

Critical-path JS is **~68.5 kB gzip** (down from 225 kB). Two easy ways to undo that:

1. **Do not add `manualChunks` to `vite.config.ts`.** Naming `recharts` /
   `framer-motion` chunks makes Vite emit `<link rel="modulepreload">` in
   `index.html`, so every first-time visitor downloads ~190 kB gzip of chart and
   animation code before a single price renders.
2. **Do not statically import a lazy component into the Browse path.** One
   top-level `import { ProductDrawer }` in `App.tsx` drags framer-motion back onto
   the critical path.

Verify after any bundling change:

```bash
npm run build && grep -E "modulepreload|<script" dist/index.html
```

The entry should preload nothing large. Full reasoning in
[ARCHITECTURE.md §7](../ARCHITECTURE.md#7-performance-architecture).

On a first visit, `src/lib/bootstrap.ts` races the live `/products` request with
a database-generated first-page snapshot served from Cloudflare R2. The edge
copy paints immediately if Render/Neon are asleep; the live response silently
replaces it when ready. Only default, unfiltered page-one queries use snapshots.
