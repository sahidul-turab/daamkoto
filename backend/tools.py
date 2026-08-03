"""
Tool registry for the DaamKoto AI agent.

Each entry in TOOLS is the JSON schema (OpenAI function-calling format).
Each handler in TOOL_HANDLERS takes (conn, **kwargs) and returns a JSON-safe dict.

The agent loop calls execute_tool(conn, name, arguments) to dispatch.
"""

from __future__ import annotations

import json
from typing import Any

from backend import queries, compat as compat_mod

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    # ── 1. search_products ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search the live product database for PC components. "
                "Call this whenever the user asks about prices, products, or wants to find parts. "
                "Returns matching products with current prices from all 15 Bangladeshi retailers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "RAM DESKTOP", "RAM LAPTOP", "GPU", "PROCESSOR", "MOTHERBOARD",
                            "SSD", "PORTABLE SSD", "HDD", "PORTABLE HDD",
                            "PSU", "CPU COOLER", "CASING COOLER", "CASING",
                        ],
                        "description": "Product category. Required for best results.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Free-text search across product name, brand, model. Use for specific model queries like 'RTX 4060 Ti Ventus'.",
                    },
                    "brand": {"type": "string", "description": "Brand name e.g. Kingston, Corsair, ASUS, MSI, Samsung, WD."},
                    "max_price": {"type": "number", "description": "Maximum price in BDT."},
                    "min_price": {"type": "number", "description": "Minimum price in BDT."},
                    "sort": {
                        "type": "string",
                        "enum": ["price_asc", "price_desc", "store_count_desc", "savings_desc", "name"],
                        "description": "Sort order. Default price_asc.",
                    },
                    "in_stock_only": {"type": "boolean", "description": "Only in-stock products. Default true."},
                    "limit": {"type": "integer", "description": "Max results (default 10, max 30)."},
                    # RAM
                    "generation": {"type": "string", "enum": ["DDR3", "DDR4", "DDR5"], "description": "[RAM] Memory generation."},
                    "capacity": {"type": "string", "description": "[RAM/SSD/HDD] Size e.g. 16GB, 1TB."},
                    "speed": {"type": "string", "description": "[RAM] Speed e.g. 3200MHz."},
                    # GPU
                    "chipset_brand": {"type": "string", "enum": ["NVIDIA", "AMD", "Intel Arc"], "description": "[GPU] GPU manufacturer."},
                    "vram": {"type": "string", "description": "[GPU] VRAM e.g. 8GB, 12GB."},
                    "chipset": {"type": "string", "description": "[GPU/Mobo] GPU chipset or mobo chipset."},
                    # CPU
                    "socket": {"type": "string", "description": "[CPU/Mobo] Socket e.g. AM5, LGA1700."},
                    "series": {"type": "string", "description": "[CPU] Series e.g. Ryzen 7, Core i5."},
                    "cores": {"type": "string", "description": "[CPU] Core count e.g. 8, 12."},
                    # Mobo
                    "ram_type": {"type": "string", "enum": ["DDR4", "DDR5"], "description": "[Mobo] Supported RAM type."},
                    "form_factor": {"type": "string", "description": "[Mobo/Case] Form factor e.g. ATX, Micro-ATX, Mid Tower."},
                    # SSD
                    "interface": {"type": "string", "description": "[SSD] Interface e.g. NVMe Gen4, SATA."},
                    "nand_type": {"type": "string", "enum": ["TLC", "QLC", "MLC", "SLC"], "description": "[SSD] NAND type."},
                    # PSU
                    "wattage": {"type": "string", "description": "[PSU] Power output e.g. 750W."},
                    "efficiency": {"type": "string", "description": "[PSU] 80+ rating e.g. 80+ Gold."},
                    "modularity": {"type": "string", "enum": ["Fully Modular", "Semi-Modular", "Non-Modular"], "description": "[PSU] Modularity."},
                    # Cooler
                    "type": {"type": "string", "description": "[CPU Cooler] Air or AIO e.g. Air, AIO 240mm."},
                    "radiator_size": {"type": "string", "description": "[CPU Cooler] Radiator size e.g. 240mm, 360mm."},
                    # Case
                    "side_panel": {"type": "string", "description": "[Case] Side panel type e.g. Tempered Glass."},
                    "color": {"type": "string", "description": "[Case] Color e.g. Black, White."},
                },
                "required": [],
            },
        },
    },

    # ── 2. get_product_details ─────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Get full details for a specific product by ID, including all retailer prices, "
                "specs, and stock status. Use after search_products when the user wants more info "
                "about a specific item, or to compare prices across retailers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "Product ID from search results."},
                },
                "required": ["product_id"],
            },
        },
    },

    # ── 3. get_price_history ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": (
                "Get price history for a product over time. Use to answer: "
                "'Is this a good time to buy?', 'Did the price drop recently?', "
                "'What was the lowest price ever?'. Returns recent price points per retailer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "Product ID."},
                    "retailer": {"type": "string", "description": "Filter to a specific retailer (optional)."},
                },
                "required": ["product_id"],
            },
        },
    },

    # ── 4. check_compatibility ─────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "check_compatibility",
            "description": (
                "Check compatibility between PC parts by product ID. "
                "Checks: CPU↔Motherboard socket, RAM gen↔Mobo, Mobo↔Case size, PSU wattage headroom, AIO radiator fit. "
                "Use when the user asks 'will this fit?', 'are these compatible?', or after planning a build."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cpu_id":    {"type": "integer", "description": "Processor product ID (optional)."},
                    "mobo_id":   {"type": "integer", "description": "Motherboard product ID (optional)."},
                    "ram_id":    {"type": "integer", "description": "RAM product ID (optional)."},
                    "gpu_id":    {"type": "integer", "description": "GPU product ID (optional)."},
                    "psu_id":    {"type": "integer", "description": "PSU product ID (optional)."},
                    "case_id":   {"type": "integer", "description": "Case product ID (optional)."},
                    "cooler_id": {"type": "integer", "description": "CPU cooler product ID (optional)."},
                    "storage_id":{"type": "integer", "description": "Storage product ID (optional)."},
                },
                "required": [],
            },
        },
    },

    # ── 5. plan_build ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "plan_build",
            "description": (
                "Generate a complete PC build recommendation within a budget. "
                "Allocates budget across all 8 slots (CPU, GPU, Mobo, RAM, Storage, PSU, Case, Cooler), "
                "picks the best value parts from the DB, checks compatibility, and returns a full build sheet. "
                "Use when the user gives a total budget like '90000 taka gaming PC'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "budget_bdt": {
                        "type": "number",
                        "description": "Total budget in BDT (Bangladeshi Taka).",
                    },
                    "use_case": {
                        "type": "string",
                        "description": "Use case: 'gaming', 'workstation', 'office', 'balanced', or a free description.",
                    },
                    "socket_preference": {
                        "type": "string",
                        "description": "Optional preferred CPU socket e.g. AM5, LGA1700.",
                    },
                    "include_gpu": {
                        "type": "boolean",
                        "description": "Whether to include a discrete GPU. Default true.",
                    },
                },
                "required": ["budget_bdt"],
            },
        },
    },

    # ── 6. get_deals ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_deals",
            "description": (
                "Get the biggest recent price drops across all retailers. "
                "Use when the user asks 'what are the best deals today?', "
                "'what dropped in price?', or 'show me value picks'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter to a specific category (optional).",
                    },
                    "limit": {"type": "integer", "description": "Number of deals (default 10)."},
                },
                "required": [],
            },
        },
    },
]

