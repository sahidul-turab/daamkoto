"""
Stage 3 loader: reads matched_products.json and writes to PostgreSQL.

What this script does:
  1. Connects to PostgreSQL using credentials from .env
  2. Ensures the three known retailers exist in the retailers table
  3. For each canonical product in matched_products.json:
     - Inserts a products row if the match_key is new; skips if it already exists
     - For each listing that has a price, inserts a prices row (append-only)
  4. Prints a load summary

Why is this idempotent?
  Products: ON CONFLICT (match_key) DO NOTHING — re-running never creates duplicates.
  Prices:   ON CONFLICT (product_id, retailer_id, scraped_at) DO NOTHING — loading the
            same file twice is a no-op. The timestamp is what distinguishes scrape runs:
            a fresh scrape has a newer scraped_at, so it always inserts new price rows.

Usage:
  python database/load.py
  python database/load.py --input data/processed/matched_products.json
  python database/load.py --dry-run    # shows what would be inserted, no DB writes
  python database/load.py --category GPU  # override category tag (default: RAM)
"""

import argparse
import io
import json
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()

# -------------------------------------------------------------------------
# Known retailers — seeded on first load
# -------------------------------------------------------------------------

KNOWN_RETAILERS = {
    "StarTech":       "https://www.startech.com.bd",
    "Ryans":          "https://www.ryans.com",
    "Techland":       "https://www.techlandbd.com",
    "PotakaIT":       "https://www.potakait.com",
    "UCC":            "https://www.ucc.com.bd",
    "UltraTech":      "https://www.ultratech.com.bd",
    "BinaryLogic":    "https://www.binarylogic.com.bd",
    "Skyland":        "https://www.skyland.com.bd",
    "Creatus":        "https://www.creatus.com.bd",
    "SellTech":       "https://www.selltech.com.bd",
    "ComputerSource": "https://computersource.com.bd",
    "TrustTech":      "https://www.trusttechbd.com",
    "PCHouse":        "https://www.pchouse.com.bd",
}


# -------------------------------------------------------------------------
# Database connection
# -------------------------------------------------------------------------

def get_connection():
    """
    Connect using environment variables from .env.
    Copy .env.example → .env and fill in your credentials.
    """
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# -------------------------------------------------------------------------
# Retailer setup
# -------------------------------------------------------------------------

