# DaamKoto — Product Requirements Document

**Status:** Live in production · **Last updated:** 2026-08-01
**Owner:** Sahidul Turab (solo builder)

> This document describes *what the product is and why*. For *how it is built*,
> see [ARCHITECTURE.md](ARCHITECTURE.md). For *what changed and why*, see
> [IMPROVEMENTS.md](IMPROVEMENTS.md).

---

## 1. Problem

A Bangladeshi buying PC parts today has to open a dozen browser tabs — StarTech,
Ryans, Techland, UCC, PotakaIT and so on — and manually compare the same GPU
across all of them. The prices genuinely differ, often by 10–20%, so the tab-hopping
is not optional if you care about money. Three specific pains:

1. **No single view.** Nobody aggregates local retailers with current prices.
2. **No price history.** You cannot tell whether today's ৳52,000 GPU is a good
   deal or a post-hike price. Retailers show only "now".
3. **Search is keyword-only.** Every shop's search is a string match. You cannot
   ask "16GB DDR5 under 6000 taka that isn't RGB".

The incumbent, **PCPartPickerBD**, partially solves (1) but has no history, no
natural-language layer, and thinner retailer coverage.

## 2. Product vision

> One page where a Bangladeshi PC buyer sees every local shop's price for the
> part they want, what that part used to cost, and can simply *ask* for what
> they need in plain Bangla-English.

## 3. Target users

| User | Need | Primary feature |
|---|---|---|
| **Budget builder** (student, first PC) | Maximum specs for a fixed budget | AI build planner, Deals feed |
| **Upgrader** | Is now a good time to buy this one part? | Price history chart, price alerts |
| **Bargain hunter** | Where is this exact SKU cheapest right now? | Cross-retailer listing comparison |
| **Browser / researcher** | Explore what exists in a category | Faceted spec filters |

**Builder profile note:** the maintainer is a data-science student with basic
Python and hands-on Playwright experience, and is weak on frontend. Decisions
should be explained, not just implemented. Prefer boring, readable solutions
over clever ones.

## 4. Core principles (non-negotiable)

1. **The database answers, the LLM only understands.** The AI translates
   language into structured queries and narrates real rows. It must never
   generate a price, a product name, or a stock status from its own weights.
   Every number a user sees traces back to a scraped row.
2. **Prices are append-only.** A price row is never updated or deleted. History
   is the product's moat and is the one thing that cannot be re-derived later.
3. **Polite crawling.** 2–3 s between page requests, robots.txt respected. The
   retailers are the data source; getting blocked ends the product.
4. **Fast for a cold visitor on Bangladeshi mobile data.** Performance is a
   feature, not a polish item. See the hot-path rules in `CLAUDE.md`.
5. **Free tier only.** The whole stack (Neon + Render + Vercel + GitHub Actions
   + Cloudflare R2 + Groq + Gemini) must cost ৳0/month.

## 5. Scope

### 5.1 Retailers — 15, all live

StarTech, Ryans, Techland BD, PotakaIT, UCC, UltraTech, BinaryLogic, Skyland,
Creatus, SellTech, ComputerSource, TrustTech, PCHouse, EZGadgets, VibeGaming.

