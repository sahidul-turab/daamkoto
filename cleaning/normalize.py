"""
Stage 2: Cleaning & normalization for all product categories.

What this script does:
  1. Loads a raw JSON file produced by the scraper
  2. Extracts structured, category-specific fields from messy product names
  3. Builds a match_key — a stable identifier for cross-retailer linking
  4. Produces a `specs` dict with all filterable attributes per category
  5. Saves cleaned records to data/processed/

Usage:
  python cleaning/normalize.py                          # uses latest raw file
  python cleaning/normalize.py --input data/raw/foo.json
  python cleaning/normalize.py --category gpu --input data/raw/startech_gpu_*.json
"""

import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Known RAM brand names
# ---------------------------------------------------------------------------
KNOWN_BRANDS = [
    "G.Skill", "G.SKILL",
    "Kingston",
    "Corsair",
    "Team",
    "Netac",
    "OCPC",
    "KingBank",
    "Colorful",
    "PNY",
    "Lexar",
    "Transcend",
    "Patriot",
    "Gigabyte",
    "Twinmos", "TwinMOS",
    "OSCOO",
    "AITC",
    "Alimoto",
    "Kimtigo",
    "Samsung",
    "Crucial",
    "HyperX",
]

BRAND_CANONICAL = {
    "g.skill": "G.Skill",
    "gskill":  "G.Skill",
    "g-skill": "G.Skill",
    "teamgroup": "Team",
    "twinmos":   "TwinMOS",
}


# ---------------------------------------------------------------------------
# Shared extraction helpers (used across multiple categories)
# ---------------------------------------------------------------------------

def extract_brand(name: str) -> str:
    name_lower = name.lower()
    for brand in KNOWN_BRANDS:
        if name_lower.startswith(brand.lower()):
            return BRAND_CANONICAL.get(brand.lower(), brand)
    first = name.split()[0] if name.split() else name
    return BRAND_CANONICAL.get(first.lower(), first)


def extract_capacity(name: str) -> str | None:
    """Total RAM/storage capacity, e.g. '16GB', '1TB'. Prefers TB over GB."""
    m_tb = re.search(r"\b(\d+(?:\.\d+)?)\s*TB\b", name, re.IGNORECASE)
    if m_tb:
        val = float(m_tb.group(1))
        return f"{int(val)}TB" if val == int(val) else f"{val}TB"
    m = re.search(r"\b(\d+)\s*GB\b", name, re.IGNORECASE)
    return f"{m.group(1)}GB" if m else None


def extract_generation(name: str) -> str | None:
    m = re.search(r"\b(DDR[345])\b", name, re.IGNORECASE)
    return m.group(1).upper() if m else None


def extract_speed(name: str) -> str | None:
    m = re.search(r"\b(\d{3,5})\s*[Mm]?[Hh][Zz]\b", name)
    return f"{m.group(1)}MHz" if m else None


def extract_latency(name: str) -> str | None:
    m = re.search(r"\b(CL\d+)\b", name, re.IGNORECASE)
    return m.group(1).upper() if m else None


def extract_form_factor(name: str) -> str:
    if re.search(r"\b(laptop|so-?dimm|sodimm)\b", name, re.IGNORECASE):
        return "Laptop"
    return "Desktop"


def normalize_name(name: str) -> str:
    name = re.sub(r"(\d+)\s+GB\b", r"\1GB", name, flags=re.IGNORECASE)
    name = re.sub(r"(\d+)\s+[Mm][Hh][Zz]\b", r"\1MHz", name)
    name = re.sub(r"\b(\d+)[Mm][Hh][Zz]\b", lambda m: f"{m.group(1)}MHz", name)
    name = re.sub(r" {2,}", " ", name).strip()
    return name


def build_match_key(brand: str, capacity: str | None, generation: str | None, speed: str | None) -> str:
    parts = [brand.lower()]
    if capacity:
        parts.append(capacity.lower())
    if generation:
        parts.append(generation.lower())
    if speed:
        parts.append(speed.lower())
    return "_".join(parts)


