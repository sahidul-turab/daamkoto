"""
FastAPI backend for DaamKoto — PC component price comparison for Bangladesh.

Endpoints:
  GET /health                  — liveness check
  GET /categories              — list all product categories
  GET /brands?category=RAM     — list brands (optionally for one category)
  GET /retailers               — list known retailers
  GET /products                — search/filter products (see query params below)
  GET /products/{id}           — single product with all current listings
  GET /products/{id}/history   — full price history for one product

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
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend import chatbot, database, queries
from backend.cache import (
    brands_cache,
    history_cache,
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

    # Clear in-memory caches so fresh prices appear immediately after the run
    product_list_cache.invalidate_all()
    brands_cache.invalidate_all()
    spec_cache.invalidate_all()

    with _active_runs_lock:
        _active_runs.pop(category, None)


# ---------------------------------------------------------------------------
# App lifecycle — init / close connection pool
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool(min_conn=1, max_conn=10)
    # Fix any RUNNING rows left behind by a previous server crash
    try:
        with database.get_db() as conn:
            stale = queries.cleanup_stale_runs(conn)
            if stale:
                _log.info("Marked %d stale RUNNING run(s) as FAILED on startup", stale)
    except Exception:
        pass  # scraper_runs table may not exist yet — migration not applied
    yield
    database.close_pool()


app = FastAPI(
    title="DaamKoto API",
    description="Compare PC part prices across 13 Bangladeshi retailers",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow Streamlit (or any local frontend) to call this API without CORS errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
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


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    params: dict                     # filter params Claude extracted
    products: list[ProductSummary]   # database results
    total: int
    explanation: str                 # Claude's brief explanation


class RunRequest(BaseModel):
    category: str
    retailers: list[str] = []        # empty → all retailers


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/categories", response_model=list[str])
def list_categories():
    """All product categories in the database (e.g. RAM, GPU, SSD)."""
    with database.get_db() as conn:
        return queries.get_categories(conn)


@app.get("/brands", response_model=list[str])
def list_brands(category: str | None = Query(None, description="Filter brands by category")):
    """All brands, optionally narrowed to one category."""
    key = brands_cache.make_key(category)
    cached = brands_cache.get(key)
    if cached is not None:
        return cached
    with database.get_db() as conn:
        result = queries.get_brands(conn, category=category)
    brands_cache.set(key, result)
    return result


@app.get("/retailers")
def list_retailers():
    """All known retailers."""
    with database.get_db() as conn:
        return queries.get_retailers(conn)


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
    cache_key = spec_cache.make_key(category, key)
    cached = spec_cache.get(cache_key)
    if cached is not None:
        return cached
    with database.get_db() as conn:
        result = queries.get_spec_values(conn, category, key)
    spec_cache.set(cache_key, result)
    return result


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
    cached = product_list_cache.get(cache_key)
    if cached is not None:
        return cached

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
    result = {"total": total, "limit": limit, "offset": offset, "products": products}
    product_list_cache.set(cache_key, result)
    return result


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
    cache_key = seller_specs_cache.make_key(product_id)
    cached = seller_specs_cache.get(cache_key)
    if cached is not None:
        return cached

    # No existence check here: this endpoint is prefetched in parallel for every
    # visible product (~20 per page). get_seller_specs returns {} for an unknown
    # id, which diff turns into empty lists — a valid, cheap response. Skipping
    # the full get_product() aggregation halves the DB work for this hot path.
    with database.get_db() as conn:
        seller_data = queries.get_seller_specs(conn, product_id)
        result = queries.diff_seller_specs(seller_data)

    response = {
        "product_id": product_id,
        "retailers": result["retailers"],
        "shared": result["shared"],
        "differing": result["differing"],
    }
    seller_specs_cache.set(cache_key, response)
    return response


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
    cache_key = history_cache.make_key(product_id, retailer, limit)
    cached = history_cache.get(cache_key)
    if cached is not None:
        return cached

    with database.get_db() as conn:
        product = queries.get_product(conn, product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        history = queries.get_price_history(
            conn, product_id, retailer=retailer, limit=limit
        )
    response = {
        "product_id": product_id,
        "product_name": product["name"],
        "history": history,
    }
    history_cache.set(cache_key, response)
    return response


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
    Natural-language product search powered by Claude.

    Send a plain-English query; Claude extracts filter params; the database
    returns real prices. Claude never invents prices — it only generates
    query parameters.

    Example body: {"message": "find 16GB DDR4 RAM under 5000 taka"}
    """
    history = [{"role": m.role, "content": m.content} for m in req.history]

    try:
        params, explanation = chatbot.translate_to_params(req.message, history=history)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not params:
        return {"params": {}, "products": [], "total": 0, "explanation": explanation}

    # Build specs_filter from any spec-level params the chatbot extracted
    _SPEC_KEYS = {
        "speed", "latency", "form_factor", "vram", "chipset", "chipset_brand",
        "memory_type", "interface", "socket", "series", "architecture",
        "ram_type", "wifi", "nand_type", "wattage", "efficiency", "modularity",
        "type", "radiator_size", "side_panel", "color",
        "resolution", "refresh_rate", "panel_type",
    }
    specs_filter = {k: v for k, v in params.items() if k in _SPEC_KEYS and v is not None}

    with database.get_db() as conn:
        products, total = queries.search_products(
            conn,
            category=params.get("category"),
            brand=params.get("brand"),
            generation=params.get("generation"),
            capacity=params.get("capacity"),
            specs_filter=specs_filter or None,
            min_price=params.get("min_price"),
            max_price=params.get("max_price"),
            in_stock_only=params.get("in_stock_only", True),
            sort=params.get("sort", "price_asc"),
            limit=20,
            offset=0,
        )

    return {
        "params": params,
        "products": products,
        "total": total,
        "explanation": explanation,
    }
