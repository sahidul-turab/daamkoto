# DaamKoto — React Frontend

A premium, modern rewrite of the Streamlit UI, built with **React + TypeScript +
Tailwind CSS v4 + Vite**. It talks to the existing **FastAPI** backend — no
backend changes were needed. The old Streamlit app (`../frontend/app.py`) is left
untouched as a fallback.

## Run it

You need two processes running.

**1. Backend** (from the project root, with your venv active):

```bash
uvicorn backend.main:app --reload --port 8000
```

**2. Frontend** (from this `frontend-react/` folder):

```bash
npm install      # first time only
npm run dev
```

Then open **http://localhost:5173**.

In dev, Vite proxies every `/api/*` request to `http://127.0.0.1:8000`, so there
are no CORS issues and the frontend uses clean same-origin URLs.

## Build / deploy

```bash
npm run build    # type-checks (tsc) then bundles to dist/
npm run preview  # serve the production build locally
```

For a deployed backend, set `VITE_API_BASE` (e.g. `https://api.example.com`)
before building — see `src/api.ts`.

## How it maps to your data

Everything is driven by the backend contract in `backend/main.py`:

| UI piece | Backend endpoint |
|---|---|
| Category tabs | hard-coded list mirroring `CATEGORY_DB` |
| Brand dropdown | `GET /brands?category=` |
| Spec filter dropdowns | `GET /specs/values?category=&key=` (live, with static fallback) |
| Product grid | `GET /products` (all filters as query params) |
| Product drawer listings | `product.listings[]` from the same payload |
| Price-history chart | `GET /products/{id}/history` |
| "Ask AI" panel | `POST /chat` |

The 13 categories and every spec filter live in **`src/config.ts`** — that's the
one file to edit when the backend gains a new category or filter.

## Project layout

```
src/
  api.ts              Typed fetch client for the FastAPI backend
  config.ts           Categories, per-category filters, retailer colors, sort
  types.ts            TypeScript mirror of the Pydantic response models
  index.css           Design tokens + Tailwind theme (dark premium look)
  App.tsx             State orchestration (filters, paging, debounced fetch)
  components/
    Header.tsx          Logo + global search + Ask-AI button
    CategoryTabs.tsx    Animated category switcher
    FilterSidebar.tsx   Global + category-specific spec filters
    ProductGrid.tsx     Card grid, skeletons, empty state
    ProductCard.tsx     Floating card w/ cursor-spotlight + savings badge
    ProductDrawer.tsx   Slide-in: listing comparison + specs + history chart
    PriceHistoryChart.tsx  Recharts line chart (lazy-loaded)
    Chatbot.tsx         AI part-finder panel (calls /chat)
    Pagination.tsx      Prev/next pager
```
