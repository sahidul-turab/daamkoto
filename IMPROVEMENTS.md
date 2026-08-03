# DaamKoto — Improvement & Decision Log

**Why the system looks the way it does.** Every entry is *problem → change →
why it matters*, so a future maintainer (human or AI) can tell which decisions
are load-bearing and which are incidental.

For the current design, see [ARCHITECTURE.md](ARCHITECTURE.md). For where it's
going, see [PRD.md](PRD.md).

---

## Timeline at a glance

| Period | Theme |
|---|---|
| Foundation | Pipeline built and proven end-to-end on StarTech RAM |
| Expansion | 13 retailers × 13 core categories, rich JSONB specs |
| **2026-05-30** | Rebrand to DaamKoto, deployed live on free tiers |
| **2026-07-24** | Data-correctness fixes, performance pass, agentic AI, full automation |
| **2026-07-24–25** | 11 new peripheral categories (13 → 24) |
| **2026-07-25–26** | Product images: rembg cutouts + Cloudflare R2 |
| **2026-07-26** | Multi-select filters, Ryans URL incident + repair, Windows/Neon hardening |
| **2026-08-01** | First-visit cold start made non-blocking (edge snapshots) |
| **2026-08-03** | EZ Gadgets added — 14th retailer, first read via an API |

---

## 1. Foundation — getting one category right first

**Decision: prove the whole chain on a single retailer and category before
scaling out.** StarTech RAM went scrape → enrich → normalize → match → load →
API → UI first. Only once 408 products and 121 prices were verified end-to-end
did the second retailer get written.

*Why it matters:* every structural mistake — spec key naming, `match_key` shape,
the append-only price rule — would have been 13× more expensive to fix after
fan-out. The shape of `specs` chosen here is still the shape used by all 24
categories today.

**Decision: prices are append-only, never updated.**

*Why it matters:* this is the product's moat. Today's price can always be
re-scraped; what a GPU cost on 15 June cannot be recovered once overwritten. It
also makes the loader idempotent and gives the history chart, deals feed and
alerts a free data source. Every read path pays for this by having to resolve
"current" via `scraped_at DESC` — which is exactly what `mv_current_prices`
pre-computes.

**Decision: two-stage matching — MPN exact, then fuzzy, folded with union-find.**

*Why it matters:* manufacturer part numbers are the only truly reliable identity,
but most BD retailers don't publish them. Fuzzy-only matching produces false
merges; MPN-only produces false splits. Doing exact first and fuzzy second within
the same `match_key` bucket keeps both error rates low. Union-find handles the
transitive case (A≈B, B≈C ⇒ one product).

---

## 2. Expansion — 13 retailers, rich specs

**Added:** Ryans, Techland, UCC, UltraTech, BinaryLogic, PotakaIT, then Skyland,
Creatus, SellTech, ComputerSource, TrustTech, PCHouse.

**Decision: code-generate scrapers for OpenCart shops.** Most Bangladeshi
retailers run OpenCart, so `gen_opencart_scrapers.py` produces the boilerplate
and only the category URLs and selectors get hand-edited.

*Why it matters:* ~257 scraper files exist. Writing each by hand was not viable.

**Ryans / Cloudflare:** Ryans sits behind a Cloudflare challenge. The working
technique is a **fresh browser context per page** — reusing one context makes
Cloudflare re-issue the challenge mid-scrape and the run dies.

*Why it matters:* this is non-obvious and costs performance, so it looks like
something worth "optimising away". It isn't. The same protection rate-limits
plain `curl`/`requests`, which is why backfill scripts also have to go through
Playwright.

**Decision: specs live in a JSONB column with a GIN index, not per-category
tables.** 24 categories with wildly different attributes (CAS latency vs. chair
footrest vs. printer duplex) would otherwise mean 24 schemas.

*Why it matters:* adding a category needs no migration. The cost is that filter
keys must be whitelisted in `_ALLOWED_SPEC_KEYS` — a key not in that set is
**silently ignored**, which is the single most common cause of "my new filter
does nothing".

**Fixed: GPU segmentation on AMD RX 500-series.** Three-digit chipset numbers
were mis-parsed, splitting one card across several products.