# Set of tool names for quick lookup
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

# Spec keys that go into specs_filter (not top-level query params)
_SPEC_KEYS = {
    "speed", "vram", "chipset", "chipset_brand", "socket", "series", "cores",
    "ram_type", "form_factor", "interface", "nand_type", "wattage", "efficiency",
    "modularity", "type", "radiator_size", "side_panel", "color",
    "latency", "memory_type", "architecture",
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_search_products(conn, **kwargs) -> dict:
    limit = min(int(kwargs.pop("limit", 10)), 30)
    specs_filter = {k: v for k, v in kwargs.items() if k in _SPEC_KEYS and v is not None}
    top_level = {k: v for k, v in kwargs.items() if k not in _SPEC_KEYS}

    products, total = queries.search_products(
        conn,
        search=top_level.get("search"),
        category=top_level.get("category"),
        brand=top_level.get("brand"),
        generation=top_level.get("generation"),
        capacity=top_level.get("capacity"),
        specs_filter=specs_filter or None,
        min_price=top_level.get("min_price"),
        max_price=top_level.get("max_price"),
        in_stock_only=top_level.get("in_stock_only", True),
        sort=top_level.get("sort", "price_asc"),
        limit=limit,
        offset=0,
    )
    return {
        "total": total,
        "returned": len(products),
        "products": [
            {
                "id": p["id"],
                "name": p["name"],
                "brand": p.get("brand"),
                "category": p.get("category"),
                "cheapest_price": p.get("cheapest_price"),
                "cheapest_retailer": p.get("cheapest_retailer"),
                "retailer_count": p.get("retailer_count", 0),
                "specs": p.get("specs", {}),
            }
            for p in products
        ],
    }


def _handle_get_product_details(conn, product_id: int, **_) -> dict:
    product = queries.get_product(conn, product_id)
    if not product:
        return {"error": f"Product {product_id} not found."}

    seller_specs = queries.get_seller_specs(conn, product_id)

    return {
        "id": product["id"],
        "name": product["name"],
        "brand": product.get("brand"),
        "category": product.get("category"),
        "specs": product.get("specs", {}),
        "cheapest_price": product.get("cheapest_price"),
        "cheapest_retailer": product.get("cheapest_retailer"),
        "retailer_count": product.get("retailer_count", 0),
        "listings": [
            {
                "retailer": l["retailer"],
                "price_bdt": l["price_bdt"],
                "in_stock": l["in_stock"],
                "stock_status": l.get("stock_status"),
                "product_url": l.get("product_url"),
            }
            for l in (product.get("listings") or [])
        ],
        "seller_specs": seller_specs,
    }


def _handle_get_price_history(conn, product_id: int, retailer: str | None = None, **_) -> dict:
    history = queries.get_price_history(conn, product_id, retailer=retailer, limit=60)
    if not history:
        return {"product_id": product_id, "message": "No price history found.", "history": []}

    # Summarise for the agent: min, max, recent trend
    prices = [h["price_bdt"] for h in history if h["price_bdt"]]
    oldest = min(prices) if prices else None
    newest_price = prices[0] if prices else None  # history is newest-first
    low = min(prices) if prices else None
    high = max(prices) if prices else None

    trend = "stable"
    if len(prices) >= 2:
        recent_avg = sum(prices[:3]) / min(3, len(prices))
        older_avg = sum(prices[-3:]) / min(3, len(prices))
        if recent_avg < older_avg * 0.97:
            trend = "dropping"
        elif recent_avg > older_avg * 1.03:
            trend = "rising"

    return {
        "product_id": product_id,
        "current_price": newest_price,
        "all_time_low": low,
        "all_time_high": high,
        "trend": trend,
        "data_points": len(history),
        "history": history[:20],  # send last 20 for context
    }


def _handle_check_compatibility(conn, **kwargs) -> dict:
    slot_map = {
        "cpu": "cpu_id",
        "mobo": "mobo_id",
        "ram": "ram_id",
        "gpu": "gpu_id",
        "psu": "psu_id",
        "case": "case_id",
        "cooler": "cooler_id",
        "storage": "storage_id",
    }
    products: dict[str, dict | None] = {}
    for slot, key in slot_map.items():
        pid = kwargs.get(key)
        if pid:
            products[slot] = queries.get_product(conn, int(pid))

    if not products:
        return {"error": "No product IDs provided for compatibility check."}

    result = compat_mod.evaluate_build(products)
    return result.to_dict()


def _handle_plan_build(conn, budget_bdt: float, use_case: str = "balanced",
                       socket_preference: str | None = None,
                       include_gpu: bool = True, **_) -> dict:
    """
    Build-from-budget: allocate budget across slots, find cheapest compatible parts.
    Returns a build_sheet structure.
    """
    profile_name = compat_mod.classify_use_case(use_case)
    profile = dict(compat_mod.BUDGET_PROFILES[profile_name])

    if not include_gpu:
        gpu_share = profile.pop("gpu", 0)
        # Redistribute GPU budget to CPU and mobo
        for slot in ["cpu", "mobo", "ram"]:
            profile[slot] = profile.get(slot, 0) + gpu_share / 3

    # Normalise so shares sum to 1
    total_share = sum(profile.values())
    if total_share > 0:
        profile = {k: v / total_share for k, v in profile.items()}

    build: dict[str, dict | None] = {}
    slot_budgets: dict[str, float] = {}
    build_cost = 0.0

    # First pass: find cheapest part within budget for each slot
    for slot, share in profile.items():
        if share == 0:
            continue
        slot_budget = budget_bdt * share
        slot_budgets[slot] = slot_budget
        category = compat_mod.SLOT_CATEGORY.get(slot)
        if not category:
            continue

        kwargs: dict = {
            "category": category,
            "sort": "price_asc",
            "in_stock_only": True,
            "max_price": slot_budget * 1.1,  # slight headroom
            "limit": 5,
        }
        if socket_preference and slot == "cpu":
            kwargs["socket"] = socket_preference
        if socket_preference and slot == "mobo":
            kwargs["socket"] = socket_preference

        products, _ = queries.search_products(conn, **kwargs)
        chosen = products[0] if products else None
        build[slot] = chosen
        if chosen and chosen.get("cheapest_price"):
            build_cost += float(chosen["cheapest_price"])

    # Run compat check
    compat_result = compat_mod.evaluate_build(build)

    # Assemble build_sheet
    slots_out = []
    for slot, product in build.items():
        if product:
            cp = product.get("cheapest_price")
            slots_out.append({
                "slot": slot,
                "category": compat_mod.SLOT_CATEGORY.get(slot, ""),
                "product_id": product["id"],
                "product_name": product["name"],
                "brand": product.get("brand"),
                "cheapest_price": float(cp) if cp is not None else None,
                "cheapest_retailer": product.get("cheapest_retailer"),
                "retailer_count": product.get("retailer_count", 0),
                "budget_allocated": round(slot_budgets.get(slot, 0)),
            })

    return {
        "profile": profile_name,
        "budget_bdt": float(budget_bdt),
        "total_cost": round(build_cost),
        "within_budget": build_cost <= float(budget_bdt) * 1.05,
        "slots": slots_out,
        "compatibility": compat_result.to_dict(),
    }


def _handle_get_deals(conn, category: str | None = None, limit: int = 10, **_) -> dict:
    deals = queries.get_deals(conn, category=category, limit=min(int(limit), 30))
    return {"deals": deals, "count": len(deals)}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "search_products":     _handle_search_products,
    "get_product_details": _handle_get_product_details,
    "get_price_history":   _handle_get_price_history,
    "check_compatibility": _handle_check_compatibility,
    "plan_build":          _handle_plan_build,
    "get_deals":           _handle_get_deals,
}


def execute_tool(conn, name: str, arguments: dict) -> dict:
    """Dispatch a tool call. Returns a JSON-safe dict."""
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(conn, **arguments)
    except Exception as exc:
        return {"error": str(exc)}
