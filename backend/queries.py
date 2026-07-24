"""
All database queries for the API.

Keeping SQL here (not inside route functions) means:
  - The AI chatbot layer can import and call these directly without HTTP round-trips
  - Queries are easy to test in isolation
  - Route functions stay thin

The "current price" concept:
  prices is append-only, so the most recent row per (product, retailer) pair
  is the current price. We use PostgreSQL's DISTINCT ON to get it efficiently.
  The _CURRENT_PRICES_CTE is included in every query that needs live prices.
"""

from __future__ import annotations

from datetime import datetime

import psycopg2.extras

# Spec keys that are allowed in filter conditions (prevents SQL injection via key names)
_ALLOWED_SPEC_KEYS = {
    # RAM
    "capacity", "generation", "speed", "latency", "form_factor", "kit", "rgb", "heatsink", "ecc",
    # GPU
    "vram", "chipset", "chipset_brand", "memory_type", "interface",
    # CPU
    "series", "model", "socket", "architecture", "cores", "boost_clock", "cache",
    # Motherboard
    "ram_type", "wifi", "m2_slots",
    # SSD / HDD
    "nand_type", "rpm",
    # PSU
    "wattage", "efficiency", "modularity", "atx30",
    # Cooler
    "type", "radiator_size", "fan_size",
    # Case
    "side_panel", "color", "psu_support", "front_usb_c",
    # Monitor
    "screen_size", "resolution", "refresh_rate", "panel_type", "response_time", "curved", "hdr",
}

# ---------------------------------------------------------------------------
# Shared CTE — used by multiple queries
# ---------------------------------------------------------------------------

_CURRENT_PRICES_CTE = """
WITH current_prices AS (
    SELECT product_id, retailer, price_bdt, in_stock, stock_status, pc_bundle_only, product_url, scraped_at
    FROM mv_current_prices
)
"""


# ---------------------------------------------------------------------------
# Search / list products
# ---------------------------------------------------------------------------

