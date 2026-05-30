"""
Stage 2: Cross-retailer product matcher.

The problem:
  "Kingston FURY Beast 8GB 3200MHz DDR4 Desktop RAM"  (StarTech)
  "Kingston Fury Beast DDR4 8GB 3200MHz RAM"          (Ryans)
  → same physical product, different names. We must link them.

Two-level approach:
  Level 1  match_key (brand + capacity + generation + speed)
           Groups candidates cheaply. Same key = worth comparing.

  Level 2  rapidfuzz on model series
           The part of the name that's left after stripping brand and specs.
           "FURY Beast" ≈ "Fury Beast"  → same product  (high score)
           "Vulcan Z"   ≈ "Delta RGB"   → different      (low score)

Union-find lets transitive matches work: if A≈B and B≈C, all three become one group.

Usage:
  python cleaning/matcher.py            # demo with synthetic cross-retailer data
  python cleaning/matcher.py --input data/processed/startech_ram_clean.json
"""

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SIMILARITY_THRESHOLD = 80  # 0–100; at or above this = same product

# Tokens to strip when extracting model series from a product name
_SPEC_RE = re.compile(
    r"\b\d+\s*GB\b"                          # capacity (RAM or VRAM)
    r"|\bDDR[345]\b"                          # RAM generation
    r"|\bGDDR[5-7]X?\b"                      # GPU memory type
    r"|\b\d{3,5}\s*MHz\b"                     # speed
    r"|\bCL\d+\b"                             # latency
    r"|\b(RAM|Memory|Desktop|Laptop|Gaming|Heatsink|UDIMM|U-DIMM|DIMM|PC|"
    r"Graphics|Card|GeForce|Radeon|Edition)\b"  # generic product words
    r"|#[A-Z0-9][A-Z0-9\-]{3,}",             # embedded MPNs
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Model-series extraction
# ---------------------------------------------------------------------------

def extract_model_series(name: str, brand: str) -> str:
    """
    Return the model series portion of a product name.
    Example: "Kingston FURY Beast 8GB DDR4 3200MHz Desktop RAM"
             brand="Kingston"  →  "FURY Beast"
    This string is what we fuzzy-match across retailers.
    """
    # Remove brand prefix (case-insensitive)
    s = re.sub(r"(?i)^" + re.escape(brand), "", name).strip()
    # Remove spec tokens
    s = _SPEC_RE.sub(" ", s)
    # Collapse whitespace and trailing punctuation
    s = re.sub(r"[\s\-]+", " ", s).strip(" -–()")
    return s


# ---------------------------------------------------------------------------
# Union-find (disjoint set) — groups transitive matches
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int):
        self._p = list(range(n))

    def find(self, x: int) -> int:
        while self._p[x] != x:
            self._p[x] = self._p[self._p[x]]   # path compression
            x = self._p[x]
        return x

    def union(self, x: int, y: int) -> None:
        self._p[self.find(x)] = self.find(y)


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def _group_within_key(records: list[dict], threshold: int) -> list[list[dict]]:
    """
    Within a single match_key bucket, form sub-groups where each sub-group
    represents one physical product. Uses union-find for transitive merges.

    Two passes:
      Pass 1 — MPN exact match: if two cross-retailer records share an MPN,
               merge them unconditionally (100% confident).
      Pass 2 — Fuzzy match: for any remaining cross-retailer pairs not yet
               in the same group, merge if model-series similarity >= threshold.

    Keeping both passes inside the match_key bucket means a Ryans record
    without an MPN can still fuzzy-match against a StarTech record that
    has one, as long as they landed in the same bucket.

    Same-retailer records are never auto-merged (distinct SKUs stay separate).
    """
    n = len(records)
    uf = _UnionFind(n)

    # Pass 1: MPN exact match (cross-retailer only)
    mpn_index: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        mpn = r.get("mpn")
        if not mpn:
            continue
        key = mpn.upper()
        for j in mpn_index.get(key, []):
            if records[j].get("source") != r.get("source"):
                uf.union(i, j)
        mpn_index.setdefault(key, []).append(i)

    # Pass 2: fuzzy on model series (cross-retailer, not already merged)
    series = [extract_model_series(r["name"], r.get("brand", "")) for r in records]
    for i in range(n):
        for j in range(i + 1, n):
            if records[i].get("source") == records[j].get("source"):
                continue
            if uf.find(i) == uf.find(j):
                continue  # already in the same group
            score = fuzz.token_sort_ratio(series[i], series[j])
            if score >= threshold:
                uf.union(i, j)

    groups: dict[int, list[dict]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(records[i])
    return list(groups.values())


@dataclass
class CanonicalProduct:
    """One physical product, possibly listed by multiple retailers."""
    match_key: str
    brand: str
    capacity: str | None
    generation: str | None
    speed: str | None
    model_series: str
    canonical_name: str
    form_factor: str | None = None
    specs: dict = field(default_factory=dict)
    listings: list[dict] = field(default_factory=list)

    @property
    def cheapest_listing(self) -> dict | None:
        priced = [l for l in self.listings if l["price_bdt"] and l["in_stock"]]
        return min(priced, key=lambda l: l["price_bdt"]) if priced else None

    @property
    def retailer_count(self) -> int:
        return len({l["source"] for l in self.listings})

    def to_dict(self) -> dict:
        c = self.cheapest_listing
        return {
            "match_key": self.match_key,
            "brand": self.brand,
            "capacity": self.capacity,
            "generation": self.generation,
            "speed": self.speed,
            "model_series": self.model_series,
            "form_factor": self.form_factor,
            "specs": self.specs,
            "canonical_name": self.canonical_name,
            "retailer_count": self.retailer_count,
            "cheapest_source": c["source"] if c else None,
            "cheapest_price_bdt": c["price_bdt"] if c else None,
            "listings": self.listings,
        }


def _make_canonical(group: list[dict], key: str) -> CanonicalProduct:
    """Build a CanonicalProduct from a resolved group of records."""
    priced = [r for r in group if r.get("price_bdt") is not None]
    rep = max(priced or group, key=lambda r: len(r["name"]))
    series = extract_model_series(rep["name"], rep.get("brand", ""))
    return CanonicalProduct(
        match_key=key,
        brand=rep.get("brand", ""),
        capacity=rep.get("capacity"),
        generation=rep.get("generation"),
        speed=rep.get("speed"),
        model_series=series,
        form_factor=rep.get("form_factor"),
        specs=rep.get("specs", {}),
        canonical_name=rep["name"],
        listings=[
            {
                "source": r["source"],
                "mpn": r.get("mpn"),
                "price_bdt": r["price_bdt"],
                "in_stock": r["in_stock"],
                "stock_status": r.get("stock_status") or ("in_stock" if r["in_stock"] else "out_of_stock"),
                "pc_bundle_only": bool(r.get("pc_bundle_only", False)),
                "product_url": r["product_url"],
                "scraped_at": r.get("scraped_at"),
                "seller_raw_specs": r.get("seller_raw_specs") or {},
            }
            for r in group
        ],
    )


def match_products(
    all_records: list[dict],
    threshold: int = SIMILARITY_THRESHOLD,
) -> list[CanonicalProduct]:
    """
    Main entry point. Accepts cleaned records from any number of retailers.
    Returns canonical products, each with a `listings` list showing
    every retailer's price for that product.

    Strategy: group by match_key first, then within each bucket apply
    _group_within_key which handles both MPN exact-match and fuzzy fallback
    in a single unified pass. This ensures a no-MPN Ryans record can still
    match a MPN-bearing StarTech record that landed in the same bucket.
    """
    by_key: dict[str, list[dict]] = {}
    for r in all_records:
        by_key.setdefault(r["match_key"], []).append(r)

    products: list[CanonicalProduct] = []
    for key, candidates in by_key.items():
        for group in _group_within_key(candidates, threshold):
            products.append(_make_canonical(group, key))

    return products


# ---------------------------------------------------------------------------
# Synthetic test data — realistic "Ryans" records for demo
# These simulate what Ryans listings would look like after cleaning.
# Deliberately includes both true matches AND one false-positive trap.
# ---------------------------------------------------------------------------

SYNTHETIC_RYANS = [
    # Should MATCH StarTech (same product, different phrasing)
    {
        "name": "Kingston Fury Beast DDR4 8GB 3200MHz RAM",
        "brand": "Kingston", "capacity": "8GB", "generation": "DDR4",
        "speed": "3200MHz", "latency": None, "form_factor": "Desktop",
        "match_key": "kingston_8gb_ddr4_3200mhz",
        "price_bdt": 8400.0, "in_stock": True,
        "product_url": "https://www.ryans.com/kingston-fury-beast-8gb-ddr4",
        "source": "Ryans", "scraped_at": "2026-05-26T12:00:00+00:00",
    },
    {
        "name": "Corsair Vengeance LPX 8GB DDR4 3200MHz Desktop Memory",
        "brand": "Corsair", "capacity": "8GB", "generation": "DDR4",
        "speed": "3200MHz", "latency": None, "form_factor": "Desktop",
        "match_key": "corsair_8gb_ddr4_3200mhz",
        "price_bdt": 8300.0, "in_stock": True,
        "product_url": "https://www.ryans.com/corsair-vengeance-lpx-8gb",
        "source": "Ryans", "scraped_at": "2026-05-26T12:00:00+00:00",
    },
    {
        "name": "G.Skill Ripjaws V 16GB DDR4 3200MHz Black",
        "brand": "G.Skill", "capacity": "16GB", "generation": "DDR4",
        "speed": "3200MHz", "latency": None, "form_factor": "Desktop",
        "match_key": "g.skill_16gb_ddr4_3200mhz",
        "price_bdt": 15200.0, "in_stock": True,
        "product_url": "https://www.ryans.com/gskill-ripjaws-v-16gb",
        "source": "Ryans", "scraped_at": "2026-05-26T12:00:00+00:00",
    },
    {
        "name": "Netac Basic DDR4 8GB 3200MHz Desktop RAM",
        "brand": "Netac", "capacity": "8GB", "generation": "DDR4",
        "speed": "3200MHz", "latency": None, "form_factor": "Desktop",
        "match_key": "netac_8gb_ddr4_3200mhz",
        "price_bdt": 8500.0, "in_stock": True,
        "product_url": "https://www.ryans.com/netac-basic-8gb-ddr4",
        "source": "Ryans", "scraped_at": "2026-05-26T12:00:00+00:00",
    },
    # Should NOT merge with StarTech's "Vulcan Z" — different model series
    # (same match_key: team_8gb_ddr4_3200mhz, but this is Delta RGB)
    {
        "name": "Team T-Force Delta RGB 8GB DDR4 3200MHz Desktop RAM",
        "brand": "Team", "capacity": "8GB", "generation": "DDR4",
        "speed": "3200MHz", "latency": None, "form_factor": "Desktop",
        "match_key": "team_8gb_ddr4_3200mhz",
        "price_bdt": 7800.0, "in_stock": True,
        "product_url": "https://www.ryans.com/team-delta-rgb-8gb-ddr4",
        "source": "Ryans", "scraped_at": "2026-05-26T12:00:00+00:00",
    },
]


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _price(bdt) -> str:
    return f"৳{bdt:,.0f}" if bdt else "N/A"


def print_results(products: list[CanonicalProduct], all_records: list[dict]) -> None:
    sources = sorted({r["source"] for r in all_records})
    multi = [p for p in products if p.retailer_count > 1]
    single = [p for p in products if p.retailer_count == 1]

    print(f"\n{'='*68}")
    print(f"  Matching results — {', '.join(sources)}")
    print(f"{'='*68}")
    source_counts = ", ".join(
        f"{sum(1 for r in all_records if r['source'] == s)} {s}" for s in sources
    )
    print(f"  Input records     : {len(all_records)}  ({source_counts})")
    print(f"  Canonical products: {len(products)}")
    print(f"  Cross-retailer matches: {len(multi)}  ← same product found in 2+ stores")
    print(f"  Single-retailer only:   {len(single)}")

    if multi:
        print(f"\n{'─'*68}")
        print(f"  CROSS-RETAILER MATCHES  (price comparison opportunities)")
        print(f"{'─'*68}")
        for p in sorted(multi, key=lambda x: x.match_key):
            c = p.cheapest_listing
            print(f"\n  {p.canonical_name}")
            print(f"  key: {p.match_key}  |  series: \"{p.model_series}\"")
            for l in p.listings:
                marker = " ← cheapest" if c and l["source"] == c["source"] and l["price_bdt"] == c["price_bdt"] else ""
                stock = "in stock" if l["in_stock"] else "out of stock"
                print(f"    {l['source']:<12} {_price(l['price_bdt']):<12} {stock}{marker}")

    # Show the team_8gb_ddr4_3200mhz bucket to illustrate non-merging
    team_bucket = [p for p in products if p.match_key == "team_8gb_ddr4_3200mhz"]
    if team_bucket:
        print(f"\n{'─'*68}")
        print(f"  SAME match_key, DIFFERENT products  (fuzzy correctly kept separate)")
        print(f"{'─'*68}")
        print(f"\n  match_key: team_8gb_ddr4_3200mhz  →  {len(team_bucket)} distinct products\n")
        for p in team_bucket:
            retailers = ", ".join(
                f"{l['source']} {_price(l['price_bdt'])}" for l in p.listings
            )
            print(f"  • \"{p.model_series or '(no series)'}\"  [{retailers}]")

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def find_all_cleaned_files(category: str) -> list[Path]:
    files = sorted(Path("data/processed").glob(f"*_{category}_clean.json"))
    if not files:
        raise FileNotFoundError(
            f"No *_{category}_clean.json files in data/processed/. "
            f"Run cleaning/normalize.py --category {category} first."
        )
    return files


def main():
    parser = argparse.ArgumentParser(description="Cross-retailer product matcher")
    parser.add_argument("--input", type=Path, nargs="+", default=None,
                        help="One or more cleaned JSON files (default: all matching files in data/processed/)")
    parser.add_argument("--category",
                        choices=["ram", "laptop_ram", "gpu", "processor", "motherboard",
                                 "ssd", "portable_ssd", "hdd", "portable_hdd",
                                 "psu", "cooler", "casing_cooler", "casing", "odd", "monitor"],
                        default="ram",
                        help="Product category — determines which clean files to load (default: ram)")
    parser.add_argument("--threshold", type=int, default=SIMILARITY_THRESHOLD,
                        help=f"Fuzzy match threshold 0-100 (default: {SIMILARITY_THRESHOLD})")
    args = parser.parse_args()

    input_paths = args.input or find_all_cleaned_files(args.category)
    all_records: list[dict] = []
    for path in input_paths:
        print(f"Loading: {path}")
        with open(path, encoding="utf-8") as f:
            all_records.extend(json.load(f))
    print(f"Total records loaded: {len(all_records)}")

    products = match_products(all_records, threshold=args.threshold)
    print_results(products, all_records)

    out_path = Path(f"data/processed/matched_{args.category}_products.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in products], f, ensure_ascii=False, indent=2)
    print(f"Saved {len(products)} canonical products -> {out_path}")


if __name__ == "__main__":
    main()
