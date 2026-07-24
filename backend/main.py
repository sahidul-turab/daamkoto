"""
FastAPI backend for DaamKoto — PC component price comparison for Bangladesh.

Endpoints:
  GET  /health                      — liveness check
  GET  /categories                  — list all product categories
  GET  /brands?category=RAM         — list brands (optionally for one category)
  GET  /retailers                   — list known retailers
  GET  /products                    — search/filter products (see query params below)
  GET  /products/{id}               — single product with all current listings
  GET  /products/{id}/history       — full price history for one product
  POST /chat                        — agentic AI assistant (multi-tool, free LLMs)
  GET  /deals                       — biggest recent price drops across all retailers
  POST /build/plan                  — AI build-from-budget
  POST /build/check                 — compatibility check for a set of part IDs
  POST /alerts                      — create a price-drop alert
  GET  /alerts?device_id=X          — list alerts for a device
  DELETE /alerts/{id}?device_id=X   — delete an alert
  GET  /alerts/triggered?device_id=X — alerts that have fired

Running locally:
  uvicorn backend.main:app --reload --port 8000

Then open: http://localhost:8000/docs  (Swagger UI — interactive API explorer)
"""

import io
import logging
import re
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend import agent as agent_mod, database, queries
from backend.cache import (
    brands_cache,
    deals_cache,
    history_cache,
    invalidate_everything,
    meta_cache,
    product_list_cache,
    seller_specs_cache,
    spec_cache,
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_log = logging.getLogger("scheduler")

# All retailer slugs (mirrors run_pipeline.py)
_ALL_RETAILERS = [
    "startech", "ryans", "techland", "potakait", "ucc",
    "ultratech", "binarylogic", "skyland", "creatus",
    "selltech", "computersource", "trusttech", "pchouse",
]

# In-process run registry — category → run_id
_active_runs: dict[str, int] = {}
_active_runs_lock = threading.Lock()

_LOG_PATH = Path("logs/scheduler.log")


# ---------------------------------------------------------------------------
# Background pipeline worker
# ---------------------------------------------------------------------------

def _read_log_tail(n: int = 120) -> str:
    if not _LOG_PATH.exists():
        return ""
    try:
        lines = _LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def _run_pipeline_bg(run_id: int, category: str, retailers: list[str]) -> None:
    """Subprocess the pipeline, log output, and record the result in scraper_runs."""
    _LOG_PATH.parent.mkdir(exist_ok=True)
    cmd = [sys.executable, "run_pipeline.py", "--category", category,
           "--retailers"] + retailers

    products_count = 0
    prices_count = 0
    error_msg: str | None = None
    status = "FAILED"

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        out = proc.stdout
        if proc.stderr.strip():
            out += "\n" + proc.stderr

        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"\n{'='*60}\n")
            fh.write(
                f"[run_id={run_id}] {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                f"category={category} retailers={retailers}\n"
            )
            fh.write(out)
            fh.write("\n")

        if proc.returncode != 0:
            error_msg = f"Pipeline exited with code {proc.returncode}"
        else:
            status = "SUCCESS"
            m = re.search(r"Products\s+inserted\s*:\s*(\d+)", out)
            if m:
                products_count = int(m.group(1))
            m = re.search(r"Prices\s+inserted\s*:\s*(\d+)", out)
            if m:
                prices_count = int(m.group(1))

    except Exception as exc:
        error_msg = str(exc)
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"[run_id={run_id}] EXCEPTION: {exc}\n")

    try:
        with database.get_db() as conn:
            queries.update_scraper_run(
                conn, run_id, status, products_count, prices_count, error_msg
            )
    except Exception as exc:
        _log.error("Failed to update scraper_run %d: %s", run_id, exc)

    # Clear in-memory caches so fresh prices appear immediately after the run,
    # then immediately re-warm so the next visitor doesn't pay for the cold cache.
    invalidate_everything()
    threading.Thread(target=_warm_caches, daemon=True).start()

    with _active_runs_lock:
        _active_runs.pop(category, None)