def search_products(
    conn,
    *,
    search: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    generation: str | None = None,
    capacity: str | None = None,
    specs_filter: dict | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = True,
    sort: str = "price_asc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Return (products, total_count) matching the given filters.

    Each product dict contains:
        id, name, brand, match_key, model_number, category, specs,
        cheapest_price, cheapest_retailer, retailer_count, listings[]

    How the query works:
      1. The CTE resolves the current price for every (product, retailer) pair.
      2. We GROUP BY product and aggregate listings into a JSON array.
      3. WHERE / HAVING filters are applied at the product level.
      4. A second COUNT(*) query gives the total without LIMIT for pagination.
    """
    # Build dynamic WHERE fragments (applied to the products table directly)
    where_parts = []
    params: list = []

    if search:
        # Split into tokens so "B840 MSI" and "MSI B840" both match "MSI B840 Pro WiFi".
        # Every token must appear in at least one of name/brand/model_number (AND across tokens).
        for token in search.split():
            # Escape LIKE wildcards so literal % or _ in the query aren't treated as patterns.
            safe = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            term = f"%{safe}%"
            where_parts.append(
                "(p.name ILIKE %s OR p.brand ILIKE %s OR p.model_number ILIKE %s)"
            )
            params.extend([term, term, term])

    if category:
        where_parts.append("UPPER(p.category) = UPPER(%s)")
        params.append(category)
    if brand:
        where_parts.append("LOWER(p.brand) = LOWER(%s)")
        params.append(brand)
    if generation:
        where_parts.append("p.specs->>'generation' = %s")
        params.append(generation)
    if capacity:
        where_parts.append("p.specs->>'capacity' = %s")
        params.append(capacity)

    # Generic JSONB spec filters — each key/value pair becomes a WHERE clause.
    # Keys are validated against _ALLOWED_SPEC_KEYS to prevent injection.
    if specs_filter:
        for key, value in specs_filter.items():
            if key not in _ALLOWED_SPEC_KEYS:
                continue
            if isinstance(value, bool):
                # Boolean values need cast: specs->>'rgb' = 'true'
                where_parts.append(f"(p.specs->>'{key}')::boolean = %s")
                params.append(value)
            else:
                where_parts.append(f"p.specs->>'{key}' ILIKE %s")
                params.append(str(value))

    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    # HAVING filters (need aggregated cheapest_price to be computed first)
    having_parts = []
    having_params: list = []

    if in_stock_only:
        having_parts.append(
            "MIN(cp.price_bdt) FILTER (WHERE cp.stock_status = 'in_stock') IS NOT NULL"
        )
    if min_price is not None:
        having_parts.append(
            "MIN(cp.price_bdt) FILTER (WHERE cp.stock_status = 'in_stock') >= %s"
        )
        having_params.append(min_price)
    if max_price is not None:
        having_parts.append(
            "MIN(cp.price_bdt) FILTER (WHERE cp.stock_status = 'in_stock') <= %s"
        )
        having_params.append(max_price)

    having_sql = ("HAVING " + " AND ".join(having_parts)) if having_parts else ""

    # Sort
    order_map = {
        "price_asc":        "cheapest_price ASC NULLS LAST",
        "price_desc":       "cheapest_price DESC NULLS LAST",
        "store_count_desc": "retailer_count DESC NULLS LAST",
        # Largest gap between cheapest and dearest in-stock seller — the deal-hunt
        # view. Single-store products have savings 0 and naturally sort last.
        "savings_desc":     "savings DESC NULLS LAST",
        "name":             "p.name ASC",
    }
    order_sql = order_map.get(sort, order_map["price_asc"])

    main_params = params + having_params

    retailer_count_sql = (
        "COUNT(DISTINCT cp.retailer) FILTER (WHERE cp.stock_status = 'in_stock')"
        if in_stock_only else
        "COUNT(DISTINCT cp.retailer)"
    )

    main_query = f"""
        {_CURRENT_PRICES_CTE}
        SELECT
            p.id,
            p.name,
            p.brand,
            p.match_key,
            p.model_number,
            p.category,
            p.specs,
            MIN(cp.price_bdt) FILTER (WHERE cp.stock_status = 'in_stock') AS cheapest_price,
            COALESCE(
                MAX(cp.price_bdt) FILTER (WHERE cp.stock_status = 'in_stock')
              - MIN(cp.price_bdt) FILTER (WHERE cp.stock_status = 'in_stock'),
            0)                                                             AS savings,
            {retailer_count_sql}                                           AS retailer_count,
            -- Window functions run after GROUP BY/HAVING but before LIMIT, so this
            -- is the full match count — the same number the old separate COUNT(*)
            -- query produced, for free instead of a second full aggregation.
            COUNT(*) OVER ()                                               AS total_count,
            JSON_AGG(
                JSON_BUILD_OBJECT(
                    'retailer',       cp.retailer,
                    'price_bdt',      cp.price_bdt,
                    'in_stock',       cp.in_stock,
                    'stock_status',   cp.stock_status,
                    'pc_bundle_only', cp.pc_bundle_only,
                    'product_url',    cp.product_url,
                    'scraped_at',     cp.scraped_at
                ) ORDER BY cp.price_bdt ASC NULLS LAST
            ) AS listings
        FROM products p
        LEFT JOIN current_prices cp ON cp.product_id = p.id
        {where_sql}
        GROUP BY p.id
        {having_sql}
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
    """

    count_query = f"""
        {_CURRENT_PRICES_CTE}
        SELECT COUNT(*) FROM (
            SELECT p.id
            FROM products p
            LEFT JOIN current_prices cp ON cp.product_id = p.id
            {where_sql}
            GROUP BY p.id
            {having_sql}
        ) sub
    """

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(main_query, main_params + [limit, offset])
        rows = cur.fetchall()

        if rows:
            total = rows[0]["total_count"]
        elif offset == 0:
            # No rows on the first page means nothing matched at all.
            total = 0
        else:
            # Paged past the end: the window count came back with no rows to
            # carry it, so fall back to the standalone COUNT for this rare case.
            cur.execute(count_query, params + having_params)
            total = cur.fetchone()["count"]

    products = []
    for row in rows:
        row = dict(row)
        row.pop("total_count", None)
        listings = row.get("listings") or []
        # Find cheapest in-stock retailer
        priced = [l for l in listings if l["price_bdt"] and l.get("stock_status", "in_stock" if l["in_stock"] else "out_of_stock") == "in_stock"]
        cheapest = min(priced, key=lambda l: l["price_bdt"]) if priced else None
        row["cheapest_retailer"] = cheapest["retailer"] if cheapest else None
        products.append(row)

    return products, total


# ---------------------------------------------------------------------------
# Single product with full current listings
# ---------------------------------------------------------------------------

def get_product(conn, product_id: int) -> dict | None:
    """
    Return one product with all current retailer listings, or None if not found.
    """
    query = f"""
        {_CURRENT_PRICES_CTE}
        SELECT
            p.id,
            p.name,
            p.brand,
            p.match_key,
            p.model_number,
            p.category,
            p.specs,
            JSON_AGG(
                JSON_BUILD_OBJECT(
                    'retailer',       cp.retailer,
                    'price_bdt',      cp.price_bdt,
                    'in_stock',       cp.in_stock,
                    'stock_status',   cp.stock_status,
                    'pc_bundle_only', cp.pc_bundle_only,
                    'product_url',    cp.product_url,
                    'scraped_at',     cp.scraped_at
                ) ORDER BY cp.price_bdt ASC NULLS LAST
            ) AS listings
        FROM products p
        LEFT JOIN current_prices cp ON cp.product_id = p.id
        WHERE p.id = %s
        GROUP BY p.id
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (product_id,))
        row = cur.fetchone()

    if not row:
        return None

    row = dict(row)
    listings = row.get("listings") or []
    priced = [l for l in listings if l["price_bdt"] and l["in_stock"]]
    cheapest = min(priced, key=lambda l: l["price_bdt"]) if priced else None
    row["cheapest_price"] = cheapest["price_bdt"] if cheapest else None
    row["cheapest_retailer"] = cheapest["retailer"] if cheapest else None
    row["retailer_count"] = len({l["retailer"] for l in listings if l["price_bdt"]})
    return row