Coverage is deliberately uneven: **SellTech** and **PCHouse** are peripheral-and-
GPU shops, and **EZGadgets** is peripherals-led with a thin core-component
range, so they only have scrapers where they actually sell. See the coverage matrix in [ARCHITECTURE.md](ARCHITECTURE.md#scraper-coverage-matrix).

### 5.2 Categories — 24 live

**Core components (13):** RAM Desktop, RAM Laptop, GPU, Processor, Motherboard,
SSD, Portable SSD, HDD, Portable HDD, PSU, CPU Cooler, Casing Cooler, Casing.

**Peripherals & lifestyle (11):** Monitor, Keyboard, Mouse, Headphone, UPS,
Speaker, Webcam, Gaming Chair, Printer, Mouse Pad, Gamepad.

> `odd` (optical drives) is registered as a pipeline choice but **has zero
> scrapers** — it is a dead option, not a live category.

### 5.3 Out of scope (deliberate)

- **Buying / checkout.** DaamKoto links out to the retailer. No cart, no payments.
- **User accounts.** Watchlist and alerts key off an anonymous device ID in
  localStorage. No signup wall, no passwords to leak.
- **Laptops, phones, pre-built PCs.** Components and peripherals only.
- **Real-time prices.** Data refreshes daily. The UI is honest about age via
  staleness badges rather than pretending to be live.

## 6. Feature requirements

### F1 — Browse & compare *(shipped)*
- Category tabs across 24 categories, each with its own faceted filter set.
- Per-category spec filters driven by **71 whitelisted JSONB spec keys**
  (multi-select, numerically sorted, live values from the DB with static fallback).
- Global filters: brand, price range, in-stock only, search, sort.
- Product card shows the canonical name, a **cutout image**, the cheapest price,
  how many stores carry it, the savings vs. the most expensive listing, and a
  **price-age badge** (green / amber / red) so stale data is never disguised.
- Product drawer: every retailer's listing side by side, price-spread bar,
  per-seller raw spec comparison (shared vs. differing), and a full history chart.
- **Requirement:** a listing that a retailer has stopped selling must stop
  counting as a current price (see [IMPROVEMENTS.md](IMPROVEMENTS.md) — dead-listing expiry).

### F2 — Price history *(shipped)*
- Every scrape appends a row; nothing is overwritten.
- `GET /products/{id}/history` returns the full series, rendered as a
  multi-retailer Recharts line chart in the drawer.

### F3 — Agentic AI assistant *(shipped)*
- `POST /chat`, backed by a **6-tool agent loop**:
  `search_products`, `get_product_details`, `get_price_history`,
  `check_compatibility`, `plan_build`, `get_deals`.
- Two-tier model routing: **Groq llama-3.3-70b** for fast retrieval,
  **Gemini 2.0 Flash** for multi-step reasoning, with automatic fallback when a
  key is missing or rate-limited.
- Replies render as **rich blocks** (product cards, charts) and can **drive the
  UI** — e.g. apply filters, open a product, switch views.

### F4 — Build studio *(shipped)*
- Slot-based PC assembly (CPU, motherboard, RAM, GPU, storage, PSU, cooler, case).
- **Compatibility engine** (`backend/compat.py`): socket match, RAM generation vs.
  board, GPU/case clearance, PSU headroom via a TDP table, form-factor fit.
- **Wattage gauge** — estimated draw rounded up to a real PSU size.
- **3D rig preview** (`Rig3D.tsx`, three.js / react-three-fiber).
- `POST /build/plan` — AI builds a parts list from a budget and use case.
- `POST /build/check` — validate any set of part IDs.

### F5 — Deals feed *(shipped)*
- `GET /deals` ranks the biggest recent price drops across all retailers,
  computed from price history rather than a retailer's own "sale" label.

### F6 — Price alerts & watchlist *(shipped, partly gated)*
- `POST /alerts` create · `GET /alerts` list · `DELETE /alerts/{id}` ·
  `GET /alerts/triggered`. Anonymous, keyed by device ID.
- Watchlist panel in the frontend.
- **Gap:** `migration_v6_alerts.sql` is not confirmed applied to the production
  Neon database — alerts may be inert in production. Verify before promoting.

### F7 — Product images *(shipped)*
- Retailer photos have a white background baked in, which looks broken on a dark
  UI. `scripts/remove_backgrounds.py` runs **rembg** to produce transparent PNGs,
  uploads them to **Cloudflare R2**, and serves them through a Worker.
- Runs automatically at the end of every pipeline load; skippable with `--no-cutouts`.

### F8 — Scraper health dashboard *(shipped)*
- `GET /scrapers/status` — per-retailer freshness grid, run history, log tail.
- `POST /scrapers/run` — trigger a background run, concurrency-safe.
- Every run is recorded in the `scraper_runs` table.

### F9 — Automated daily refresh *(shipped)*
- GitHub Actions runs the full sweep at 20:00 UTC (02:00 Dhaka) **as a matrix**,
  4 categories in parallel, writing directly to Neon. No local machine involved.
- `keep-warm.yml` pings `/health?deep=1` during Bangladeshi waking hours.
- `weekly-backup.yml` dumps the database Sundays as a 90-day artifact.
- After each sweep, database-generated first pages for all 24 categories are
  published to Cloudflare R2. A cold visitor sees this edge snapshot while the
  browser wakes and revalidates Render/Neon in the background.

## 7. Non-functional requirements

| Requirement | Target | Current status |
|---|---|---|
| Critical-path JS | < 70 kB gzip | **~68.5 kB** ✅ |
| Warm API response | < 300 ms | ~250 ms ✅ |
| Products visible with API cold | < 2 s | ~1.2–1.8 s in production via edge snapshot ✅ |
| Category revisit | Zero network requests | client SWR cache ✅ |
| Crawl politeness | 2–3 s between pages, ≤4 concurrent crawlers per shop | ✅ |
| Monthly cost | ৳0 | ✅ (Render 608 h of 750 budget) |
| Data freshness | Daily | ✅, surfaced honestly via badges |

## 8. Known gaps / roadmap

**Correctness & completeness**
- [ ] Confirm `migration_v6_alerts.sql` is applied to production Neon (F6).
- [ ] Fill scraper coverage gaps — notably `gamepad` (6 retailers missing),
      `mousepad` (6), `webcam` (4). See the matrix in ARCHITECTURE.md.
- [ ] Remove or implement the dead `odd` category choice in `run_pipeline.py`.

**Product**
- [ ] Bangla-language UI and Bangla NL queries in the chatbot.
- [ ] Price-drop email/push notification delivery (alerts currently only surface in-app).
- [ ] Public price-history API / shareable deep links for a specific part.
- [ ] "Best time to buy" signal derived from the history series.

**Engineering hygiene**
- [ ] Root directory holds one-off scripts from early exploration
      (`probe_*.py`, `wipe_gpu.py`, `rerun_all_fixed.py`, `check_*.py`) plus a
      17 MB `daamkoto_db_dump.sql`. Worth moving to `scripts/archive/` or deleting.
- [ ] No automated test suite. Highest-value first target: `cleaning/normalize.py`,
      which is 84 KB of regex-driven spec extraction and the single most
      breakage-prone file in the project.

## 9. Success metrics

Since there is no analytics stack yet, these are the intended measures:

1. **Coverage** — products with ≥3 retailer listings (the comparison is only
   useful when multiple shops carry the item).
2. **Freshness** — % of listings scraped within 24 h.
3. **Match quality** — false merges (two different SKUs folded into one product)
   and false splits (one SKU appearing as several products).
4. **Speed** — time to first product on screen for a cold mobile visitor.
5. **AI trust** — zero hallucinated prices. Any occurrence is a P0 bug.