*Why it matters:* the bug class recurs every time a vendor invents a naming
convention. Treat `normalize.py` regexes as high-risk on any new product line.

---

## 3. 2026-05-30 — Live on free tiers

**Rebrand to DaamKoto** (দাম কত? — "what's the price?") and full deployment:
Vercel (frontend) + Render (backend) + Neon (PostgreSQL).

**Decision: `backend/database.py` prefers `DATABASE_URL`, falls back to discrete
`DB_*` vars.**

*Why it matters:* identical code runs on a laptop against local Postgres and on
Render against Neon. It also enables the "scrape straight into production" flow —
set `DATABASE_URL` locally and the pipeline writes to Neon with no other change.

**Decision: Streamlit frontend removed; React is the only UI.**

*Why it matters:* documentation in several places still described Streamlit as a
"fallback". It is gone. `frontend-react/` is the sole frontend.

---

## 4. 2026-07-24 — Data correctness

Three fixes in this batch changed what users *see*, not just how fast they see it.
These are the most important entries in this file.

### 4.1 Dead listings were winning the headline price *(migration v8)*

**Problem:** nothing ever expired a listing. When UltraTech stopped selling a
ZOTAC RTX 5060 at ৳44,999 in May, that row stayed "current" forever. Prices drift
upward, so **dead listings are systematically the cheapest ones** — they won the
headline "FROM" price on **41% of GPUs**, showing visitors a price nobody could
buy at, stamped "Updated 56d ago".

**Change:** a listing stops counting as current once the retailer stops carrying it.

*Why it matters:* this was silently destroying the core promise of the product —
that the cheapest price shown is real. Any future change to how "current" is
computed must preserve expiry.

### 4.2 Duplicate listings at one retailer *(migration v7)*

**Problem:** a retailer sometimes sells one product under two URLs at different
prices. Skyland listed the same AITC Kingsman DDR5 kit at both ৳70,200 and
৳17,500. The matcher correctly folded them into one product, but the view then
had two "current" prices for one retailer.

**Change:** when a retailer has several current listings for one product, take
the **cheapest**.

### 4.3 Freshness was over-reported

**Problem:** the freshness check counted every retailer, including ones a given
run never touched — so a partial run looked like a full refresh.

**Change:** scope the check to the retailers a run actually covered.

*Why it matters:* the staleness badges are the honesty mechanism for daily-refresh
data. If freshness lies, the badges lie.

---

## 5. 2026-07-24 — Performance pass

