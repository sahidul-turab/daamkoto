"""
AI chatbot layer — translates natural language into structured product search params.

Uses the Groq API (free tier) with llama-3.3-70b-versatile and OpenAI-compatible
function calling. The LLM NEVER generates or guesses prices — it only fills in
query parameters (category, brand, capacity, etc.) which are passed to the database.
All prices come from the database.

How it works:
  1. User asks: "find 16GB DDR4 RAM under 5000 taka"
  2. Groq calls the `search_products` function with structured params
  3. We extract those params and query the actual database
  4. Groq writes a brief summary of what it searched for
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are DaamKoto, a helpful PC component price comparison assistant for Bangladesh.
You help users find the best prices for PC parts across 13 local retailers including
StarTech, Ryans, Techland BD, Skyland, Creatus, UltraTech, TrustTech, ComputerSource,
BinaryLogic, UCC, PotakaIT, SellTech, and PCHouse.

Rules:
- ALWAYS call the search_products function when the user asks about prices, products, or components.
- NEVER invent or guess prices. All real prices come from the database via the function.
- After calling the function, briefly explain what you searched for (1-2 sentences max).
- If the user's query is unclear, make a reasonable assumption and explain it.
- Understand Bangladeshi taka: "4000 taka", "4k taka", "under ৳4000" all mean max_price=4000.

Category mapping (always use exact English name):
- RAM / desktop RAM / DDR memory → "RAM DESKTOP"
- Laptop RAM / SO-DIMM → "RAM LAPTOP"
- GPU / graphics card / video card → "GPU"
- CPU / processor → "PROCESSOR"
- Motherboard / mobo → "MOTHERBOARD"
- SSD / NVMe / solid state → "SSD"
- Portable SSD / external SSD → "PORTABLE SSD"
- HDD / hard drive / hard disk → "HDD"
- Portable HDD / external HDD → "PORTABLE HDD"
- PSU / power supply → "PSU"
- CPU cooler / AIO / liquid cooler / air cooler → "CPU COOLER"
- Case fan / casing fan / chassis fan → "CASING COOLER"
- Casing / PC case / cabinet → "CASING"

Spec hint — include relevant spec params when the user mentions them:
- RAM: generation (DDR4/DDR5), capacity (8GB/16GB/32GB), speed (3200MHz)
- GPU: chipset_brand (NVIDIA/AMD), vram (8GB/12GB), chipset (RTX 4070)
- CPU: socket (AM5/LGA1700), series (Ryzen 7/Core i5), cores (8/12)
- Motherboard: socket, chipset (B650/Z790), ram_type (DDR5), form_factor (ATX)
- SSD: capacity, interface (NVMe Gen4/SATA), nand_type (TLC/QLC)
- PSU: wattage (750W), efficiency (80+ Gold), modularity (Fully Modular)
- CPU Cooler: type (Air/AIO 240mm), radiator_size (240mm/360mm)
- Casing: form_factor (Mid Tower), side_panel (Tempered Glass), color (Black/White)"""

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": (
            "Search the database for PC components by category and optional filters. "
            "Call this whenever the user asks about products, prices, or components."
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
                    "description": "Product category. Map user intent to the exact enum value.",
                },
                "brand": {
                    "type": "string",
                    "description": "Brand name e.g. Kingston, Corsair, ASUS, MSI, Samsung, WD. Omit if not mentioned.",
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in BDT. Extract from 'under 5000 taka', 'below ৳4k', etc.",
                },
                "min_price": {
                    "type": "number",
                    "description": "Minimum price in BDT. Extract from 'above 3000 taka', 'at least ৳5000'.",
                },
                "sort": {
                    "type": "string",
                    "enum": ["price_asc", "price_desc", "store_count_desc", "savings_desc", "name"],
                    "description": "Sort order. Default store_count_desc (most compared first).",
                },
                "in_stock_only": {
                    "type": "boolean",
                    "description": "Only return in-stock products. Default true.",
                },
                # ── RAM ────────────────────────────────────────────────────────
                "generation": {
                    "type": "string",
                    "enum": ["DDR3", "DDR4", "DDR5"],
                    "description": "[RAM] Memory generation.",
                },
                "capacity": {
                    "type": "string",
                    "description": "[RAM/SSD/HDD] Size e.g. 16GB, 1TB, 2TB.",
                },
                "speed": {
                    "type": "string",
                    "description": "[RAM] Bus speed e.g. 3200MHz, 4800MHz.",
                },
                # ── GPU ────────────────────────────────────────────────────────
                "chipset_brand": {
                    "type": "string",
                    "enum": ["NVIDIA", "AMD", "Intel Arc"],
                    "description": "[GPU] GPU manufacturer.",
                },
                "vram": {
                    "type": "string",
                    "description": "[GPU] VRAM size e.g. 8GB, 12GB, 16GB.",
                },
                "chipset": {
                    "type": "string",
                    "description": "[GPU/Motherboard] GPU chipset (RTX 4070) or mobo chipset (B650, Z790).",
                },
                # ── CPU ────────────────────────────────────────────────────────
                "socket": {
                    "type": "string",
                    "description": "[CPU/Motherboard] Socket e.g. AM5, LGA1700, LGA1851.",
                },
                "series": {
                    "type": "string",
                    "description": "[CPU] Series e.g. Ryzen 7, Core i5, Core Ultra 5.",
                },
                "cores": {
                    "type": "string",
                    "description": "[CPU] Number of cores e.g. 6, 8, 12.",
                },
                # ── Motherboard ────────────────────────────────────────────────
                "ram_type": {
                    "type": "string",
                    "enum": ["DDR4", "DDR5"],
                    "description": "[Motherboard] Supported RAM type.",
                },
                "form_factor": {
                    "type": "string",
                    "description": "[Motherboard/Casing] e.g. ATX, Micro-ATX, Mini-ITX, Mid Tower.",
                },
                # ── SSD ────────────────────────────────────────────────────────
                "interface": {
                    "type": "string",
                    "description": "[SSD] Interface e.g. NVMe Gen4, NVMe Gen3, SATA.",
                },
                "nand_type": {
                    "type": "string",
                    "enum": ["TLC", "QLC", "MLC", "SLC"],
                    "description": "[SSD] NAND flash type.",
                },
                # ── PSU ────────────────────────────────────────────────────────
                "wattage": {
                    "type": "string",
                    "description": "[PSU] Power output e.g. 650W, 750W, 850W.",
                },
                "efficiency": {
                    "type": "string",
                    "description": "[PSU] 80+ rating e.g. 80+ Gold, 80+ Platinum.",
                },
                "modularity": {
                    "type": "string",
                    "enum": ["Fully Modular", "Semi-Modular", "Non-Modular"],
                    "description": "[PSU] Cable modularity.",
                },
                # ── Cooler ────────────────────────────────────────────────────
                "type": {
                    "type": "string",
                    "description": "[CPU Cooler] Air or AIO e.g. Air, AIO 240mm, AIO 360mm.",
                },
                "radiator_size": {
                    "type": "string",
                    "description": "[CPU Cooler] AIO radiator size e.g. 240mm, 360mm.",
                },
                # ── Casing ────────────────────────────────────────────────────
                "side_panel": {
                    "type": "string",
                    "description": "[Casing] Side panel type e.g. Tempered Glass, Mesh.",
                },
                "color": {
                    "type": "string",
                    "description": "[Casing] Chassis color e.g. Black, White.",
                },
            },
            "required": ["category"],
        },
    },
}