# ---------------------------------------------------------------------------
# Cache warmup
# ---------------------------------------------------------------------------

# Category tabs in frontend-react/src/config.ts order — the first entry is the
# default landing view, so warming follows the same order users arrive in.
_WARM_CATEGORIES = [
    "RAM DESKTOP", "RAM LAPTOP", "GPU", "PROCESSOR", "MOTHERBOARD",
    "SSD", "PORTABLE SSD", "HDD", "PORTABLE HDD", "PSU",
    "CPU COOLER", "CASING COOLER", "CASING",
]

# These must mirror frontend-react/src/config.ts (PAGE_SIZE) and
# src/lib/filterDefaults.ts (sort) — a mismatch would warm cache keys that no
# real request ever asks for, leaving every visitor on the slow path.
_WARM_PAGE_SIZE = 20
_WARM_SORTS = ("store_count_desc", "price_asc")


def _warm_product_page(conn, category: str, sort: str) -> dict:
    products, total = queries.search_products(
        conn, category=category, in_stock_only=True, sort=sort,
        limit=_WARM_PAGE_SIZE, offset=0,
    )
    return {"total": total, "limit": _WARM_PAGE_SIZE, "offset": 0,
            "products": products}


def _warm_caches() -> None:
    """
    Pre-populate the response cache with the queries real users make first.

    Without this, the first visitor after every deploy or cold start pays the
    full aggregation cost on whatever category they land on — and on Render's
    free tier that is exactly the visitor who already waited for a cold boot.
    Runs on a background thread, so it never delays the server becoming ready.
    """
    try:
        with database.get_db() as conn:
            meta_cache.warm(meta_cache.make_key("categories"),
                            lambda: queries.get_categories(conn))
            meta_cache.warm(meta_cache.make_key("retailers"),
                            lambda: queries.get_retailers(conn))

            for cat in _WARM_CATEGORIES:
                for sort in _WARM_SORTS:
                    key = product_list_cache.make_key(
                        None, cat, None, None, None, None, None, None,
                        True, sort, _WARM_PAGE_SIZE, 0,
                    )
                    product_list_cache.warm(
                        key, lambda c=cat, s=sort: _warm_product_page(conn, c, s)
                    )
                brands_cache.warm(brands_cache.make_key(cat),
                                  lambda c=cat: queries.get_brands(conn, category=c))
        _log.info("Cache warmup complete (%d categories)", len(_WARM_CATEGORIES))
    except Exception as exc:
        _log.warning("Cache warmup skipped: %s", exc)


# ---------------------------------------------------------------------------
# App lifecycle — init / close connection pool
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # min_conn=3: opening a connection to a managed Postgres (Neon, Singapore)
    # costs a TLS handshake worth ~100ms+. Keeping a few open means the first
    # requests after boot never pay it.
    database.init_pool(min_conn=3, max_conn=10)
    # Fix any RUNNING rows left behind by a previous server crash
    try:
        with database.get_db() as conn:
            stale = queries.cleanup_stale_runs(conn)
            if stale:
                _log.info("Marked %d stale RUNNING run(s) as FAILED on startup", stale)
    except Exception:
        pass  # scraper_runs table may not exist yet — migration not applied

    # Fill the response cache in the background so the first real visitor gets
    # a cache hit instead of a cold aggregation.
    threading.Thread(target=_warm_caches, daemon=True).start()

    yield
    database.close_pool()