# ---------------------------------------------------------------------------
# Price history for one product
# ---------------------------------------------------------------------------

def get_price_history(
    conn,
    product_id: int,
    retailer: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    All price rows for a product, newest first.
    Optionally filtered to a single retailer.
    Useful for drawing a price-over-time chart.
    """
    where_parts = ["pr.product_id = %s"]
    params: list = [product_id]

    if retailer:
        where_parts.append("LOWER(r.name) = LOWER(%s)")
        params.append(retailer)

    where_sql = "WHERE " + " AND ".join(where_parts)

    query = f"""
        SELECT
            r.name      AS retailer,
            pr.price_bdt,
            pr.in_stock,
            pr.scraped_at
        FROM prices pr
        JOIN retailers r ON r.id = pr.retailer_id
        {where_sql}
        ORDER BY pr.scraped_at DESC
        LIMIT %s
    """
    params.append(limit)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Metadata helpers (used for search filter dropdowns)
# ---------------------------------------------------------------------------

def get_categories(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category"
        )
        return [r[0] for r in cur.fetchall()]


def get_brands(conn, category: str | None = None) -> list[str]:
    if category:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT brand FROM products WHERE UPPER(category) = UPPER(%s) AND brand IS NOT NULL ORDER BY brand",
                (category,),
            )
            return [r[0] for r in cur.fetchall()]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand"
        )
        return [r[0] for r in cur.fetchall()]


def get_retailers(conn) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, name, base_url FROM retailers ORDER BY name")
        return [dict(r) for r in cur.fetchall()]


def get_seller_specs(conn, product_id: int) -> dict:
    """
    Return the latest seller_specs per retailer for a product.
    Result: {retailer_name: {spec_key: value, ...}, ...}

    Only returns retailers that have non-empty seller_specs (populated after
    normalize.py was updated to emit seller_raw_specs).
    """
    query = """
        SELECT DISTINCT ON (pr.retailer_id)
            r.name        AS retailer,
            pr.seller_specs
        FROM prices pr
        JOIN retailers r ON r.id = pr.retailer_id
        WHERE pr.product_id = %s
          AND pr.seller_specs IS NOT NULL
          AND pr.seller_specs != '{}'::jsonb
        ORDER BY pr.retailer_id, pr.scraped_at DESC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (product_id,))
        rows = cur.fetchall()

    result = {}
    for row in rows:
        specs = row["seller_specs"] or {}
        if specs:
            result[row["retailer"]] = dict(specs)
    return result