def ensure_retailers(cur) -> dict[str, int]:
    """
    Insert each known retailer if it doesn't exist yet.
    Returns a {name: id} dict used for price inserts.
    """
    id_map: dict[str, int] = {}
    for name, base_url in KNOWN_RETAILERS.items():
        cur.execute(
            """
            INSERT INTO retailers (name, base_url)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            (name, base_url),
        )
        cur.execute("SELECT id FROM retailers WHERE name = %s", (name,))
        id_map[name] = cur.fetchone()[0]
    return id_map


# -------------------------------------------------------------------------
# Product upsert
# -------------------------------------------------------------------------

def upsert_product(cur, product: dict, category: str) -> tuple[int, bool]:
    """
    Insert a product row keyed on match_key. Returns (product_id, was_inserted).

    ON CONFLICT (match_key) DO NOTHING means:
      - First run: inserts the row, RETURNING gives us the new id.
      - Re-run: the insert is silently skipped; we SELECT to find the existing id.

    model_number stores the best MPN found across all listings (may be None).
    specs stores the structured fields as JSONB for flexible querying.
    """
    # Pick the first MPN we find across all listings
    mpn = next(
        (lst["mpn"] for lst in product.get("listings", []) if lst.get("mpn")),
        None,
    )
    # Prefer the rich category-specific specs dict from normalize.py.
    # Fall back to flat fields for any data loaded before the specs dict was added.
    specs = product.get("specs") or {
        "capacity":     product.get("capacity"),
        "generation":   product.get("generation"),
        "speed":        product.get("speed"),
        "model_series": product.get("model_series"),
        "form_factor":  product.get("form_factor"),
    }

    cur.execute(
        """
        INSERT INTO products (name, brand, match_key, model_number, category, specs)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_key, name) DO UPDATE SET specs = EXCLUDED.specs
        RETURNING id, (xmax = 0) AS inserted
        """,
        (
            product["canonical_name"],
            product.get("brand"),
            product["match_key"],
            mpn,
            category,
            json.dumps(specs),
        ),
    )
    row = cur.fetchone()
    return row[0], bool(row[1])


# -------------------------------------------------------------------------
# Price insert
# -------------------------------------------------------------------------

def insert_price(cur, product_id: int, retailer_id: int, listing: dict) -> bool:
    """
    Insert a price row. Returns True if a new row was inserted.

    Skips listings with no price (out-of-stock items with no listed price).
    The UNIQUE constraint on (product_id, retailer_id, scraped_at) makes
    this a no-op if the same listing is loaded twice.
    """
    if listing.get("price_bdt") is None:
        return False

    in_stock = listing.get("in_stock", True)
    stock_status = listing.get("stock_status") or ("in_stock" if in_stock else "out_of_stock")
    pc_bundle_only = bool(listing.get("pc_bundle_only", False))

    cur.execute(
        """
        INSERT INTO prices (product_id, retailer_id, price_bdt, in_stock, stock_status, pc_bundle_only, product_url, scraped_at, seller_specs)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (product_id, retailer_id, scraped_at)
        DO UPDATE SET pc_bundle_only = EXCLUDED.pc_bundle_only
        """,
        (
            product_id,
            retailer_id,
            listing["price_bdt"],
            in_stock,
            stock_status,
            pc_bundle_only,
            listing.get("product_url"),
            listing.get("scraped_at"),
            json.dumps(listing.get("seller_raw_specs") or {}),
        ),
    )
    return cur.rowcount > 0


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def dry_run_report(products: list[dict]) -> None:
    priced = sum(1 for p in products for l in p["listings"] if l.get("price_bdt"))
    sources = sorted({l["source"] for p in products for l in p["listings"]})
    print(f"[dry-run] {len(products)} products would be upserted")
    print(f"[dry-run] {priced} price rows would be inserted")
    print(f"[dry-run] Sources: {', '.join(sources)}")


def load(input_path: Path, category: str, dry_run: bool) -> None:
    print(f"Input : {input_path}")

    with open(input_path, encoding="utf-8") as f:
        products = json.load(f)

    print(f"Records: {len(products)} canonical products")

    if dry_run:
        dry_run_report(products)
        return

    conn = get_connection()
    try:
        with conn:  # auto-commit on success, rollback on exception
            with conn.cursor() as cur:
                retailer_ids = ensure_retailers(cur)

                products_inserted = 0
                products_existing = 0
                prices_inserted   = 0
                prices_skipped    = 0

                for product in products:
                    product_id, was_new = upsert_product(cur, product, category)
                    if was_new:
                        products_inserted += 1
                    else:
                        products_existing += 1

                    for listing in product.get("listings", []):
                        source = listing.get("source", "")
                        retailer_id = retailer_ids.get(source)
                        if retailer_id is None:
                            # Unknown retailer — add to KNOWN_RETAILERS and re-run, or
                            # the loader will skip this listing with a warning.
                            print(f"  WARNING: unknown retailer '{source}' — skipping listing")
                            continue

                        inserted = insert_price(cur, product_id, retailer_id, listing)
                        if inserted:
                            prices_inserted += 1
                        else:
                            prices_skipped += 1

        print(f"\n{'='*55}")
        print(f"  Load complete")
        print(f"{'='*55}")
        print(f"  Products  inserted : {products_inserted}")
        print(f"  Products  existing : {products_existing}  (skipped, already in DB)")
        print(f"  Prices    inserted : {prices_inserted}")
        print(f"  Prices    skipped  : {prices_skipped}  (duplicate scraped_at)")
        print(f"{'='*55}")

    finally:
        conn.close()


def find_latest_matched_file(category: str = "ram") -> Path:
    p = Path(f"data/processed/matched_{category}_products.json")
    if not p.exists():
        raise FileNotFoundError(
            f"data/processed/matched_{category}_products.json not found. "
            f"Run cleaning/matcher.py --category {category} first."
        )
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Load matched products into PostgreSQL")
    parser.add_argument("--input", type=Path, default=None,
                        help="Path to matched_*_products.json (default: auto from --category)")
    parser.add_argument("--category", default="RAM",
                        help="Category tag: RAM, GPU, CPU, SSD, etc. (default: RAM)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be inserted without touching the DB")
    args = parser.parse_args()

    input_path = args.input or find_latest_matched_file(args.category.lower())
    load(input_path, category=args.category, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