app = FastAPI(
    title="DaamKoto API",
    description="Compare PC part prices across 13 Bangladeshi retailers",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
#
# Starlette applies middleware outermost-last, so the response travels:
#   route → cache headers → gzip → CORS → client
# ---------------------------------------------------------------------------

# How long a browser may reuse a response without asking again, per path prefix.
# Prices only move when the scraper pipeline runs (at most a few times a day),
# so short max-age plus a long stale-while-revalidate window gives instant
# repeat loads while keeping data effectively current.
_CACHEABLE: tuple[tuple[str, str], ...] = (
    ("/products",       "public, max-age=120, stale-while-revalidate=600"),
    ("/categories",     "public, max-age=900, stale-while-revalidate=3600"),
    ("/brands",         "public, max-age=900, stale-while-revalidate=3600"),
    ("/retailers",      "public, max-age=900, stale-while-revalidate=3600"),
    ("/specs/values",   "public, max-age=900, stale-while-revalidate=3600"),
    ("/deals",          "public, max-age=300, stale-while-revalidate=1800"),
)

# Never cache these — they report live state and must not be served stale.
_NO_STORE_PREFIXES = ("/scrapers", "/alerts", "/chat", "/build", "/health")


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    """
    Attach Cache-Control to read-only data endpoints.

    This is what stops a returning visitor from re-fetching the same product
    list on every navigation and page refresh — the browser serves it from disk
    with no network request at all, and any CDN in front can do the same.
    """
    response = await call_next(request)

    if request.method != "GET" or response.status_code != 200:
        return response

    path = request.url.path
    if path.startswith(_NO_STORE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
        return response

    # GZipMiddleware sits outside this one and sets Vary: Accept-Encoding itself
    # whenever it compresses, so there is nothing to add here.
    for prefix, value in _CACHEABLE:
        if path.startswith(prefix):
            response.headers["Cache-Control"] = value
            break

    return response


# Compress JSON responses. A 20 KB product page drops to roughly 3 KB, which is
# the difference that shows up on a mobile connection.
app.add_middleware(GZipMiddleware, minimum_size=800)

# Allow the deployed frontend (or any local dev server) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class Listing(BaseModel):
    retailer: str
    price_bdt: float | None
    in_stock: bool
    stock_status: str = "in_stock"  # in_stock | out_of_stock | upcoming | bundle_only
    pc_bundle_only: bool = False
    product_url: str | None
    scraped_at: Any  # datetime — keep as Any to avoid timezone parsing edge cases


class ProductSummary(BaseModel):
    id: int
    name: str
    brand: str | None
    match_key: str
    model_number: str | None
    category: str | None
    specs: dict
    cheapest_price: float | None
    cheapest_retailer: str | None
    retailer_count: int
    listings: list[Listing]


class ProductDetail(ProductSummary):
    pass  # same fields — kept separate for future additions


class PricePoint(BaseModel):
    retailer: str
    price_bdt: float | None
    in_stock: bool
    scraped_at: Any


class ProductHistory(BaseModel):
    product_id: int
    product_name: str
    history: list[PricePoint]


class ProductList(BaseModel):
    total: int
    limit: int
    offset: int
    products: list[ProductSummary]


class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class ChatContext(BaseModel):
    """Optional UI context sent from the frontend with each chat turn."""
    category: str | None = None            # currently-browsed category
    filters: dict | None = None            # active filter params
    build_slots: dict | None = None        # {slot: product_id} for current build


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    context: ChatContext | None = None


class ChatResponse(BaseModel):
    text: str                            # agent's natural-language answer
    blocks: list[dict] = []             # rich UI blocks (product_list, build_sheet, etc.)
    actions: list[dict] = []            # UI directives (apply_filters, add_to_build, etc.)
    # Legacy fields kept for backward compat
    params: dict = {}
    products: list[Any] = []
    total: int = 0
    explanation: str = ""


class BuildPlanRequest(BaseModel):
    budget_bdt: float
    use_case: str = "balanced"
    socket_preference: str | None = None
    include_gpu: bool = True


class BuildCheckRequest(BaseModel):
    cpu_id: int | None = None
    mobo_id: int | None = None
    ram_id: int | None = None
    gpu_id: int | None = None
    psu_id: int | None = None
    case_id: int | None = None
    cooler_id: int | None = None
    storage_id: int | None = None


class AlertCreate(BaseModel):
    device_id: str
    product_id: int
    target_price: float


class RunRequest(BaseModel):
    category: str
    retailers: list[str] = []        # empty → all retailers


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health(deep: bool = Query(False, description="Also round-trip the database")):
    """
    Liveness check. Stays dependency-free by default so a database blip never
    makes the platform restart a perfectly healthy web process.

    `?deep=1` additionally touches the database. The keep-warm cron uses that
    form so a managed Postgres with idle auto-suspend stays awake too — a
    suspended database is a multi-second stall for whoever arrives next.
    """
    if not deep:
        return {"status": "ok"}

    started = time.monotonic()
    try:
        with database.get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        db_ok = True
        db_error = None
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "db_error": db_error,
        "db_ms": round((time.monotonic() - started) * 1000, 1),
        "cache_warm": product_list_cache.size(),
    }


@app.get("/categories", response_model=list[str])
def list_categories():
    """All product categories in the database (e.g. RAM, GPU, SSD)."""
    def load():
        with database.get_db() as conn:
            return queries.get_categories(conn)
    return meta_cache.get_or_load(meta_cache.make_key("categories"), load)


@app.get("/brands", response_model=list[str])
def list_brands(category: str | None = Query(None, description="Filter brands by category")):
    """All brands, optionally narrowed to one category."""
    def load():
        with database.get_db() as conn:
            return queries.get_brands(conn, category=category)
    return brands_cache.get_or_load(brands_cache.make_key(category), load)


@app.get("/retailers")
def list_retailers():
    """All known retailers."""
    def load():
        with database.get_db() as conn:
            return queries.get_retailers(conn)
    return meta_cache.get_or_load(meta_cache.make_key("retailers"), load)


@app.get("/specs/values", response_model=list[str])
def get_spec_values(
    category: str = Query(..., description="Category to query, e.g. RAM, GPU, Motherboard"),
    key: str = Query(..., description="Spec key to get values for, e.g. speed, chipset, socket"),
):
    """
    Return all distinct values for a spec filter key within a category.
    Use this to populate filter dropdowns dynamically.

    Examples:
      /specs/values?category=RAM&key=speed          → ["1600MHz","2400MHz","3200MHz",...]
      /specs/values?category=GPU&key=chipset_brand  → ["AMD","Intel","NVIDIA"]
      /specs/values?category=Motherboard&key=socket → ["AM4","AM5","LGA1700",...]
      /specs/values?category=PSU&key=efficiency     → ["80+ Bronze","80+ Gold",...]
    """
    def load():
        with database.get_db() as conn:
            return queries.get_spec_values(conn, category, key)
    return spec_cache.get_or_load(spec_cache.make_key(category, key), load)


@app.get("/products", response_model=ProductList)
def list_products(
    # ── Core filters (work across all categories) ───────────────────────────
    search: str | None = Query(None, description="Free-text search on product name, brand, or model"),
    category: str | None = Query(None, description="e.g. RAM, GPU, SSD, Motherboard, PSU, Cooler, Casing, Monitor"),
    brand: str | None = Query(None, description="Card/module brand, e.g. Kingston, ASUS, Corsair"),
    min_price: float | None = Query(None, ge=0, description="Minimum price in BDT"),
    max_price: float | None = Query(None, ge=0, description="Maximum price in BDT"),
    in_stock_only: bool = Query(True, description="Only return products currently in stock"),
    sort: str = Query(
        "price_asc",
        description="Sort order: price_asc | price_desc | store_count_desc | savings_desc | name",
        pattern="^(price_asc|price_desc|store_count_desc|savings_desc|name)$",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    # ── RAM filters ─────────────────────────────────────────────────────────
    capacity: str | None = Query(None, description="[RAM/SSD/HDD] Storage/memory size, e.g. 8GB, 16GB, 1TB"),
    generation: str | None = Query(None, description="[RAM] DDR generation: DDR4, DDR5"),
    speed: str | None = Query(None, description="[RAM] Clock speed, e.g. 3200MHz, 4800MHz"),
    latency: str | None = Query(None, description="[RAM] CAS latency, e.g. CL16, CL36"),
    form_factor: str | None = Query(None, description="[RAM/Mobo/Case/PSU] e.g. Desktop, Laptop, ATX, Mid Tower"),
    heatsink: bool | None = Query(None, description="[RAM] Has heatsink/heat spreader"),
    ecc: bool | None = Query(None, description="[RAM] ECC error-correcting memory"),
    # ── GPU filters ─────────────────────────────────────────────────────────
    vram: str | None = Query(None, description="[GPU] Video memory size, e.g. 8GB, 12GB, 16GB"),
    chipset: str | None = Query(None, description="[GPU/Mobo] GPU chipset (RTX 4070) or mobo chipset (Z790, B760)"),
    chipset_brand: str | None = Query(None, description="[GPU] GPU manufacturer: NVIDIA, AMD, Intel"),
    memory_type: str | None = Query(None, description="[GPU] VRAM type: GDDR6, GDDR6X, GDDR7"),
    interface: str | None = Query(None, description="[GPU/SSD] PCIe interface or NVMe Gen: NVMe Gen4, PCIe 4.0 x16"),
    # ── CPU filters ─────────────────────────────────────────────────────────
    socket: str | None = Query(None, description="[CPU/Mobo] CPU socket: LGA1700, LGA1851, AM4, AM5"),
    series: str | None = Query(None, description="[CPU] CPU series: Core i5, Core i7, Ryzen 5, Ryzen 7"),
    architecture: str | None = Query(None, description="[CPU] Microarchitecture: Raptor Lake, Zen 4, Arrow Lake"),
    cores: str | None = Query(None, description="[CPU] Core count, e.g. 6, 8, 12, 16"),
    boost_clock: str | None = Query(None, description="[CPU] Boost/turbo clock, e.g. 5.4GHz"),
    cache: str | None = Query(None, description="[CPU/HDD] L3 cache or HDD buffer, e.g. 36MB, 256MB"),
    # ── Motherboard filters ──────────────────────────────────────────────────
    ram_type: str | None = Query(None, description="[Mobo] Supported RAM type: DDR4, DDR5"),
    wifi: bool | None = Query(None, description="[Mobo] Has built-in WiFi"),
    m2_slots: str | None = Query(None, description="[Mobo] Number of M.2 slots, e.g. 2, 3, 4"),
    # ── SSD filters ─────────────────────────────────────────────────────────
    nand_type: str | None = Query(None, description="[SSD] NAND flash type: TLC, QLC, MLC"),
    # ── PSU filters ─────────────────────────────────────────────────────────
    wattage: str | None = Query(None, description="[PSU] Power output, e.g. 650W, 750W, 850W"),
    efficiency: str | None = Query(None, description="[PSU] 80+ rating: 80+ Bronze, 80+ Gold, 80+ Platinum"),
    modularity: str | None = Query(None, description="[PSU] Fully Modular, Semi-Modular, Non-Modular"),
    atx30: bool | None = Query(None, description="[PSU] ATX 3.0 / PCIe 5.0 ready (12VHPWR connector)"),
    # ── Cooler filters ───────────────────────────────────────────────────────
    cooler_type: str | None = Query(None, alias="type", description="[Cooler] Air or AIO 240mm / AIO 360mm"),
    radiator_size: str | None = Query(None, description="[Cooler] AIO radiator size: 120mm, 240mm, 360mm"),
    # ── Case filters ─────────────────────────────────────────────────────────
    side_panel: str | None = Query(None, description="[Case] Side panel: Tempered Glass, Mesh, Solid"),
    color: str | None = Query(None, description="[Case] Chassis color: Black, White, Silver"),
    front_usb_c: bool | None = Query(None, description="[Case] Has front panel USB Type-C"),
    # ── Monitor filters ──────────────────────────────────────────────────────
    resolution: str | None = Query(None, description="[Monitor] e.g. 1920x1080, 2560x1440, 3840x2160"),
    refresh_rate: str | None = Query(None, description="[Monitor] e.g. 60Hz, 144Hz, 240Hz"),
    panel_type: str | None = Query(None, description="[Monitor] IPS, VA, TN, OLED"),
):
    """
    Search and filter products. Returns current cheapest price per product across all retailers.

    Category-specific filter params are applied via JSONB specs matching — pass only the params
    relevant to your chosen category; unrecognised combinations return no results.

    Examples:
      /products?category=RAM&generation=DDR5&capacity=16GB&max_price=8000
      /products?category=GPU&chipset_brand=NVIDIA&vram=8GB&sort=price_asc
      /products?category=Motherboard&socket=AM5&ram_type=DDR5&wifi=true
      /products?category=PSU&wattage=750W&efficiency=80%2B+Gold&modularity=Fully+Modular
      /products?category=Monitor&resolution=2560x1440&refresh_rate=144Hz&panel_type=IPS
    """
    # Build specs_filter from all category-specific params
    specs_filter: dict = {}
    for key_name, value in [
        ("speed", speed),
        ("latency", latency),
        ("form_factor", form_factor),
        ("heatsink", heatsink),
        ("ecc", ecc),
        ("vram", vram),
        ("chipset", chipset),
        ("chipset_brand", chipset_brand),
        ("memory_type", memory_type),
        ("interface", interface),
        ("socket", socket),
        ("series", series),
        ("architecture", architecture),
        ("cores", cores),
        ("boost_clock", boost_clock),
        ("cache", cache),
        ("ram_type", ram_type),
        ("wifi", wifi),
        ("m2_slots", m2_slots),
        ("nand_type", nand_type),
        ("wattage", wattage),
        ("efficiency", efficiency),
        ("modularity", modularity),
        ("atx30", atx30),
        ("type", cooler_type),
        ("radiator_size", radiator_size),
        ("side_panel", side_panel),
        ("color", color),
        ("front_usb_c", front_usb_c),
        ("resolution", resolution),
        ("refresh_rate", refresh_rate),
        ("panel_type", panel_type),
    ]:
        if value is not None:
            specs_filter[key_name] = value

    cache_key = product_list_cache.make_key(
        search, category, brand, generation, capacity,
        specs_filter or None, min_price, max_price,
        in_stock_only, sort, limit, offset,
    )
    def load():
        with database.get_db() as conn:
            products, total = queries.search_products(
                conn,
                search=search,
                category=category,
                brand=brand,
                generation=generation,
                capacity=capacity,
                specs_filter=specs_filter or None,
                min_price=min_price,
                max_price=max_price,
                in_stock_only=in_stock_only,
                sort=sort,
                limit=limit,
                offset=offset,
            )
        return {"total": total, "limit": limit, "offset": offset, "products": products}

    return product_list_cache.get_or_load(cache_key, load)


@app.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int):
    """
    Full details for one product: specs, all current retailer listings, and prices.
    """
    with database.get_db() as conn:
        product = queries.get_product(conn, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


class SellerSpecsResponse(BaseModel):
    product_id: int
    retailers: list[str]
    shared: dict       # {spec_key: value} — same across all retailers with data
    differing: dict    # {spec_key: {retailer: value_or_None}}


@app.get("/products/{product_id}/seller-specs", response_model=SellerSpecsResponse)
def get_seller_specs(product_id: int):
    """
    Per-retailer raw spec data for one product, split into:
      shared    — specs where all retailers agree on the value
      differing — specs where values differ between retailers (or only some have it)

    Only populated after running the pipeline with the updated normalize.py that
    emits seller_raw_specs (enrich.py detail-page specs + inline_specs from listing scrapers).
    """
    # No existence check here: get_seller_specs returns {} for an unknown id,
    # which diff turns into empty lists — a valid, cheap response. Skipping the
    # full get_product() aggregation halves the DB work for this path.
    def load():
        with database.get_db() as conn:
            seller_data = queries.get_seller_specs(conn, product_id)
            result = queries.diff_seller_specs(seller_data)
        return {
            "product_id": product_id,
            "retailers": result["retailers"],
            "shared": result["shared"],
            "differing": result["differing"],
        }

    return seller_specs_cache.get_or_load(
        seller_specs_cache.make_key(product_id), load
    )


@app.get("/products/{product_id}/history", response_model=ProductHistory)
def get_price_history(
    product_id: int,
    retailer: str | None = Query(None, description="Filter to one retailer"),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Full price history for one product — every scrape run's price point.
    Use this data to draw a price-over-time chart in the frontend.

    Example: /products/42/history?retailer=StarTech
    """
    def load():
        with database.get_db() as conn:
            product = queries.get_product(conn, product_id)
            if product is None:
                raise HTTPException(
                    status_code=404, detail=f"Product {product_id} not found"
                )
            history = queries.get_price_history(
                conn, product_id, retailer=retailer, limit=limit
            )
        return {
            "product_id": product_id,
            "product_name": product["name"],
            "history": history,
        }

    return history_cache.get_or_load(
        history_cache.make_key(product_id, retailer, limit), load
    )


@app.get("/scrapers/status")
def scraper_status():
    """
    Dashboard endpoint — returns:
      • active_runs   : {category: run_id} for any in-process pipeline threads
      • recent_runs   : last 15 rows from scraper_runs
      • freshness     : per-retailer last_scraped, product count, price-row count
      • log_tail      : last ~120 lines of logs/scheduler.log
    """
    try:
        with database.get_db() as conn:
            runs      = queries.get_scraper_runs(conn, limit=15)
            freshness = queries.get_retailer_freshness(conn)
    except Exception:
        runs      = []
        freshness = []

    with _active_runs_lock:
        active = dict(_active_runs)

    return {
        "active_runs":  active,
        "recent_runs":  runs,
        "freshness":    freshness,
        "log_tail":     _read_log_tail(120),
    }


@app.post("/scrapers/run")
def trigger_run(req: RunRequest):
    """
    Trigger a background pipeline run for one category.

    Returns 409 if a run for the same category is already in flight.
    Retailers default to all 13 if not specified.

    Example body: {"category": "ram", "retailers": ["startech", "ryans"]}
    """
    retailers = req.retailers or _ALL_RETAILERS

    # In-memory guard (fast path — catches threads started by *this* server process)
    with _active_runs_lock:
        if req.category in _active_runs:
            raise HTTPException(
                status_code=409,
                detail=f"A run for '{req.category}' is already active "
                       f"(run_id={_active_runs[req.category]})",
            )

    # DB guard (catches runs started by the scheduler daemon or another process)
    try:
        with database.get_db() as conn:
            existing = queries.get_active_run(conn, req.category)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"A run for '{req.category}' is already RUNNING in the DB "
                           f"(run_id={existing['id']})",
                )
            run_id = queries.create_scraper_run(conn, req.category, retailers)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB error: {exc}")

    with _active_runs_lock:
        _active_runs[req.category] = run_id

    threading.Thread(
        target=_run_pipeline_bg,
        args=(run_id, req.category, retailers),
        daemon=True,
    ).start()

    return {
        "run_id":    run_id,
        "status":    "RUNNING",
        "category":  req.category,
        "retailers": retailers,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Agentic AI assistant — multi-tool, multi-step.

    The agent can search products, get price history, check compatibility,
    plan a full PC build from budget, and return UI action directives
    (apply filters, add to build, open product). All powered by free LLMs
    (Groq llama-3.3-70b for fast search, Gemini 2.0 Flash for reasoning).

    Example body:
      {"message": "Build me a 90000 taka gaming PC"}
      {"message": "Find cheap RTX 4060 and check if prices dropped"}

    The response includes:
      text    — natural-language answer
      blocks  — typed rich payloads: product_list, build_sheet, compat_report, etc.
      actions — UI directives the frontend should execute
    """
    history = [{"role": m.role, "content": m.content} for m in req.history]
    context = req.context.model_dump() if req.context else {}

    try:
        with database.get_db() as conn:
            result = agent_mod.run(
                message=req.message,
                history=history,
                context=context,
                conn=conn,
            )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        # Rate-limit / quota errors — surface as a chat message, not a 500
        msg = str(exc)
        return {
            "text": msg, "blocks": [], "actions": [],
            "params": {}, "products": [], "total": 0, "explanation": msg,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    # Populate legacy fields for backward compatibility with older frontend builds
    products: list = []
    total = 0
    explanation = result.get("text", "")
    for block in result.get("blocks", []):
        if block.get("type") == "product_list" and not products:
            products = block.get("products", [])
            total = block.get("total", len(products))
        elif block.get("type") == "build_sheet" and not products:
            products = [
                {"id": s["product_id"], "name": s["product_name"],
                 "brand": s.get("brand"), "cheapest_price": s.get("cheapest_price")}
                for s in block.get("slots", [])
            ]
            total = len(products)

    return {
        "text": result.get("text", ""),
        "blocks": result.get("blocks", []),
        "actions": result.get("actions", []),
        # Legacy
        "params": {},
        "products": products,
        "total": total,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Deals feed
# ---------------------------------------------------------------------------

@app.get("/deals")
def get_deals(
    category: str | None = Query(None, description="Filter deals by category"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Biggest recent price drops across all retailers.
    Each entry includes: product info, current vs previous price, drop amount and %.
    """
    def load():
        with database.get_db() as conn:
            deals = queries.get_deals(conn, category=category, limit=limit)
        return {"deals": deals, "count": len(deals)}

    return deals_cache.get_or_load(deals_cache.make_key(category, limit), load)


# ---------------------------------------------------------------------------
# Build endpoints (callable directly, not just via chat)
# ---------------------------------------------------------------------------

@app.post("/build/plan")
def plan_build(req: BuildPlanRequest):
    """
    Generate a full PC build within a budget.

    Allocates budget across CPU, GPU, Mobo, RAM, Storage, PSU, Case, Cooler —
    picks cheapest compatible parts from the DB, runs compatibility checks.

    Example body: {"budget_bdt": 90000, "use_case": "gaming"}
    """
    from backend import tools as tools_mod
    with database.get_db() as conn:
        result = tools_mod._handle_plan_build(
            conn,
            budget_bdt=req.budget_bdt,
            use_case=req.use_case,
            socket_preference=req.socket_preference,
            include_gpu=req.include_gpu,
        )
    return result


@app.post("/build/check")
def check_compatibility(req: BuildCheckRequest):
    """
    Check compatibility between PC parts by product ID.

    Checks: CPU↔Mobo socket, RAM gen↔Mobo, Mobo↔Case size, PSU wattage, AIO fit.
    Pass only the slots you want to check — missing slots are skipped.

    Example body: {"cpu_id": 42, "mobo_id": 77, "ram_id": 15}
    """
    from backend import compat as compat_mod
    slot_map = {
        "cpu": req.cpu_id, "mobo": req.mobo_id, "ram": req.ram_id,
        "gpu": req.gpu_id, "psu": req.psu_id, "case": req.case_id,
        "cooler": req.cooler_id, "storage": req.storage_id,
    }
    with database.get_db() as conn:
        products = {
            slot: queries.get_product(conn, pid)
            for slot, pid in slot_map.items() if pid
        }
    result = compat_mod.evaluate_build(products)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.post("/alerts")
def create_alert(req: AlertCreate):
    """
    Create or update a price-drop alert. Fires when current price ≤ target_price.
    device_id is a client-generated UUID stored in localStorage (no auth required).
    """
    with database.get_db() as conn:
        alert = queries.create_alert(conn, req.device_id, req.product_id, req.target_price)
    return alert


@app.get("/alerts")
def list_alerts(device_id: str = Query(..., description="Client device UUID")):
    """List all active and triggered alerts for this device."""
    with database.get_db() as conn:
        return queries.list_alerts(conn, device_id)


@app.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int, device_id: str = Query(..., description="Client device UUID")):
    """Delete a price-drop alert."""
    with database.get_db() as conn:
        deleted = queries.delete_alert(conn, device_id, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"deleted": True}


@app.get("/alerts/triggered")
def get_triggered_alerts(device_id: str = Query(..., description="Client device UUID")):
    """Get alerts that have fired (price reached target). Used for UI badge."""
    with database.get_db() as conn:
        return queries.get_triggered_alerts(conn, device_id)