def diff_seller_specs(seller_data: dict) -> dict:
    """
    Given {retailer: {spec_key: value}}, split specs into:
      shared    — same non-null value across ALL retailers that have data
      differing — value differs between retailers, or only some have it

    Returns:
      {
        "shared":    {key: common_value},
        "differing": {key: {retailer: value_or_None}},
        "retailers": [ordered list of retailer names],
      }
    """
    retailers = list(seller_data.keys())
    if not retailers:
        return {"shared": {}, "differing": {}, "retailers": []}

    all_keys: set[str] = set()
    for specs in seller_data.values():
        all_keys.update(k for k, v in specs.items() if v)

    shared: dict[str, str] = {}
    differing: dict[str, dict] = {}

    for key in sorted(all_keys):
        values = {r: seller_data[r].get(key) for r in retailers}
        non_null = {v for v in values.values() if v}

        if len(non_null) == 1 and all(values.get(r) for r in retailers):
            # Every retailer has this key and they all agree
            shared[key] = list(non_null)[0]
        else:
            differing[key] = values

    return {"shared": shared, "differing": differing, "retailers": retailers}


# ---------------------------------------------------------------------------
# Scraper run tracking
# ---------------------------------------------------------------------------

def cleanup_stale_runs(conn) -> int:
    """Mark RUNNING rows older than 3 hours as FAILED (server restarted mid-run)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scraper_runs
            SET status        = 'FAILED',
                finished_at   = NOW(),
                error_message = 'Server restarted while running'
            WHERE status = 'RUNNING'
              AND started_at < NOW() - INTERVAL '3 hours'
            """
        )
        return cur.rowcount