def extract_kit(name: str) -> str | None:
    """Return kit config like '2x8GB', '2x16GB' from kit notation."""
    m = re.search(r"\b(\d+)\s*[Xx]\s*(\d+)\s*GB\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}x{m.group(2)}GB"
    return None


def detect_rgb(name: str) -> bool:
    return bool(re.search(r"\b(rgb|argb|aura|mystic\s*light|chroma|razer\s*chroma)\b", name, re.IGNORECASE))


def detect_heatsink(name: str) -> bool:
    return bool(re.search(r"\b(heatsink|heat\s*sink|hs\b|with\s*heat\s*spreader)\b", name, re.IGNORECASE))


def detect_ecc(name: str) -> bool:
    return bool(re.search(r"\becc\b", name, re.IGNORECASE))


def detect_wifi(name: str) -> bool:
    return bool(re.search(r"\b(wifi|wi.?fi|wireless|ax\d{3,4}|802\.11)\b", name, re.IGNORECASE))


def extract_color(name: str) -> str | None:
    if re.search(r"\bwhite\b", name, re.IGNORECASE):
        return "White"
    if re.search(r"\bblack\b", name, re.IGNORECASE):
        return "Black"
    if re.search(r"\bsilver\b", name, re.IGNORECASE):
        return "Silver"
    if re.search(r"\bred\b", name, re.IGNORECASE):
        return "Red"
    return None


def extract_cpu_cores(name: str) -> str | None:
    m = re.search(r"\b(\d{1,2})[- ]?[Cc]ore(?:s)?\b", name)
    if m:
        return m.group(1)
    word_map = {"dual": "2", "quad": "4", "hexa": "6", "octa": "8", "deca": "10", "dodeca": "12"}
    for word, count in word_map.items():
        if re.search(rf"\b{word}.?core\b", name, re.IGNORECASE):
            return count
    return None


def extract_cpu_boost_clock(name: str) -> str | None:
    """Extract boost/turbo clock from product name, e.g. '5.6GHz'."""
    m = re.search(
        r"\b(?:up\s*to|max\s*turbo|turbo|boost)\s*(?:speed\s*)?(\d+(?:\.\d+)?)\s*GHz\b",
        name, re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}GHz"
    return None


def extract_cpu_cache(name: str) -> str | None:
    """Extract L3 cache like '36MB', '32MB'."""
    m = re.search(r"\b(\d+)\s*MB\s*(?:L3\s*)?Cache\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}MB"
    m = re.search(r"\b(\d+)\s*MB\b", name, re.IGNORECASE)
    # Sanity check: only return values plausible for CPU cache (4–192 MB)
    if m and 4 <= int(m.group(1)) <= 192:
        return f"{m.group(1)}MB"
    return None


def extract_hdd_cache(name: str) -> str | None:
    m = re.search(r"\b(\d+)\s*MB\s*(?:Cache|Buffer)\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}MB"
    return None


def extract_mobo_m2_slots(name: str) -> str | None:
    m = re.search(r"\b(\d)\s*[Xx]?\s*M\.?2\b", name, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def detect_atx30(name: str) -> bool:
    return bool(re.search(r"\b(ATX\s*3\.0|PCIe\s*5\.0\s*Ready|12VHPWR)\b", name, re.IGNORECASE))


def detect_argb_fan(name: str) -> bool:
    return bool(re.search(r"\b(argb|a-rgb)\b", name, re.IGNORECASE))


def detect_front_usb_c(name: str) -> bool:
    return bool(re.search(r"\b(USB\s*Type.?C|USB-C|USB\s*3\.2\s*Gen\s*2x2)\b", name, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Processor-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_PROCESSOR_BRANDS = ["Intel", "AMD"]


def extract_processor_brand(name: str) -> str:
    nl = name.lower()
    if nl.startswith("intel") or any(x in nl for x in ("core i", "pentium", "celeron", "xeon", "athlon gold", "athlon silver")):
        return "Intel"
    if nl.startswith("amd") or any(x in nl for x in ("ryzen", "athlon", "threadripper", "epyc")):
        return "AMD"
    return name.split()[0]


def extract_processor_model(name: str) -> str | None:
    m = re.search(r"\bCore\s+Ultra\s+([3579])\s+(\d{3}[A-Z0-9]*)\b", name, re.IGNORECASE)
    if m:
        return f"Core Ultra {m.group(1)} {m.group(2).upper()}"

    m = re.search(r"\b(i[3579])-(\d{4,6}[A-Z0-9]*)\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).upper()}"

    m = re.search(r"\b(i[3579])\s+(\d{4,6}[A-Z0-9]*)\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1).upper()}-{m.group(2).upper()}"

    series_m = re.search(r"\bi([3579])\b", name, re.IGNORECASE)
    if series_m:
        rest = name[series_m.end():]
        model_m = re.search(r"\b(\d{4,6}[A-Z0-9]*)\b(?!\s*(?:th|nd|st|rd)\b)", rest, re.IGNORECASE)
        if model_m:
            return f"I{series_m.group(1).lower()}-{model_m.group(1).upper()}"

    m = re.search(r"\bRyzen\s*([3579])\s+(\d{4}[A-Z0-9]*)\b", name, re.IGNORECASE)
    if m:
        return f"Ryzen {m.group(1)} {m.group(2).upper()}"

    m = re.search(r"\bPentium\s+(?:Gold|Silver)\s+(G?\d{4,5}[A-Z]*)\b", name, re.IGNORECASE)
    if m:
        return f"Pentium {m.group(1).upper()}"

    m = re.search(r"\bCeleron\s+(G?\d{4,5}[A-Z]*)\b", name, re.IGNORECASE)
    if m:
        return f"Celeron {m.group(1).upper()}"

    m = re.search(r"\bAthlon(?:\s+PRO)?\s+(\d{3,4}[A-Z0-9]*)\b", name, re.IGNORECASE)
    if m:
        return f"Athlon {m.group(1).upper()}"

    m = re.search(r"\b(G\d{4}[A-Z]*)\b", name, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    return None


_PROC_NOISE = re.compile(
    r"\b(processor|desktop|laptop|gen|generation|socket|am[45]|lga\d*|up\s*to|ghz|mhz|"
    r"intel|amd|with|radeon|vega|graphics|gaming|series|tray|oem|rebox|box|"
    r"core2?|threads?|cache|turbo|boost|upto|base|clock|speed|gold|silver|"
    r"rocket\s*lake|alder\s*lake|raptor\s*lake|comet\s*lake|coffee\s*lake|"
    r"arrow\s*lake|zen\s*[234]?|vermeer|cezanne|renoir|matisse|raphael|phoenix)\b",
    re.IGNORECASE,
)


def extract_processor_series(name: str) -> str | None:
    m = re.search(r"\bCore\s+Ultra\s+([3579])\b", name, re.IGNORECASE)
    if m:
        return f"Core Ultra {m.group(1)}"
    m = re.search(r"\bCore\s+(i[3579])\b", name, re.IGNORECASE)
    if m:
        return f"Core {m.group(1).lower()}"
    m = re.search(r"\bRyzen\s*([3579])\b", name, re.IGNORECASE)
    if m:
        return f"Ryzen {m.group(1)}"
    if re.search(r"\bPentium\b", name, re.IGNORECASE):
        return "Pentium"
    if re.search(r"\bCeleron\b", name, re.IGNORECASE):
        return "Celeron"
    if re.search(r"\bAthlon\b", name, re.IGNORECASE):
        return "Athlon"
    if re.search(r"\bThreadripper\b", name, re.IGNORECASE):
        return "Threadripper"
    return None


def extract_cpu_socket(name: str) -> str | None:
    m = re.search(r"\b(LGA\s*\d{3,4}|AM[345][\+]?|sTRX\d+|sWRX\d+|TR\d+)\b", name, re.IGNORECASE)
    if m:
        return re.sub(r"\s+", "", m.group(1).upper())
    return None


def extract_cpu_architecture(name: str) -> str | None:
    patterns = [
        (r"\barrow\s*lake\b", "Arrow Lake"),
        (r"\braptor\s*lake\b", "Raptor Lake"),
        (r"\balder\s*lake\b", "Alder Lake"),
        (r"\brocket\s*lake\b", "Rocket Lake"),
        (r"\bcoffee\s*lake\b", "Coffee Lake"),
        (r"\bcomet\s*lake\b", "Comet Lake"),
        (r"\bzen\s*5\b", "Zen 5"),
        (r"\bzen\s*4\b", "Zen 4"),
        (r"\bzen\s*3\b", "Zen 3"),
        (r"\bzen\s*2\b", "Zen 2"),
        (r"\braphael\b", "Zen 4"),
        (r"\bvermeer\b", "Zen 3"),
        (r"\bmatisse\b", "Zen 2"),
        (r"\brenoir\b", "Zen 2"),
        (r"\bphoenix\b", "Zen 4"),
        (r"\bcezanne\b", "Zen 3"),
    ]
    for pattern, arch in patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return arch
    return None


def build_processor_match_key(brand: str, model: str | None, raw_name: str = "") -> str:
    if model:
        norm = re.sub(r"[\s\-]+", "_", model.lower())
        return f"{brand.lower()}_{norm}"
    stub = _PROC_NOISE.sub(" ", raw_name)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:50]
    return f"{brand.lower()}_{stub}" if stub else brand.lower()


def clean_processor_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)

    brand = extract_processor_brand(norm_name)
    model = extract_processor_model(norm_name)
    series = extract_processor_series(norm_name)
    socket = extract_cpu_socket(norm_name)
    architecture = extract_cpu_architecture(norm_name)
    cores = extract_cpu_cores(norm_name)
    boost_clock = extract_cpu_boost_clock(norm_name)
    cache = extract_cpu_cache(norm_name)
    match_key = build_processor_match_key(brand, model, norm_name)

    specs = {
        "brand":        brand,
        "series":       series,
        "model":        model,
        "socket":       socket,
        "architecture": architecture,
        "cores":        cores,
        "boost_clock":  boost_clock,
        "cache":        cache,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields (used by matcher)
        "capacity": None, "generation": series, "speed": model,
        "latency": None, "form_factor": "Desktop",
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# GPU-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_GPU_BRANDS = [
    "ASUS", "MSI", "Gigabyte", "Zotac", "ZOTAC",
    "Colorful", "INNO3D", "Palit", "Galax", "GALAX",
    "PowerColor", "Sapphire", "XFX", "ASRock", "PNY",
    "EVGA", "Gainward",
]

GPU_BRAND_CANONICAL = {
    "zotac": "ZOTAC",
    "galax": "GALAX",
    "inno3d": "INNO3D",
}


def extract_gpu_brand(name: str) -> str:
    name_lower = name.lower()
    for brand in KNOWN_GPU_BRANDS:
        if name_lower.startswith(brand.lower()):
            return GPU_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_chipset(name: str) -> str | None:
    m = re.search(
        r"\b(RTX\s*\d{4}(?:\s*Ti(?:\s*Super)?|\s*Super)?|"
        r"GTX\s*\d{4}(?:\s*Ti(?:\s*Super)?|\s*Super)?|"
        r"GT\s*\d{3,4})\b",
        name, re.IGNORECASE,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip().upper())
    m = re.search(r"\b(RX\s*\d{3,4}(?:\s*(?:XTX|XT|GRE))?)\b", name, re.IGNORECASE)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip().upper())
    m = re.search(r"\b(Arc\s*[AB]\d{3})\b", name, re.IGNORECASE)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    return None


def extract_chipset_brand(chipset: str | None) -> str | None:
    if not chipset:
        return None
    if re.search(r"\b(RTX|GTX|GT)\b", chipset, re.IGNORECASE):
        return "NVIDIA"
    if re.search(r"\bRX\b", chipset, re.IGNORECASE):
        return "AMD"
    if re.search(r"\bArc\b", chipset, re.IGNORECASE):
        return "Intel"
    return None


def extract_vram(name: str) -> str | None:
    m = re.search(r"\b(\d+)\s*GB\b", name, re.IGNORECASE)
    return f"{m.group(1)}GB" if m else None


def extract_gpu_memory_type(name: str) -> str | None:
    if re.search(r"\bGDDR7\b", name, re.IGNORECASE):
        return "GDDR7"
    if re.search(r"\bGDDR6X\b", name, re.IGNORECASE):
        return "GDDR6X"
    if re.search(r"\bGDDR6\b", name, re.IGNORECASE):
        return "GDDR6"
    if re.search(r"\bGDDR5X\b", name, re.IGNORECASE):
        return "GDDR5X"
    if re.search(r"\bGDDR5\b", name, re.IGNORECASE):
        return "GDDR5"
    return None


def extract_gpu_interface(name: str) -> str | None:
    if re.search(r"\bPCIe?\s*5\.0\b", name, re.IGNORECASE):
        return "PCIe 5.0 x16"
    if re.search(r"\bPCIe?\s*4\.0\b", name, re.IGNORECASE):
        return "PCIe 4.0 x16"
    if re.search(r"\bPCIe?\s*3\.0\b", name, re.IGNORECASE):
        return "PCIe 3.0 x16"
    return None


_GPU_VARIANT_NOISE = re.compile(
    r"\b(?:geforce|radeon|arc|rtx|gtx|rx|gddr[5-7]x?|graphics?|"
    r"card|gpu|video|nvidia|amd|intel|edition)\b"
    r"|\b\d+\s*gb\b"               # VRAM like 12GB
    r"|\b\d{3,4}\b"                # chipset numbers like 5070, 4090
    r"|#[A-Z0-9][A-Z0-9\-]{3,}",  # MPN codes like #ZT-B50700Q-10P
    re.IGNORECASE,
)


def extract_gpu_variant(name: str, brand: str) -> str:
    """Return a normalized variant slug that distinguishes GPU sub-models.

    "ZOTAC Gaming GeForce RTX 5070 Twin Edge OC White Edition 12GB GDDR7"
        → "gaming_twin_edge_oc_white"
    "ZOTAC GAMING GeForce RTX 5070 SOLID GDDR7 12GB"
        → "gaming_solid"

    Included in match_key so SOLID, Twin Edge, Gaming X Trio, etc. land in
    separate buckets and are never falsely merged by fuzzy matching.
    """
    s = re.sub(re.escape(brand), "", name, flags=re.IGNORECASE).strip()
    s = _GPU_VARIANT_NOISE.sub(" ", s)
    s = re.sub(r"[^a-zA-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", "_", s.strip().lower()).strip("_")
    return s or "standard"


def build_gpu_match_key(brand: str, chipset: str | None, vram: str | None, variant: str = "") -> str:
    parts = [brand.lower()]
    if chipset:
        parts.append(chipset.lower().replace(" ", "_"))
    if vram:
        parts.append(vram.lower())
    if variant:
        parts.append(variant)
    return "_".join(parts)


def clean_gpu_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)

    brand = extract_gpu_brand(norm_name)
    chipset = extract_chipset(norm_name)
    vram = extract_vram(norm_name)
    chipset_brand = extract_chipset_brand(chipset)
    memory_type = extract_gpu_memory_type(norm_name)
    interface = extract_gpu_interface(norm_name)
    variant = extract_gpu_variant(norm_name, brand)
    match_key = build_gpu_match_key(brand, chipset, vram, variant)

    raw_mpn = raw.get("mpn") or raw.get("specs", {}).get("MPN")
    if not raw_mpn:
        m = re.search(r"#([A-Z0-9][A-Z0-9\-]{3,})", name, re.IGNORECASE)
        if m:
            raw_mpn = m.group(1)
    mpn = raw_mpn.strip().upper() if raw_mpn else None

    specs = {
        "vram":         vram,
        "chipset":      chipset,
        "chipset_brand": chipset_brand,
        "memory_type":  memory_type,
        "interface":    interface,
        "variant":      variant,
    }

    return {
        "raw_name": name, "mpn": mpn,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields (used by matcher)
        "capacity": vram, "generation": chipset,
        "speed": None, "latency": None, "form_factor": "Desktop",
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Motherboard-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_MOBO_BRANDS = [
    "ASUS", "MSI", "Gigabyte", "ASRock", "Biostar", "Colorful",
    "EVGA", "Supermicro",
]

MOBO_BRAND_CANONICAL = {
    "asus": "ASUS", "msi": "MSI", "gigabyte": "Gigabyte", "asrock": "ASRock",
    "biostar": "Biostar", "colorful": "Colorful",
}


def extract_mobo_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_MOBO_BRANDS:
        if nl.startswith(brand.lower()):
            return MOBO_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_mobo_chipset(name: str) -> str | None:
    m = re.search(r"\b([HBZWQ][0-9]{2,3}[A-Z]?)\b", name)
    if m:
        candidate = m.group(1).upper()
        if re.match(r"^[HBZWQ]\d{2,3}[A-Z]?$", candidate) and int(re.search(r"\d+", candidate).group()) > 40:
            return candidate
    m = re.search(r"\b([ABX][45][0-9]{1,2}E?)\b", name)
    if m:
        return m.group(1).upper()
    return None


def extract_mobo_socket(name: str) -> str | None:
    m = re.search(r"\b(LGA\s*\d{3,4}|AM[345][\+]?|sTRX\d+|sWRX\d+)\b", name, re.IGNORECASE)
    if m:
        return re.sub(r"\s+", "", m.group(1).upper())
    return None


def extract_mobo_form_factor(name: str) -> str:
    if re.search(r"\b(mini.?itx|mitx)\b", name, re.IGNORECASE):
        return "Mini-ITX"
    if re.search(r"\b(micro.?atx|matx|m.?atx)\b", name, re.IGNORECASE):
        return "Micro-ATX"
    if re.search(r"\b(e.?atx|extended.?atx)\b", name, re.IGNORECASE):
        return "E-ATX"
    if re.search(r"\bATX\b", name, re.IGNORECASE):
        return "ATX"
    return "ATX"


def extract_mobo_ram_type(name: str) -> str | None:
    if re.search(r"\bDDR5\b", name, re.IGNORECASE):
        return "DDR5"
    if re.search(r"\bDDR4\b", name, re.IGNORECASE):
        return "DDR4"
    return None


_MOBO_NOISE = re.compile(
    r"\b(motherboard|mainboard|desktop|gaming|wifi|wi.?fi|bluetooth|bt|"
    r"ddr[345]|pcie|gen|generation|argb|rgb|socket|lga\d*|am[345]|"
    r"m\.?2|nvme|sata|usb|thunderbolt|intel|amd|series|pro|ultra|prime|"
    r"rog|strix|tuf|msi|mag|mpg|meg|asus|gigabyte|asrock)\b",
    re.IGNORECASE,
)


def build_mobo_match_key(brand: str, chipset: str | None, name: str) -> str:
    if chipset:
        stub = _MOBO_NOISE.sub(" ", name)
        stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
        stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:30]
        return f"{brand.lower()}_{chipset.lower()}_{stub}" if stub else f"{brand.lower()}_{chipset.lower()}"
    stub = _MOBO_NOISE.sub(" ", name)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:50]
    return f"{brand.lower()}_{stub}" if stub else brand.lower()


def clean_motherboard_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_mobo_brand(norm_name)
    chipset = extract_mobo_chipset(norm_name)
    socket = extract_mobo_socket(norm_name)
    form_factor = extract_mobo_form_factor(norm_name)
    ram_type = extract_mobo_ram_type(norm_name)
    wifi = detect_wifi(norm_name)
    m2_slots = extract_mobo_m2_slots(norm_name)
    match_key = build_mobo_match_key(brand, chipset, norm_name)

    specs = {
        "chipset":    chipset,
        "socket":     socket,
        "form_factor": form_factor,
        "ram_type":   ram_type,
        "wifi":       wifi,
        "m2_slots":   m2_slots,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields (used by matcher)
        "capacity": socket, "generation": chipset,
        "speed": None, "latency": None, "form_factor": form_factor,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# SSD-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_SSD_BRANDS = [
    "Samsung", "WD", "Western Digital", "Kingston", "Crucial", "Seagate",
    "Silicon Power", "Transcend", "Lexar", "Patriot", "PNY", "Corsair",
    "Gigabyte", "ADATA", "Team", "Sabrent", "Netac", "XPG",
    "Colorful", "Acer", "HP", "Fanxiang", "Inland", "SK Hynix",
]

SSD_BRAND_CANONICAL = {
    "western digital": "WD",
    "wd": "WD",
    "silicon power": "Silicon Power",
    "sk hynix": "SK Hynix",
}


def extract_ssd_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_SSD_BRANDS:
        if nl.startswith(brand.lower()):
            return SSD_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_ssd_capacity(name: str) -> str | None:
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*TB\b", name, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return f"{int(val)}TB" if val == int(val) else f"{val}TB"
    m = re.search(r"\b(\d+)\s*GB\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}GB"
    return None


def extract_ssd_interface(name: str) -> str | None:
    if re.search(r"\b(pcie\s*gen\s*5|gen\s*5|nvme\s*gen\s*5)\b", name, re.IGNORECASE):
        return "NVMe Gen5"
    if re.search(r"\b(pcie\s*gen\s*4|gen\s*4|nvme\s*gen\s*4)\b", name, re.IGNORECASE):
        return "NVMe Gen4"
    if re.search(r"\b(pcie\s*gen\s*3|gen\s*3|nvme\s*gen\s*3)\b", name, re.IGNORECASE):
        return "NVMe Gen3"
    if re.search(r"\b(nvme|m\.?2\s*nvme|pcie)\b", name, re.IGNORECASE):
        return "NVMe"
    if re.search(r"\b(sata|2\.5)\b", name, re.IGNORECASE):
        return "SATA"
    if re.search(r"\bm\.?2\b", name, re.IGNORECASE):
        return "NVMe"
    return None


def extract_ssd_form_factor(name: str) -> str:
    if re.search(r"\b2\.5\b", name):
        return "2.5\""
    if re.search(r"\bm\.?2\b", name, re.IGNORECASE):
        return "M.2"
    return "M.2"


def extract_nand_type(name: str) -> str | None:
    if re.search(r"\bQLC\b", name, re.IGNORECASE):
        return "QLC"
    if re.search(r"\bTLC\b", name, re.IGNORECASE):
        return "TLC"
    if re.search(r"\bMLC\b", name, re.IGNORECASE):
        return "MLC"
    if re.search(r"\bSLC\b", name, re.IGNORECASE):
        return "SLC"
    return None


_SSD_NOISE = re.compile(
    r"\b(solid\s*state\s*drive|ssd|nvme|sata|m\.?2|pcie|gen\s*\d|internal|"
    r"desktop|laptop|gaming|drive|disk|flash|tlc|qlc|mlc|slc|3d\s*nand|"
    r"nand|gb|tb|read|write|gbps|mbs|mb\/?s|gb\/?s)\b",
    re.IGNORECASE,
)


def build_ssd_match_key(brand: str, capacity: str | None, interface: str | None, name: str) -> str:
    parts = [brand.lower()]
    if capacity:
        parts.append(capacity.lower())
    if interface:
        parts.append(interface.lower().replace(" ", "_"))
    stub = _SSD_NOISE.sub(" ", name)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:25]
    if stub:
        parts.append(stub)
    return "_".join(parts)


def clean_ssd_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_ssd_brand(norm_name)
    capacity = extract_ssd_capacity(norm_name)
    interface = extract_ssd_interface(norm_name)
    form_factor = extract_ssd_form_factor(norm_name)
    nand_type = extract_nand_type(norm_name)
    match_key = build_ssd_match_key(brand, capacity, interface, norm_name)

    specs = {
        "capacity":    capacity,
        "interface":   interface,
        "form_factor": form_factor,
        "nand_type":   nand_type,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields (used by matcher)
        "capacity": capacity, "generation": interface,
        "speed": None, "latency": None, "form_factor": form_factor,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# HDD-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_HDD_BRANDS = ["Seagate", "WD", "Western Digital", "Toshiba", "HGST", "Hitachi"]

HDD_BRAND_CANONICAL = {"western digital": "WD", "wd": "WD", "hgst": "HGST"}


def extract_hdd_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_HDD_BRANDS:
        if nl.startswith(brand.lower()):
            return HDD_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_hdd_capacity(name: str) -> str | None:
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*TB\b", name, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return f"{int(val)}TB" if val == int(val) else f"{val}TB"
    m = re.search(r"\b(\d+)\s*GB\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}GB"
    return None


def extract_hdd_rpm(name: str) -> str | None:
    m = re.search(r"\b(7200|5400|5900|10000)\s*(?:rpm|RPM)\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}RPM"
    return None


def extract_hdd_form_factor(name: str) -> str:
    if re.search(r"\b2\.5\b", name):
        return "2.5\""
    if re.search(r"\b3\.5\b", name):
        return "3.5\""
    return "3.5\""


def build_hdd_match_key(brand: str, capacity: str | None, name: str) -> str:
    parts = [brand.lower()]
    if capacity:
        parts.append(capacity.lower())
    stub = re.sub(r"\b(hard\s*disk|hdd|drive|internal|external|desktop|laptop|rpm|\d+rpm|tb|gb)\b",
                  " ", name, flags=re.IGNORECASE)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:30]
    if stub:
        parts.append(stub)
    return "_".join(parts)


def clean_hdd_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_hdd_brand(norm_name)
    capacity = extract_hdd_capacity(norm_name)
    rpm = extract_hdd_rpm(norm_name)
    form_factor = extract_hdd_form_factor(norm_name)
    cache = extract_hdd_cache(norm_name)
    match_key = build_hdd_match_key(brand, capacity, norm_name)

    specs = {
        "capacity":    capacity,
        "rpm":         rpm,
        "form_factor": form_factor,
        "cache":       cache,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields
        "capacity": capacity, "generation": None, "speed": rpm,
        "latency": None, "form_factor": form_factor,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# PSU-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_PSU_BRANDS = [
    "Corsair", "Seasonic", "EVGA", "Antec", "Thermaltake", "DeepCool",
    "Cooler Master", "be quiet!", "NZXT", "Fractal", "FSP", "Silverstone",
    "Lian Li", "Super Flower", "Cougar", "Enermax", "Gigabyte", "MSI",
    "Gamdias", "Gamemax", "Redragon", "Aigo", "ABKO", "Chieftec",
    "BitFenix", "XPG", "Phanteks",
]

PSU_BRAND_CANONICAL = {
    "be quiet!": "be quiet!",
    "cooler master": "Cooler Master",
    "lian li": "Lian Li",
    "super flower": "Super Flower",
}


def extract_psu_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_PSU_BRANDS:
        if nl.startswith(brand.lower()):
            return PSU_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_psu_wattage(name: str) -> str | None:
    m = re.search(r"\b(\d{3,4})\s*[Ww]\b", name)
    if m:
        return f"{m.group(1)}W"
    return None


def extract_psu_efficiency(name: str) -> str | None:
    if re.search(r"\b(titanium)\b", name, re.IGNORECASE):
        return "80+ Titanium"
    if re.search(r"\b(platinum)\b", name, re.IGNORECASE):
        return "80+ Platinum"
    if re.search(r"\b(gold)\b", name, re.IGNORECASE):
        return "80+ Gold"
    if re.search(r"\b(silver)\b", name, re.IGNORECASE):
        return "80+ Silver"
    if re.search(r"\b(bronze)\b", name, re.IGNORECASE):
        return "80+ Bronze"
    if re.search(r"\b(white)\b", name, re.IGNORECASE):
        return "80+ White"
    if re.search(r"\b80\+", name, re.IGNORECASE):
        return "80+"
    return None


def extract_modularity(name: str) -> str | None:
    if re.search(r"\bfully\s*modular\b", name, re.IGNORECASE):
        return "Fully Modular"
    if re.search(r"\bsemi.?\s*modular\b", name, re.IGNORECASE):
        return "Semi-Modular"
    if re.search(r"\bnon.?\s*modular\b|\bnot\s*modular\b", name, re.IGNORECASE):
        return "Non-Modular"
    if re.search(r"\bmodular\b", name, re.IGNORECASE):
        return "Fully Modular"
    return None


def extract_psu_form_factor(name: str) -> str:
    if re.search(r"\bSFX-L\b", name, re.IGNORECASE):
        return "SFX-L"
    if re.search(r"\bSFX\b", name, re.IGNORECASE):
        return "SFX"
    if re.search(r"\bTFX\b", name, re.IGNORECASE):
        return "TFX"
    return "ATX"


def build_psu_match_key(brand: str, wattage: str | None, efficiency: str | None, name: str) -> str:
    parts = [brand.lower()]
    if wattage:
        parts.append(wattage.lower())
    if efficiency:
        parts.append(efficiency.lower().replace(" ", "_").replace("+", "plus"))
    stub = re.sub(r"\b(power\s*supply|psu|watt|atx|modular|semi|fully|non|w\b|\d{3,4}w|80\+|\w+\s*\+)\b",
                  " ", name, flags=re.IGNORECASE)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:25]
    if stub:
        parts.append(stub)
    return "_".join(parts)


def clean_psu_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_psu_brand(norm_name)
    wattage = extract_psu_wattage(norm_name)
    efficiency = extract_psu_efficiency(norm_name)
    modularity = extract_modularity(norm_name)
    form_factor = extract_psu_form_factor(norm_name)
    atx30 = detect_atx30(norm_name)
    match_key = build_psu_match_key(brand, wattage, efficiency, norm_name)

    specs = {
        "wattage":     wattage,
        "efficiency":  efficiency,
        "modularity":  modularity,
        "form_factor": form_factor,
        "atx30":       atx30,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields
        "capacity": wattage, "generation": efficiency,
        "speed": None, "latency": None, "form_factor": form_factor,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# CPU Cooler-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_COOLER_BRANDS = [
    "DeepCool", "Cooler Master", "NZXT", "Corsair", "Arctic", "Noctua",
    "be quiet!", "Antec", "Thermaltake", "Scythe", "ID-Cooling", "Lian Li",
    "Zalman", "EK", "EKWB", "Fractal", "Phanteks", "Silverstone",
    "Cryorig", "Alpenfohn", "Enermax", "SilverStone", "Gamdias",
    "Redragon", "Darkflash", "ID Cooling", "Xilence",
]

COOLER_BRAND_CANONICAL = {
    "be quiet!": "be quiet!",
    "cooler master": "Cooler Master",
    "id-cooling": "ID-Cooling",
    "id cooling": "ID-Cooling",
    "ekwb": "EK",
}


def extract_cooler_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_COOLER_BRANDS:
        if nl.startswith(brand.lower()):
            return COOLER_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_cooler_type(name: str) -> str:
    if re.search(r"\b(liquid|aio|water\s*cooler|all.in.one)\b", name, re.IGNORECASE):
        for size in ["420", "360", "280", "240", "120"]:
            if re.search(rf"\b{size}\s*mm\b|\b{size}\b", name):
                return f"AIO {size}mm"
        return "AIO"
    # Also detect by radiator size alone
    for size in ["420", "360", "280", "240"]:
        if re.search(rf"\b{size}\s*mm\b|\b{size}\b", name):
            return f"AIO {size}mm"
    return "Air"


def extract_cooler_radiator(name: str) -> str | None:
    for size in ["420", "360", "280", "240", "120"]:
        if re.search(rf"\b{size}\s*mm\b|\b{size}\b", name):
            return f"{size}mm"
    return None


def extract_fan_size(name: str) -> str | None:
    """Return fan size for air coolers like '120mm', '140mm'."""
    if re.search(r"\b140\s*mm\b", name, re.IGNORECASE):
        return "140mm"
    if re.search(r"\b120\s*mm\b", name, re.IGNORECASE):
        return "120mm"
    if re.search(r"\b92\s*mm\b", name, re.IGNORECASE):
        return "92mm"
    return None


_COOLER_NOISE = re.compile(
    r"\b(cpu\s*cooler|cooler|cooling|fan|heatsink|heat\s*sink|radiator|"
    r"aio|liquid|water|air|tower|mm|rpm|tdp|lga\d*|am[345]|rgb|argb|"
    r"pwm|intel|amd|socket|compatible|black|white|silver|blue|red)\b",
    re.IGNORECASE,
)


def build_cooler_match_key(brand: str, cooler_type: str, name: str) -> str:
    parts = [brand.lower()]
    parts.append(cooler_type.lower().replace(" ", "_"))
    stub = _COOLER_NOISE.sub(" ", name)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:30]
    if stub:
        parts.append(stub)
    return "_".join(parts)


def clean_cooler_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_cooler_brand(norm_name)
    cooler_type = extract_cooler_type(norm_name)
    radiator = extract_cooler_radiator(norm_name)
    fan_size = extract_fan_size(norm_name) if cooler_type == "Air" else None
    match_key = build_cooler_match_key(brand, cooler_type, norm_name)

    specs = {
        "type":          cooler_type,
        "radiator_size": radiator,
        "fan_size":      fan_size,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields
        "capacity": radiator, "generation": cooler_type,
        "speed": None, "latency": None, "form_factor": "Desktop",
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Casing-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_CASING_BRANDS = [
    "NZXT", "Corsair", "Lian Li", "Antec", "Cooler Master", "Phanteks",
    "Fractal", "DeepCool", "Thermaltake", "be quiet!", "Silverstone",
    "Cougar", "ASUS", "MSI", "Gigabyte", "Zalman", "Aerocool",
    "Gamdias", "Redragon", "Darkflash", "Xigmatek", "Tecware",
    "View", "ID-Cooling", "In Win", "Jonsbo",
]

CASING_BRAND_CANONICAL = {
    "cooler master": "Cooler Master",
    "lian li": "Lian Li",
    "be quiet!": "be quiet!",
    "in win": "In Win",
    "id-cooling": "ID-Cooling",
}


def extract_casing_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_CASING_BRANDS:
        if nl.startswith(brand.lower()):
            return CASING_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_casing_form_factor(name: str) -> str:
    if re.search(r"\b(mini.?itx|mini\s+tower|itx)\b", name, re.IGNORECASE):
        return "Mini-ITX"
    if re.search(r"\b(micro.?atx|micro\s+tower|matx|m.?atx)\b", name, re.IGNORECASE):
        return "Micro-ATX"
    if re.search(r"\b(full\s*tower|e.?atx|xl\s*tower)\b", name, re.IGNORECASE):
        return "Full Tower"
    return "Mid Tower"


def extract_side_panel(name: str) -> str | None:
    if re.search(r"\btempered\s*glass\b|\b\bTG\b\b", name, re.IGNORECASE):
        return "Tempered Glass"
    if re.search(r"\bacrylic\b", name, re.IGNORECASE):
        return "Acrylic"
    if re.search(r"\bmesh\b", name, re.IGNORECASE):
        return "Mesh"
    if re.search(r"\bsolid\b", name, re.IGNORECASE):
        return "Solid"
    return None


def extract_psu_support(name: str) -> str:
    if re.search(r"\bSFX-L\b", name, re.IGNORECASE):
        return "SFX-L"
    if re.search(r"\bSFX\b", name, re.IGNORECASE):
        return "SFX"
    return "ATX"


_CASING_NOISE = re.compile(
    r"\b(case|casing|cabinet|chassis|gaming|tower|mid|full|mini|micro|"
    r"atx|itx|tempered\s*glass|tg|rgb|argb|black|white|silver|red|blue|"
    r"side\s*panel|mesh|fan|slot|bay|usb|type.?c)\b",
    re.IGNORECASE,
)


def build_casing_match_key(brand: str, form_factor: str, name: str) -> str:
    parts = [brand.lower()]
    parts.append(form_factor.lower().replace(" ", "_").replace("-", "_"))
    stub = _CASING_NOISE.sub(" ", name)
    stub = re.sub(r"[^a-zA-Z0-9 ]", " ", stub)
    stub = re.sub(r"\s+", "_", stub.strip().lower()).strip("_")[:30]
    if stub:
        parts.append(stub)
    return "_".join(parts)


def clean_casing_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_casing_brand(norm_name)
    form_factor = extract_casing_form_factor(norm_name)
    side_panel = extract_side_panel(norm_name)
    color = extract_color(norm_name)
    psu_support = extract_psu_support(norm_name)
    front_usb_c = detect_front_usb_c(norm_name)
    match_key = build_casing_match_key(brand, form_factor, norm_name)

    specs = {
        "form_factor": form_factor,
        "side_panel":  side_panel,
        "color":       color,
        "psu_support": psu_support,
        "front_usb_c": front_usb_c,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields
        "capacity": None, "generation": form_factor,
        "speed": None, "latency": None, "form_factor": form_factor,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Monitor-specific extraction helpers
# ---------------------------------------------------------------------------

KNOWN_MONITOR_BRANDS = [
    "Samsung", "LG", "Dell", "ASUS", "AOC", "Acer", "BenQ", "ViewSonic",
    "Gigabyte", "MSI", "Philips", "HP", "Lenovo", "Mi", "Xiaomi",
]

MONITOR_BRAND_CANONICAL = {}


def extract_monitor_brand(name: str) -> str:
    nl = name.lower()
    for brand in KNOWN_MONITOR_BRANDS:
        if nl.startswith(brand.lower()):
            return MONITOR_BRAND_CANONICAL.get(brand.lower(), brand)
    return extract_brand(name)


def extract_screen_size(name: str) -> str | None:
    m = re.search(r"\b(\d{2}(?:\.\d)?)\s*(?:inch|\"|″|')\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}\""
    m = re.search(r"\b(\d{2}(?:\.\d)?)\s*in\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}\""
    return None


def extract_resolution(name: str) -> str | None:
    if re.search(r"\b(5120\s*[x×]\s*1440|5k2k|super\s*ultra\s*wide)\b", name, re.IGNORECASE):
        return "5120x1440"
    if re.search(r"\b(3840\s*[x×]\s*1600|uwqhd)\b", name, re.IGNORECASE):
        return "3840x1600"
    if re.search(r"\b(3440\s*[x×]\s*1440|uwqhd|ultra\s*wide\s*qhd)\b", name, re.IGNORECASE):
        return "3440x1440"
    if re.search(r"\b(2560\s*[x×]\s*1440|1440p|2k|qhd|wqhd)\b", name, re.IGNORECASE):
        return "2560x1440"
    if re.search(r"\b(3840\s*[x×]\s*2160|4k|uhd)\b", name, re.IGNORECASE):
        return "3840x2160"
    if re.search(r"\b(2560\s*[x×]\s*1080|uwfhd|ultra\s*wide\s*fhd)\b", name, re.IGNORECASE):
        return "2560x1080"
    if re.search(r"\b(1920\s*[x×]\s*1080|1080p|fhd|full\s*hd)\b", name, re.IGNORECASE):
        return "1920x1080"
    if re.search(r"\b(1366\s*[x×]\s*768|hd|720p)\b", name, re.IGNORECASE):
        return "1366x768"
    return None


def extract_refresh_rate(name: str) -> str | None:
    m = re.search(r"\b(\d{2,3})\s*[Hh][Zz]\b", name)
    if m:
        return f"{m.group(1)}Hz"
    return None


def extract_panel_type(name: str) -> str | None:
    if re.search(r"\bOLED\b", name, re.IGNORECASE):
        return "OLED"
    if re.search(r"\bIPS\b", name, re.IGNORECASE):
        return "IPS"
    if re.search(r"\bVA\b", name, re.IGNORECASE):
        return "VA"
    if re.search(r"\bTN\b", name, re.IGNORECASE):
        return "TN"
    if re.search(r"\bNano\s*IPS\b", name, re.IGNORECASE):
        return "Nano IPS"
    return None


def extract_response_time(name: str) -> str | None:
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*ms\b", name, re.IGNORECASE)
    if m:
        return f"{m.group(1)}ms"
    return None


def build_monitor_match_key(brand: str, size: str | None, resolution: str | None, refresh: str | None) -> str:
    parts = [brand.lower()]
    if size:
        parts.append(size.lower().replace('"', 'inch'))
    if resolution:
        parts.append(resolution.lower().replace("x", "x"))
    if refresh:
        parts.append(refresh.lower())
    return "_".join(parts)


def clean_monitor_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_monitor_brand(norm_name)
    size = extract_screen_size(norm_name)
    resolution = extract_resolution(norm_name)
    refresh_rate = extract_refresh_rate(norm_name)
    panel_type = extract_panel_type(norm_name)
    response_time = extract_response_time(norm_name)
    curved = bool(re.search(r"\bcurved\b", norm_name, re.IGNORECASE))
    hdr = bool(re.search(r"\bHDR\b", norm_name, re.IGNORECASE))
    match_key = build_monitor_match_key(brand, size, resolution, refresh_rate)

    specs = {
        "screen_size":    size,
        "resolution":     resolution,
        "refresh_rate":   refresh_rate,
        "panel_type":     panel_type,
        "response_time":  response_time,
        "curved":         curved,
        "hdr":            hdr,
    }

    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        # Flat compat fields
        "capacity": size, "generation": resolution,
        "speed": refresh_rate, "latency": None, "form_factor": None,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# RAM cleaner (default)
# ---------------------------------------------------------------------------

def clean_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)

    brand = extract_brand(norm_name)
    capacity = extract_capacity(norm_name)
    generation = extract_generation(norm_name)
    speed = extract_speed(norm_name)
    latency = extract_latency(norm_name)
    form_factor = extract_form_factor(norm_name)
    kit = extract_kit(norm_name) or extract_kit(name)
    rgb = detect_rgb(norm_name)
    match_key = build_match_key(brand, capacity, generation, speed)

    raw_mpn = raw.get("mpn") or raw.get("specs", {}).get("MPN")
    if not raw_mpn:
        m = re.search(r"#([A-Z0-9][A-Z0-9\-]{3,})", name, re.IGNORECASE)
        if m:
            raw_mpn = m.group(1)
    mpn = raw_mpn.strip().upper() if raw_mpn else None

    if not generation:
        spec_type = (
            raw.get("specs", {}).get("Type")
            or raw.get("inline_specs", {}).get("RAM Type")
            or ""
        )
        gen_match = re.search(r"DDR[345]", spec_type, re.IGNORECASE)
        if gen_match:
            generation = gen_match.group(0).upper()

    heatsink = detect_heatsink(norm_name)
    ecc = detect_ecc(norm_name)
    specs = {
        "capacity":    capacity,
        "generation":  generation,
        "speed":       speed,
        "latency":     latency,
        "form_factor": form_factor,
        "kit":         kit,
        "rgb":         rgb,
        "heatsink":    heatsink,
        "ecc":         ecc,
    }

    return {
        "raw_name": name,
        "mpn": mpn,
        "price_bdt": raw.get("price_bdt"),
        "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"),
        "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"),
        "name": norm_name,
        "brand": brand,
        # Flat compat fields (used by matcher)
        "capacity": capacity,
        "generation": generation,
        "speed": speed,
        "latency": latency,
        "form_factor": form_factor,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Laptop RAM cleaner (SO-DIMM)
# ---------------------------------------------------------------------------

def clean_laptop_ram_record(raw: dict) -> dict:
    """Same extraction as desktop RAM but always forces form_factor=SO-DIMM."""
    result = clean_record(raw)
    result["form_factor"] = "SO-DIMM"
    result["specs"]["form_factor"] = "SO-DIMM"
    return result


# ---------------------------------------------------------------------------
# Casing cooler / case fan helpers
# ---------------------------------------------------------------------------

def extract_fan_blade_size(name: str) -> str | None:
    m = re.search(r"\b(200|180|140|120|92|80)\s*mm\b", name, re.IGNORECASE)
    return f"{m.group(1)}mm" if m else None


def extract_fan_pack(name: str) -> str | None:
    m = re.search(r"\b(\d+)\s*(?:pack|pcs?|in\s*1)\b", name, re.IGNORECASE)
    if m and int(m.group(1)) > 1:
        return f"{m.group(1)}-pack"
    return None


def build_fan_match_key(brand: str, size: str | None, norm_name: str) -> str:
    parts = [brand.lower().replace(" ", "_")]
    if size:
        parts.append(size.lower().replace(" ", "_"))
    slug = re.sub(r"[^a-z0-9]+", "_", norm_name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")[:45]
    parts.append(slug)
    return "_".join(p for p in parts if p)


def clean_casing_cooler_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand_lower = norm_name.lower()
    # Reuse extract_cooler_brand for fan brands (same pool)
    brand = extract_cooler_brand(norm_name)
    size = extract_fan_blade_size(norm_name)
    pack = extract_fan_pack(norm_name)
    rgb = detect_rgb(norm_name)
    match_key = build_fan_match_key(brand, size, norm_name)

    specs = {
        "capacity":    size,
        "generation":  None,
        "speed":       pack,
        "form_factor": "Case Fan",
        "rgb":         rgb,
    }
    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        "capacity": size,
        "generation": None,
        "speed": pack,
        "form_factor": "Case Fan",
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# ODD (Optical Disk Drive) helpers
# ---------------------------------------------------------------------------

def extract_odd_type(name: str) -> str | None:
    n = name.upper()
    if "BLU-RAY" in n or "BLURAY" in n or "BD" in n:
        return "Blu-ray"
    if "DVD" in n:
        return "DVD"
    if "CD" in n:
        return "CD"
    return None


def extract_odd_interface(name: str) -> str | None:
    n = name.upper()
    if "USB" in n:
        return "USB"
    if "SLIM" in n or "LAPTOP" in n:
        return "Slim SATA"
    return "SATA"


def clean_odd_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_cooler_brand(norm_name) or extract_brand(norm_name)
    drive_type = extract_odd_type(norm_name)
    interface = extract_odd_interface(norm_name)
    slug = re.sub(r"[^a-z0-9]+", "_", norm_name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")[:45]
    match_key = f"{brand.lower().replace(' ', '_')}_{slug}"

    specs = {
        "capacity":    None,
        "generation":  drive_type,
        "speed":       None,
        "form_factor": interface,
    }
    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        "capacity": None,
        "generation": drive_type,
        "speed": None,
        "form_factor": interface,
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Portable HDD helpers
# ---------------------------------------------------------------------------

def extract_usb_interface(name: str) -> str | None:
    n = name.upper()
    if re.search(r"USB\s*4", n):
        return "USB 4"
    if re.search(r"USB\s*3\.2\s*GEN\s*2", n):
        return "USB 3.2 Gen2"
    if re.search(r"USB\s*3\.2", n):
        return "USB 3.2"
    if re.search(r"USB\s*3\.1\s*GEN\s*2", n):
        return "USB 3.1 Gen2"
    if re.search(r"USB\s*3\.1", n):
        return "USB 3.1"
    if re.search(r"USB\s*3\.0|USB\s*3\b", n):
        return "USB 3.0"
    if re.search(r"USB-?C|TYPE-?C", n):
        return "USB-C"
    if re.search(r"USB", n):
        return "USB"
    return None


def clean_portable_hdd_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_hdd_brand(norm_name)
    capacity = extract_hdd_capacity(norm_name)
    interface = extract_usb_interface(norm_name) or "USB"

    parts = [brand.lower().replace(" ", "_")]
    if capacity:
        parts.append(capacity.lower())
    parts.append(interface.lower().replace(" ", "_").replace(".", ""))
    slug = re.sub(r"[^a-z0-9]+", "_", norm_name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")[:35]
    parts.append(slug)
    match_key = "_".join(p for p in parts if p)

    specs = {
        "capacity":    capacity,
        "generation":  interface,
        "speed":       None,
        "form_factor": "External",
    }
    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        "capacity": capacity,
        "generation": interface,
        "speed": None,
        "form_factor": "External",
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Portable SSD helpers
# ---------------------------------------------------------------------------

def clean_portable_ssd_record(raw: dict) -> dict:
    name = raw.get("name", "")
    norm_name = normalize_name(name)
    brand = extract_ssd_brand(norm_name)
    capacity = extract_ssd_capacity(norm_name)
    interface = extract_usb_interface(norm_name) or "USB"

    parts = [brand.lower().replace(" ", "_")]
    if capacity:
        parts.append(capacity.lower())
    parts.append(interface.lower().replace(" ", "_").replace(".", ""))
    slug = re.sub(r"[^a-z0-9]+", "_", norm_name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")[:35]
    parts.append(slug)
    match_key = "_".join(p for p in parts if p)

    specs = {
        "capacity":    capacity,
        "generation":  interface,
        "speed":       None,
        "form_factor": "External",
    }
    return {
        "raw_name": name, "mpn": None,
        "price_bdt": raw.get("price_bdt"), "in_stock": raw.get("in_stock"),
        "product_url": raw.get("product_url"), "source": raw.get("source"),
        "scraped_at": raw.get("scraped_at"), "pc_bundle_only": bool(raw.get("pc_bundle_only", False)), "name": norm_name,
        "brand": brand,
        "capacity": capacity,
        "generation": interface,
        "speed": None,
        "form_factor": "External",
        "match_key": match_key,
        "specs": specs,
    }


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

def find_latest_raw_file() -> Path:
    raw_dir = Path("data/raw")
    files = sorted(raw_dir.glob("*_ram_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(
            "No raw files found in data/raw/. "
            "Run a scraper first: python scrapers/startech/scrape_ram.py --save"
        )
    return files[0]


def print_summary(raw_records: list[dict], clean_records: list[dict], label: str = "") -> None:
    total = len(clean_records)
    priced = sum(1 for r in clean_records if r["price_bdt"] is not None)
    in_stock = sum(1 for r in clean_records if r["in_stock"])
    unique_keys = len({r["match_key"] for r in clean_records})

    print(f"\n{'='*65}")
    print(f"  Cleaning summary — {label or 'RAM'}")
    print(f"{'='*65}")
    print(f"  Total records   : {total}")
    print(f"  With price      : {priced}  ({100*priced//total if total else 0}%)")
    print(f"  In stock        : {in_stock}")
    print(f"  Unique match keys: {unique_keys}  (potential duplicate listings: {total - unique_keys})")

    print(f"\n--- Before / After examples (first 6 records with prices) ---\n")
    shown = 0
    for raw, clean in zip(raw_records, clean_records):
        if clean["price_bdt"] is None:
            continue
        print(f"  Raw : {raw['name']}")
        print(f"  Clean name: {clean['name']}")
        print(f"  -> specs: {clean.get('specs', {})}")
        print(f"  -> match_key: {clean['match_key']}")
        print()
        shown += 1
        if shown >= 6:
            break

    gaps = [r for r in clean_records if not r.get("specs")]
    if gaps:
        print(f"--- {len(gaps)} records with no specs dict (check these) ---\n")
        for r in gaps[:4]:
            print(f"  {r['raw_name']}")
            print()


def main():
    parser = argparse.ArgumentParser(description="Normalize raw scraper data")
    parser.add_argument("--input", type=Path, default=None,
                        help="Path to raw JSON file (default: latest in data/raw/)")
    parser.add_argument("--category",
                        choices=["ram", "laptop_ram", "gpu", "processor", "motherboard",
                                 "ssd", "portable_ssd", "hdd", "portable_hdd",
                                 "psu", "cooler", "casing_cooler", "casing", "odd", "monitor"],
                        default=None,
                        help="Product category — inferred from filename if omitted")
    args = parser.parse_args()

    input_path = args.input or find_latest_raw_file()
    print(f"Loading: {input_path}")

    stem_parts = input_path.stem.split("_")
    retailer = stem_parts[0] if stem_parts else "raw"
    category = args.category or (stem_parts[1] if len(stem_parts) > 1 else "ram")

    with open(input_path, encoding="utf-8") as f:
        raw_records = json.load(f)

    CLEANERS = {
        "gpu":           clean_gpu_record,
        "processor":     clean_processor_record,
        "motherboard":   clean_motherboard_record,
        "ssd":           clean_ssd_record,
        "portable_ssd":  clean_portable_ssd_record,
        "hdd":           clean_hdd_record,
        "portable_hdd":  clean_portable_hdd_record,
        "psu":           clean_psu_record,
        "cooler":        clean_cooler_record,
        "casing_cooler": clean_casing_cooler_record,
        "casing":        clean_casing_record,
        "odd":           clean_odd_record,
        "monitor":       clean_monitor_record,
        "laptop_ram":    clean_laptop_ram_record,
    }
    cleaner = CLEANERS.get(category, clean_record)

    # Build cleaned records, preserving the retailer's raw spec data separately.
    # inline_specs  = key/value attributes from the listing page (all retailers)
    # specs         = full spec table from detail-page enrichment (StarTech enrich.py)
    # Together they form seller_raw_specs used for cross-seller spec comparison.
    clean_records = []
    for raw in raw_records:
        cleaned = cleaner(raw)
        inline = raw.get("inline_specs") or {}
        raw_spec_table = raw.get("specs") or {}
        # Detail-page specs override inline where keys clash (more authoritative)
        cleaned["seller_raw_specs"] = {**inline, **raw_spec_table}
        # Pass stock_status through; derive from in_stock boolean if scraper didn't set it
        cleaned["stock_status"] = raw.get("stock_status") or (
            "in_stock" if raw.get("in_stock") else "out_of_stock"
        )
        cleaned["pc_bundle_only"] = bool(raw.get("pc_bundle_only", False))
        clean_records.append(cleaned)

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{retailer}_{category}_clean.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(clean_records, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_path}")

    label = f"{retailer.title()} {category.upper()}"
    print_summary(raw_records, clean_records, label=label)


if __name__ == "__main__":
    main()
