"""
Re-key RAM products after extract_speed learned MT/s and the DDRx-NNNN grade.

Why this has to run
-------------------
`match_key` is product identity, and `products` is UNIQUE (match_key, name).
When normalize.py starts producing a different key for the same stick, the
loader no longer recognises the existing row: it inserts a *new* product and the
old one keeps its price history. One product becomes two, each with half a
chart, and nothing errors. This script moves the existing rows onto the new keys
so the code change lands without splitting anything.

Run it once, on every database the pipeline writes to, before the next RAM
scrape. Local and Neon are separate — do both.

Scope and safety
----------------
  * Only RAM DESKTOP / RAM LAPTOP rows are considered.
  * A row is touched only when recomputing its key with the *old* speed logic
    reproduces exactly what is stored. That proves the difference is the speed
    change and not some other drift, so pre-existing oddities (stale `g-skill`
    keys, bundle names where a 2TB SSD is read as the RAM's capacity) are left
    alone rather than silently rewritten to something else wrong.
  * Aborts if any update would collide with UNIQUE (match_key, name).
  * Touches `products.match_key` only. No price row is read, written or
    deleted — prices stay append-only.

Usage:
  python scripts/backfill_ram_speed_keys.py            # dry run, prints the plan
  python scripts/backfill_ram_speed_keys.py --apply
  python scripts/backfill_ram_speed_keys.py --apply --neon
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from dotenv import load_dotenv, dotenv_values

from cleaning import normalize as n

RAM_CATEGORIES = ("RAM DESKTOP", "RAM LAPTOP")

# extract_speed exactly as it behaved before the change, so we can prove a
# difference is attributable to it and nothing else.
_OLD_SPEED = re.compile(r"\b(\d{3,5})\s*[Mm]?[Hh][Zz]\b")


def _old_speed(name: str) -> str | None:
    m = _OLD_SPEED.search(name)
    return f"{m.group(1)}MHz" if m else None


def _keys(name: str) -> tuple[str, str]:
    """(key under the old speed logic, key under the new one)."""
    norm = n.normalize_name(name)
    brand = n.extract_brand(norm)
    cap = n.extract_capacity(norm)
    gen = n.extract_generation(norm)
    return (
        n.build_match_key(brand, cap, gen, _old_speed(norm)),
        n.build_match_key(brand, cap, gen, n.extract_speed(norm)),
    )


def connect(use_neon: bool):
    if use_neon:
        url = dotenv_values(".env.neon").get("NEON_URL")
        if not url:
            sys.exit("NEON_URL not found in .env.neon")
        return psycopg2.connect(url), "Neon (production)"
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg2.connect(url), "DATABASE_URL"
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ), f"local {os.getenv('DB_HOST', '127.0.0.1')}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-key RAM products for the MT/s speed fix")
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--neon", action="store_true", help="target .env.neon instead of local")
    args = ap.parse_args()

    conn, label = connect(args.neon)
    conn.autocommit = False
    cur = conn.cursor()
    print(f"Database: {label}")

    cur.execute(
        "SELECT id, name, match_key FROM products WHERE category = ANY(%s)",
        (list(RAM_CATEGORIES),),
    )
    rows = cur.fetchall()
    cur.execute("SELECT match_key, name FROM products")
    taken = {(k, nm) for k, nm in cur.fetchall()}

    planned, skipped_drift, already = [], [], 0
    for pid, name, stored in rows:
        old_key, new_key = _keys(name)
        if old_key == new_key:
            continue                      # speed change does not affect this row
        if new_key == stored:
            already += 1                  # migrated by an earlier run
            continue
        if old_key != stored:
            # Recomputation does not reproduce the stored key, so something
            # other than the speed change differs. Not ours to rewrite.
            skipped_drift.append((pid, name, stored, old_key, new_key))
            continue
        planned.append((pid, name, stored, new_key))

    collisions = [p for p in planned if (p[3], p[1]) in taken]

    print(f"  RAM products               : {len(rows):,}")
    print(f"  to re-key                  : {len(planned):,}")
    print(f"  already migrated           : {already:,}")
    print(f"  skipped (unrelated drift)  : {len(skipped_drift):,}")
    print(f"  collisions                 : {len(collisions):,}")

    if skipped_drift:
        print("\n  skipped rows (left exactly as they are):")
        for pid, name, stored, ok, nk in skipped_drift[:8]:
            print(f"    #{pid} stored={stored} recomputed={ok}  {name[:44]}")

    if collisions:
        print("\nABORT: these updates would violate UNIQUE (match_key, name):")
        for pid, name, stored, nk in collisions[:10]:
            print(f"  #{pid} -> {nk}  {name[:56]}")
        sys.exit(1)

    print("\n  sample:")
    for pid, name, stored, nk in planned[:8]:
        print(f"    {stored:<28} -> {nk:<34} {name[:38]}")

    if not args.apply:
        print(f"\nDry run. Pass --apply to update {len(planned):,} rows.")
        return

    cur.executemany(
        "UPDATE products SET match_key = %s WHERE id = %s",
        [(nk, pid) for pid, _, _, nk in planned],
    )
    conn.commit()
    print(f"\nUPDATED {cur.rowcount if cur.rowcount != -1 else len(planned):,} product rows.")
    print("Prices untouched. Re-run database/refresh_mv.py if you want the view rebuilt.")
    conn.close()


if __name__ == "__main__":
    main()