def get_scraper_runs(conn, limit: int = 15) -> list[dict]:
    """Return the most recent scraper run records, newest first."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, category, retailers, started_at, finished_at,
                   status, products_count, prices_count, error_message
            FROM scraper_runs
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_retailer_freshness(conn) -> list[dict]:
    """Per-retailer max scraped_at, distinct product count, and total price rows."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                r.name                              AS retailer,
                MAX(pr.scraped_at)                  AS last_scraped,
                COUNT(DISTINCT pr.product_id)       AS product_count,
                COUNT(pr.id)                        AS price_rows
            FROM retailers r
            LEFT JOIN prices pr ON pr.retailer_id = r.id
            GROUP BY r.name
            ORDER BY MAX(pr.scraped_at) DESC NULLS LAST
            """
        )
        return [dict(r) for r in cur.fetchall()]


def create_scraper_run(conn, category: str, retailers: list[str]) -> int:
    """Insert a RUNNING row and return its id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scraper_runs (category, retailers, status)
            VALUES (%s, %s, 'RUNNING')
            RETURNING id
            """,
            (category, retailers),
        )
        return cur.fetchone()[0]


def update_scraper_run(
    conn,
    run_id: int,
    status: str,
    products_count: int = 0,
    prices_count: int = 0,
    error_message: str | None = None,
) -> None:
    """Set a run's terminal state (SUCCESS or FAILED) with stats."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scraper_runs
            SET status         = %s,
                finished_at    = NOW(),
                products_count = %s,
                prices_count   = %s,
                error_message  = %s
            WHERE id = %s
            """,
            (status, products_count, prices_count, error_message, run_id),
        )


def get_active_run(conn, category: str) -> dict | None:
    """Return the RUNNING row for a category, or None if no run is active."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, started_at FROM scraper_runs
            WHERE category = %s AND status = 'RUNNING'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (category,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_spec_values(conn, category: str, key: str) -> list[str]:
    """
    Return sorted distinct non-null values for a specs JSONB key within a category.
    Used to populate filter dropdowns: /specs/values?category=RAM&key=speed
    """
    if key not in _ALLOWED_SPEC_KEYS:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT p.specs->>%s AS val
            FROM products p
            WHERE UPPER(p.category) = UPPER(%s)
              AND p.specs->>%s IS NOT NULL
              AND p.specs->>%s != 'null'
              AND p.specs->>%s != 'false'
            ORDER BY val
            """,
            (key, category, key, key, key),
        )
        return [r[0] for r in cur.fetchall() if r[0]]


# ---------------------------------------------------------------------------
# Deals feed — biggest recent price drops
# ---------------------------------------------------------------------------

def get_deals(
    conn,
    category: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Return products with the biggest recent price drops.

    Compares the most recent price in mv_current_prices against that same
    listing's previous price. Ranks by absolute BDT drop descending.

    The comparison is per product_url, not just per (product, retailer). A
    retailer sometimes sells one product under two URLs at different prices -
    Skyland lists the same AITC DDR5 kit at both 70,200 and 17,500 - and the
    matcher rightly folds them into one canonical product. Comparing by
    (product, retailer) alone then picks whichever listing was scraped last as
    the "previous" price and reports a 75% crash that never happened.
    """
    where_sql = ""
    params: list = []
    if category:
        where_sql = "WHERE UPPER(p.category) = UPPER(%s)"
        params.append(category)

    params.append(limit)

    query = f"""
        WITH current AS (
            SELECT product_id, retailer, product_url, price_bdt, scraped_at
            FROM mv_current_prices
            WHERE price_bdt IS NOT NULL
        ),
        previous AS (
            SELECT DISTINCT ON (pr.product_id, r.name, pr.product_url)
                pr.product_id,
                r.name         AS retailer,
                pr.product_url,
                pr.price_bdt   AS prev_price,
                pr.scraped_at
            FROM prices pr
            JOIN retailers r ON r.id = pr.retailer_id
            -- Joining to `current` pins the comparison to the same listing and
            -- replaces the old correlated MAX() subquery.
            JOIN current c
              ON  c.product_id  = pr.product_id
              AND c.retailer    = r.name
              AND c.product_url IS NOT DISTINCT FROM pr.product_url
            WHERE pr.price_bdt IS NOT NULL
              AND pr.scraped_at < c.scraped_at
            ORDER BY pr.product_id, r.name, pr.product_url, pr.scraped_at DESC
        ),
        drops AS (
            SELECT
                c.product_id,
                c.retailer,
                c.price_bdt   AS current_price,
                prev.prev_price,
                (prev.prev_price - c.price_bdt) AS drop_bdt,
                CASE WHEN prev.prev_price > 0
                     THEN ROUND(((prev.prev_price - c.price_bdt) / prev.prev_price) * 100, 1)
                     ELSE 0 END AS drop_pct
            FROM current c
            JOIN previous prev USING (product_id, retailer, product_url)
            WHERE c.price_bdt < prev.prev_price
        )
        SELECT
            p.id,
            p.name,
            p.brand,
            p.category,
            p.specs,
            d.retailer,
            d.current_price,
            d.prev_price,
            d.drop_bdt,
            d.drop_pct
        FROM drops d
        JOIN products p ON p.id = d.product_id
        {where_sql}
        ORDER BY d.drop_bdt DESC
        LIMIT %s
    """

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Alerts — price-drop notifications
# ---------------------------------------------------------------------------

def create_alert(
    conn,
    device_id: str,
    product_id: int,
    target_price: float,
) -> dict:
    """Create or update a price-drop alert for a product."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO alerts (device_id, product_id, target_price)
            VALUES (%s, %s, %s)
            ON CONFLICT (device_id, product_id) DO UPDATE
              SET target_price = EXCLUDED.target_price,
                  triggered     = FALSE,
                  last_notified_at = NULL
            RETURNING id, device_id, product_id, target_price, triggered, created_at
            """,
            (device_id, product_id, target_price),
        )
        conn.commit()
        return dict(cur.fetchone())


