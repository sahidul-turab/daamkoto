"""
Find product rows that duplicate an existing product because a load ran for a
single retailer.

Why these exist
---------------
`cleaning/matcher.py` elects a canonical name per group: the longest listing
name among the retailers *in that run*. `database/load.py` then upserts
`ON CONFLICT (match_key, name)`. So when a sweep covers every retailer the
canonical name is stable and a new retailer's listing joins the existing
product — but when a sweep covers only one retailer, that retailer's own name
becomes canonical, misses the conflict target, and inserts a second product row
beside the original.

That is what a `--retailers <one>` dispatch of daily-scrape.yml did on
2026-08-03 for EZGadgets. The fix for the future is to never load a single
retailer against a populated database; this script cleans up what already
landed.

What counts as a duplicate
--------------------------
A candidate must:
  1. be sold *only* by the suspect retailer (no other retailer's price rows), and
  2. share `match_key` + `category` with another product, and
  3. have a name that normalises (lowercase, alphanumeric only) to *exactly*
     the same string as that other product.

Rule 3 is deliberately strict. `match_key` is not unique by design — see the
comment in database/schema.sql — so "Team Vulcan Z" and "Team Delta RGB" can
legitimately share one. Fuzzy name matching also over-reports here: token-set
similarity scores "AJAZZ AJ159 NL" against "AJAZZ AJ159 NL P" at 100, and those
are different SKUs. Only an exact normalised match is safe to merge unattended.

Usage:
  python scripts/audit_orphan_duplicates.py --retailer EZGadgets            # report
  python scripts/audit_orphan_duplicates.py --retailer EZGadgets --apply    # merge
  python scripts/audit_orphan_duplicates.py --retailer EZGadgets --env .env.neon

Reporting is the default and touches nothing. `--apply` repoints the orphan's
price rows at the surviving product and deletes the orphan row; prices are
preserved, never deleted, so price history stays intact.
"""

import argparse
import os
import re
import sys

import psycopg2
from dotenv import load_dotenv

CANDIDATES_SQL = """
WITH suspect AS (
    SELECT DISTINCT pr.id, pr.match_key, pr.category, pr.name
    FROM products pr
    JOIN prices p    ON p.product_id = pr.id
    JOIN retailers r ON r.id = p.retailer_id
    WHERE r.name = %(retailer)s
),
orphan AS (
    SELECT s.* FROM suspect s
    WHERE NOT EXISTS (
        SELECT 1
        FROM prices p2
        JOIN retailers r2 ON r2.id = p2.retailer_id
        WHERE p2.product_id = s.id AND r2.name <> %(retailer)s
    )
)
SELECT o.id, o.category, o.name, k.id, k.name
FROM orphan o
JOIN products k
  ON  k.match_key = o.match_key
 AND  k.category  = o.category
 AND  k.id       <> o.id
"""


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def connect(env_file: str):
    load_dotenv(env_file)
    dsn = os.getenv("DATABASE_URL") or os.getenv("NEON_URL")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retailer", required=True,
                    help="display name, e.g. EZGadgets")
    ap.add_argument("--env", default=".env", help="env file holding the DSN")
    ap.add_argument("--apply", action="store_true",
                    help="merge duplicates (default is report only)")
    args = ap.parse_args()

    conn = connect(args.env)
    if not args.apply:
        conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(CANDIDATES_SQL, {"retailer": args.retailer})
    rows = cur.fetchall()

    # keeper_id -> orphan rows, exact normalised-name matches only
    merges: list[tuple[int, str, str, int, str]] = []
    for orphan_id, category, orphan_name, keep_id, keep_name in rows:
        if norm(orphan_name) == norm(keep_name):
            merges.append((orphan_id, category, orphan_name, keep_id, keep_name))

    # One orphan can collide with several keepers; keep the lowest id (oldest).
    best: dict[int, tuple] = {}
    for m in merges:
        if m[0] not in best or m[3] < best[m[0]][3]:
            best[m[0]] = m

    print(f"Retailer          : {args.retailer}")
    print(f"Collision rows    : {len(rows)}")
    print(f"Exact duplicates  : {len(best)}\n")

    if not best:
        print("Nothing to merge.")
        return 0

    for orphan_id, category, orphan_name, keep_id, keep_name in sorted(
            best.values(), key=lambda m: (m[1], m[2])):
        print(f"  {category:<13} orphan {orphan_id} -> keep {keep_id}")
        print(f"      orphan: {orphan_name[:70]}")
        print(f"      keep  : {keep_name[:70]}")

    if not args.apply:
        print(f"\nReport only — nothing changed. Re-run with --apply to merge "
              f"{len(best)} product row(s).")
        return 0

    moved = deleted = 0
    for orphan_id, _cat, _on, keep_id, _kn in best.values():
        # Prices are append-only, so repoint rather than delete. The unique
        # (product_id, retailer_id, scraped_at) constraint can already be
        # satisfied on the keeper, so skip those rather than fail the batch.
        cur.execute(
            """
            UPDATE prices p SET product_id = %(keep)s
            WHERE p.product_id = %(orphan)s
              AND NOT EXISTS (
                  SELECT 1 FROM prices q
                  WHERE q.product_id  = %(keep)s
                    AND q.retailer_id = p.retailer_id
                    AND q.scraped_at  = p.scraped_at
              )
            """,
            {"keep": keep_id, "orphan": orphan_id},
        )
        moved += cur.rowcount
        cur.execute("DELETE FROM prices WHERE product_id = %s", (orphan_id,))
        cur.execute("DELETE FROM products WHERE id = %s", (orphan_id,))
        deleted += cur.rowcount

    conn.commit()
    print(f"\nMerged. Price rows repointed: {moved} · product rows removed: {deleted}")
    print("Now run: python database/refresh_mv.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