# Spec keys the chatbot can extract that go into the specs_filter dict (not top-level params)
_SPEC_KEYS = {
    "speed", "vram", "chipset", "chipset_brand", "socket", "series", "cores",
    "ram_type", "form_factor", "interface", "nand_type", "wattage", "efficiency",
    "modularity", "type", "radiator_size", "side_panel", "color",
}


def translate_to_params(
    user_message: str,
    history: list[dict] | None = None,
) -> tuple[dict, str]:
    """
    Send the user message to Groq. The model calls search_products with extracted params.

    Returns:
      (params, explanation)
        params      — dict of filter kwargs to pass to queries.search_products()
        explanation — model's short description of what it searched for

    Raises:
      ValueError if the API key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com and add it to your .env file."
        )

    client = Groq(api_key=api_key)

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[SEARCH_TOOL],
        tool_choice="auto",
        max_tokens=512,
        temperature=0.1,
    )

    message = response.choices[0].message
    params: dict = {}
    explanation: str = message.content or ""

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        try:
            params = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            params = {}

    if not params:
        return {}, explanation or "I didn't find a search query in your message."

    if not explanation:
        explanation = _default_explanation(params)

    return params, explanation


def _default_explanation(params: dict) -> str:
    parts = []
    if params.get("capacity"):
        parts.append(params["capacity"])
    if params.get("generation"):
        parts.append(params["generation"])
    if params.get("series"):
        parts.append(params["series"])
    if params.get("chipset"):
        parts.append(params["chipset"])
    if params.get("category"):
        parts.append(params["category"].title())
    if params.get("brand"):
        parts.append(f"by {params['brand']}")
    if params.get("max_price"):
        parts.append(f"under ৳{params['max_price']:,.0f}")
    if params.get("min_price"):
        parts.append(f"above ৳{params['min_price']:,.0f}")
    return "Searching for " + " ".join(parts) + "." if parts else "Searching..."