def list_alerts(conn, device_id: str) -> list[dict]:
    """List all alerts for a device, with current product price."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                a.id,
                a.product_id,
                a.target_price,
                a.triggered,
                a.last_notified_at,
                a.created_at,
                p.name        AS product_name,
                p.category    AS product_category,
                cp.price_bdt  AS current_price,
                cp.retailer   AS cheapest_retailer
            FROM alerts a
            JOIN products p ON p.id = a.product_id
            LEFT JOIN mv_current_prices cp ON cp.product_id = a.product_id
              AND cp.price_bdt = (
                  SELECT MIN(m2.price_bdt) FROM mv_current_prices m2
                  WHERE m2.product_id = a.product_id AND m2.price_bdt IS NOT NULL
              )
            WHERE a.device_id = %s
            ORDER BY a.created_at DESC
            """,
            (device_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def delete_alert(conn, device_id: str, alert_id: int) -> bool:
    """Delete an alert. Returns True if deleted."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM alerts WHERE id = %s AND device_id = %s",
            (alert_id, device_id),
        )
        conn.commit()
        return cur.rowcount > 0


def evaluate_alerts(conn) -> list[dict]:
    """
    Check all active (non-triggered) alerts against current prices.
    Returns a list of triggered alerts with product + price info.
    Called by the scheduler after each scrape cycle.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                a.id,
                a.device_id,
                a.product_id,
                a.target_price,
                p.name        AS product_name,
                MIN(cp.price_bdt) AS current_price,
                (SELECT retailer FROM mv_current_prices
                 WHERE product_id = a.product_id AND price_bdt IS NOT NULL
                 ORDER BY price_bdt ASC LIMIT 1) AS cheapest_retailer
            FROM alerts a
            JOIN products p ON p.id = a.product_id
            JOIN mv_current_prices cp ON cp.product_id = a.product_id
            WHERE a.triggered = FALSE
              AND cp.price_bdt IS NOT NULL
              AND cp.price_bdt <= a.target_price
            GROUP BY a.id, a.device_id, a.product_id, a.target_price, p.name
            """,
        )
        triggered = [dict(r) for r in cur.fetchall()]

    if triggered:
        ids = [t["id"] for t in triggered]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET triggered = TRUE, last_notified_at = NOW() WHERE id = ANY(%s)",
                (ids,),
            )
            conn.commit()

    return triggered


def get_triggered_alerts(conn, device_id: str) -> list[dict]:
    """Get triggered alerts for a device (for the UI notification badge)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                a.id,
                a.product_id,
                a.target_price,
                a.last_notified_at,
                p.name AS product_name,
                MIN(cp.price_bdt) AS current_price
            FROM alerts a
            JOIN products p ON p.id = a.product_id
            LEFT JOIN mv_current_prices cp ON cp.product_id = a.product_id
            WHERE a.device_id = %s AND a.triggered = TRUE
            GROUP BY a.id, a.product_id, a.target_price, a.last_notified_at, p.name
            ORDER BY a.last_notified_at DESC
            """,
            (device_id,),
        )
        return [dict(r) for r in cur.fetchall()]