Critical-path JS went **225 kB → 64 kB gzip**. Five mechanisms, all documented in
[ARCHITECTURE.md §7](ARCHITECTURE.md#7-performance-architecture). The reasoning
behind the two counter-intuitive ones:

### 5.1 Removing `manualChunks` made it faster

**Problem:** forcing `recharts` and `framer-motion` into named chunks caused Vite
to emit `<link rel="modulepreload">` for them in `index.html`. Every first-time
visitor downloaded ~190 kB gzip of chart and animation code **before a single
price rendered**.

**Change:** deleted `manualChunks`; let Rollup derive chunks from the real import
graph, and lazy-load every view except Browse plus every overlay.

*Why it matters:* this looks like a performance *regression* in a diff ("you
removed chunk splitting"). It is the opposite. The rule is now a ⚠️ in both
`CLAUDE.md` and `ARCHITECTURE.md`. Verify with
`npm run build && grep modulepreload dist/index.html`.

### 5.2 The cache is stale-while-revalidate + single-flight, not a TTL dict

An expired entry is returned **immediately** while it refreshes on a background
thread, and N concurrent misses on one key run one query rather than N.

*Why it matters:* a plain TTL cache makes one unlucky user per interval pay the
full cold query, and a traffic spike on a cold key stampedes the database. The
consequence for callers: **the loader passed to `get_or_load` must open its own
connection**, because it can run after the request has already returned.

### 5.3 The unbounded query is refused, not optimised

A `/products` call with neither `category` nor `search` aggregates the entire
catalogue and is by far the slowest thing the API can do.

**Change:** `useProductSearch` refuses to issue it. Keep that guard.

### 5.4 Cold starts

Render free spins down after ~15 min idle (30–50 s cold start) and Neon suspends
an idle database, so a large share of real visitors were hitting a cold backend
*and* a cold database. `keep-warm.yml` pings `/health?deep=1` — `deep=1`
round-trips Postgres, because pinging only the web process would leave Neon free
to suspend underneath it.

**Budget reasoning:** Render allows 750 instance-hours/month against a ~730-hour
month, so 24/7 leaves no headroom. The cron runs 00:00–20:00 UTC = 06:00–02:00
Dhaka — every waking hour in Bangladesh, ~608 h/month.

### 5.5 `localhost` vs `127.0.0.1`

Windows resolves `localhost` to IPv6 first, adding ~200 ms per connection. That
alone accounted for the slow category switches during development. Always use
`127.0.0.1` locally.

---

## 6. 2026-07-24 — Agentic AI

**Problem:** the original chatbot translated natural language into query
parameters and nothing more. It could not answer "is this a good time to buy" or
"plan me a build".

**Change:** a real agent loop (`backend/agent.py`) over **six tools**
(`backend/tools.py`): `search_products`, `get_product_details`,
`get_price_history`, `check_compatibility`, `plan_build`, `get_deals`.

**Decision: the model may only speak through tools.** Every price, name and stock
status in a reply comes from a tool returning real database rows.

*Why it matters:* this is principle #1 of the product. A hallucinated price is a
P0 bug, not a quirk. Adding a capability means adding a *tool*, never loosening
the prompt.

**Decision: two-tier model routing.** Groq `llama-3.3-70b-versatile` for fast
retrieval, Gemini `2.0-flash` for multi-step reasoning, with automatic fallback
when a key is missing or rate-limited. A `_gemini_auth_ok` flag caches a failed
auth so the app stops retrying a bad key.

*Why it matters:* both are free tiers with real rate limits. Fallback is what
keeps the assistant answering instead of erroring. **Note:** this project does
**not** use the Anthropic API — older docs claimed it did, which was wrong.

**Also shipped in this batch:** the deals feed (`GET /deals`, ranked from price
history rather than retailer "sale" labels), price-drop alerts (anonymous, keyed
by a localStorage device ID — no accounts, no passwords to leak), and a chatbot
rebuilt to render rich blocks and drive the UI.

---

## 7. 2026-07-24 — Automation

**Problem:** refreshing prices meant running `python scheduler.py` on the
maintainer's PC. The site was only as fresh as the laptop was on.

**Change:** `daily-scrape.yml` runs the full pipeline against Neon at 20:00 UTC.

**Decision: run categories as a parallel matrix with `max-parallel: 4`.**

*Why it matters, in both directions:* sequentially a full sweep measured **4 h 02
m**, leaving no room under GitHub's 6 h job ceiling — hence parallelism. But
every category hits the **same 13 shops**, so N parallel jobs means N× the
request rate at each retailer. The scrapers sleep 2–3 s between pages precisely
to stay polite; running 13 at once would throw that away and invite a block.
Four keeps a sweep near an hour while no shop sees more than four concurrent
crawlers. **Do not raise this number to "speed things up".**

**Decision: serialise database writes and fail loudly when a category fails.**
Parallel scraping is fine; parallel loading is not.

**Added `weekly-backup.yml`** (Sundays 21:00 UTC, after Sunday's scrape).

*Why it matters:* prices are append-only and the history cannot be regenerated.
Before this, the only copy lived in Neon, whose free tier keeps just **6 hours**
of point-in-time restore — a bad migration or accidental `DROP` would have been
permanent. Dumps land as 90-day build artifacts.

---

## 8. 2026-07-24–25 — 13 → 24 categories

**Added:** Monitor, Keyboard, Mouse, Headphone, UPS (2026-07-24), then Speaker,
Webcam, Gaming Chair, Printer, Mouse Pad, Gamepad (2026-07-25).

*Why it matters:* it nearly doubled the catalogue (~35,000 products today) and
broadened the audience beyond core PC builders. Casing, Monitor and Keyboard are
now three of the four largest categories.

**Supporting change: `scrapers/category_urls.py`** records verified category URLs
and card selectors per retailer, so adding a category is a data edit rather than
site archaeology.

**Debt this created:** `_WARM_CATEGORIES` in `backend/main.py` was never updated
past the original 13, so the 11 new categories are **not pre-warmed** and their
first visitor after a deploy pays a cold aggregation. Still open — see
[PRD.md §8](PRD.md#8-known-gaps--roadmap). Coverage gaps also remain (`gamepad`
missing at 7 retailers, `mousepad` at 6, `webcam` at 5).

---

## 9. 2026-07-25–26 — Product images

**Problem:** retailer photos have a solid white background baked into the JPEG.
On the dark UI every card looked like a broken white rectangle.

**Change:** a cutout stage — download the image, run **rembg** to a transparent
PNG, upload to **Cloudflare R2**, serve through a Worker.

**Decision: key the cutout table on the source image URL.** `image_cutouts`
(migration v10) maps source URL → cutout path, and queries `LEFT JOIN` it.

*Why it matters:* the entire scrape → normalize → match → load chain needed **no
changes**. The stage is idempotent, re-runnable, and `run_pipeline.py` calls it
automatically with `fatal=False` so a cutout failure never blocks a price update.

**Decision: hotlink the retailer's original image, never copy the bytes.** Only
the derived cutout is self-hosted.

**Two operational traps, both learned the hard way:**

> **rembg OOMs above 6 workers on this machine and fails *silently*.** Twelve
> workers produce no error, just missing cutouts. Keep `--workers 6`.

> **Never serve from `r2.dev`** — it is aggressively rate-limited. Always go
> through the Worker (`scripts/r2_image_worker.js`).

---

## 10. 2026-07-26 — Filters, the Ryans incident, Windows hardening

### 10.1 Multi-select filters and dead spec keys

**Problem:** filters were single-select, options sorted as strings (so
`"1600MHz"` sorted after `"16000MHz"`), and several spec keys the cleaners
produced were never wired into `_ALLOWED_SPEC_KEYS` — those filters silently did
nothing.

**Change:** multi-select filters, numeric-aware option sorting
(`_natural_sort_key`), dead keys wired up, and a scrollbar on long filter lists.

*Why it matters:* the silent-failure mode is the important lesson. A filter that
does nothing looks identical to a filter with no matches. When adding a spec key,
`_ALLOWED_SPEC_KEYS` is the step that gets forgotten.

### 10.2 The Ryans URL incident

**Problem:** Ryans changed its markup and dropped the `product_slug` field the
scraper relied on. Every Ryans URL loaded as **NULL** — the "Buy" link went
nowhere for an entire retailer.

**Change:** extract the URL from the product card's anchor element instead
(`03ffbd1`), plus `scripts/backfill_ryans_urls.py` to repair the rows already
loaded, matching on `match_key`.

*Why it matters:* a scraper that returns *fewer fields* still "succeeds". Nothing
crashed; the data just quietly lost a column. Cloudflare also rate-limits `curl`,
so the backfill had to drive Playwright — the same constraint as the scraper.

### 10.3 Windows and Neon hardening

**Problem:** `run_pipeline.py` printed `→ ✓ ৳`, Windows consoles default to
cp1252, and a stray glyph could abort an entire run.

**Change:** force UTF-8 on the pipeline's own stdio and set `PYTHONIOENCODING`
for child processes. Loaders were also made DSN/Neon aware in the same pass.

*Why it matters:* an encoding crash mid-sweep looked like a scraper failure and
cost real debugging time.

---

## 11. Cross-cutting lessons

1. **Silent failures dominate.** Dead listings, ignored spec keys, dropped URL
   fields, rembg OOM — none raised an error. When something looks wrong, check
   for a quietly-missing value before assuming a crash.
2. **Politeness is a hard constraint, not a setting.** Sleep timings and
   `max-parallel: 4` exist so the shops don't block us. Getting blocked ends the
   product.
3. **"Optimisations" that add preloads or chunk names have made this site
   slower.** Measure with `grep modulepreload dist/index.html` before believing a
   bundling change helped.
4. **The LLM never sources facts.** Capabilities are added as tools.
5. **Documentation drifts fastest on counts.** "13 retailers" stayed accurate;
   "13 categories" silently became 24. Prefer generating counts from the code
   over restating them.

---

## 12. 2026-08-01 — First-visit cold start became non-blocking

**Problem:** the warm API responds in roughly 300 ms, but Render and Neon both
sleep on their free tiers. GitHub's nominal ten-minute keep-warm schedule was
observed starting only every one to three hours, so a new visitor could stare at
skeletons for one or two minutes while both services woke.

**Change:** `scripts/export_bootstrap_snapshots.py` publishes database-generated
first pages for every category and both default sorts to the existing Cloudflare
R2 Worker after each daily scrape. The frontend races that edge snapshot against
the live API, paints whichever arrives first, and always lets the API replace the
snapshot when ready. Backend startup now opens one connection instead of three,
moves housekeeping off the readiness path, and warms all 24 categories.

*Why it matters:* first paint no longer depends on a chain of best-effort cron →
Render → Neon. With the API forcibly offline, a clean browser rendered all 20
RAM cards from the production site in roughly 1.2–1.8 seconds.

**Operational trap:** store snapshot objects as plain JSON. Pre-gzipping the body
and setting `Content-Encoding: gzip` caused Cloudflare to gzip it again; browsers
decoded one layer and then failed `response.json()` on the remaining gzip bytes.

---

## 13. 2026-08-03 — EZ Gadgets, and the first shop we read via an API

**Added:** EZ Gadgets (`ggezgadgets.com`) as the 14th retailer — 14 categories,
595 live listings, competing on 182 products that other shops already carried.
It is peripherals-led: 199 keyboards and 169 mice against a single motherboard.
That shape is the point — it lands in `gamepad` and `mousepad`, the two thinnest
categories in the catalogue.

**Decision: read the WooCommerce Store API, not the rendered category pages.**

EZ Gadgets is the first WooCommerce shop here; the other thirteen are OpenCart or
bespoke themes, so there was no existing template to copy and the choice was open.
Both paths were built and compared on the same 199 keyboards: identical product
set, identical stock, identical images, and 3 price differences that resolved to
the shop editing its own catalogue during the 25 minutes between runs (one product
was deleted outright mid-comparison).

*Why the API won:* one call returns 100 products, so the keyboard category costs
2 requests instead of 10 full Woodmart page loads with their JS, CSS and images —
roughly 10 cheap requests per sweep in place of 38 heavy ones. Politeness is the
constraint that governs this whole project (it is why `max-parallel` stays at 4),
and this is the cheapest large win available on it. Reading WooCommerce's own data
instead of the theme's rendered archive also means a Woodmart upgrade cannot
silently change what we parse.

The DOM scraper is kept as a fallback and prints a loud banner if it ever runs.
A shop closing `/wp-json` must not look like a normal run — the same class of
silent failure as the Ryans URL incident (§10.2).

**Trap: an API is not automatically cleaner than a DOM.** WordPress stores post
titles as HTML, so the API returns `27&#8243;` and `Keyboard &#038; Mouse` where
`textContent` had silently decoded them. 58 of 1,033 names (5.6%) were affected.
This was not cosmetic: the product name feeds the fuzzy matcher and becomes the
canonical name shown in the UI, so it would have both split products and rendered
entity codes on the card. Names are `html.unescape`d on the way in.

**Decision: do not map the API's `sku` to `mpn`.** It is tempting — MPN is the
matcher's highest-confidence key and almost no BD retailer publishes one. But
these SKUs are the shop's own codes (`EWX75V2`), not manufacturer part numbers,
and an MPN is treated as an *exact* identity. Feeding it proprietary codes risks
fusing two unrelated products, which is worse than the fuzzy matching it replaces.

**Note on shop-side price errors:** the MSI RTX 5070 lists at ৳10,500 against
৳85,900+ everywhere else. The archive page, the Store API and the product page
markup all agree, so this is EZ Gadgets' own data entry, faithfully reported.
It is currently out of stock, so migration v8's expiry and the in-stock filters
keep it off the headline price — but it is a reminder that "the shop published
it" and "the price is real" are different claims.
