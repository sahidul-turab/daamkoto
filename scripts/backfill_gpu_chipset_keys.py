"""
Re-key GPU products after extract_chipset learned to read through ™/® and soft
hyphens, and to spell each chipset one way ("RX550" -> "RX 550").

Why this has to run
-------------------
The chipset is part of the GPU match_key, and `products` is UNIQUE (match_key,
name). Once normalize.py produces a different key for the same card, the loader
stops recognising the existing row: it inserts a *new* product and the old one
keeps its price history. One product becomes two, each with half a chart, and
nothing errors. This script moves the existing rows onto the new keys so the
code change lands without splitting anything (same approach as
backfill_ram_speed_keys.py).

Run it once, on every database the pipeline writes to, before the next GPU
scrape. Local and Neon are separate — do both.

Scope and safety
----------------
  * Only GPU rows are considered.
  * A row is re-keyed only when recomputing its key with the *old* chipset
    logic reproduces exactly what is stored, which proves the difference is
    this change and not some other drift.
  * Aborts if any update would collide with UNIQUE (match_key, name).
  * specs.chipset / specs.chipset_brand are refreshed for every GPU row whose
    chipset reading changed, so the chipset filter is right immediately rather
    than after the next scrape re-saves specs.
  * Touches `products` only. No price row is read, written or deleted.

Usage:
  python scripts/backfill_gpu_chipset_keys.py            # dry run, prints the plan
  python scripts/backfill_gpu_chipset_keys.py --apply
  python scripts/backfill_gpu_chipset_keys.py --apply --neon
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cleaning import normalize as n  # noqa: E402
from scripts.backfill_ram_speed_keys import connect  # noqa: E402


def _old_extract_chipset(name: str) -> str | None:
    """extract_chipset exactly as it behaved before the change."""
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


def _keys(name: str) -> tuple[str, str, str | None]:
    """(key under the old chipset logic, key under the new one, new chipset)."""
    norm = n.normalize_name(name)
    brand = n.extract_gpu_brand(norm)
    vram = n.extract_vram(norm)
    variant = n.extract_gpu_variant(norm, brand)
    new_chip = n.extract_chipset(norm)
    return (
        n.build_gpu_match_key(brand, _old_extract_chipset(norm), vram, variant),
        n.build_gpu_match_key(brand, new_chip, vram, variant),
        new_chip,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-key GPU products for the chipset fix")
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--neon", action="store_true", help="target .env.neon instead of local")
    args = ap.parse_args()

    conn, label = connect(args.neon)
    conn.autocommit = False
    cur = conn.cursor()
    print(f"Database: {label}")

    cur.execute("SELECT id, name, match_key, specs FROM products WHERE category = 'GPU'")
    rows = cur.fetchall()
    cur.execute("SELECT match_key, name FROM products")
    taken = {(k, nm) for k, nm in cur.fetchall()}

    rekey, spec_only, skipped_drift, already = [], [], [], 0
    for pid, name, stored, specs in rows:
        old_key, new_key, chip = _keys(name)
        specs = specs or {}
        spec_changed = specs.get("chipset") != chip
        if old_key != new_key:
            if new_key == stored:
                already += 1
            elif old_key != stored:
                skipped_drift.append((pid, name, stored, old_key, new_key))
                continue
            else:
                rekey.append((pid, name, stored, new_key))
        if spec_changed:
            spec_only.append((pid, chip))

    planned_pairs = [(nk, nm) for _, nm, _, nk in rekey]
    collisions = [p for p in rekey if (p[3], p[1]) in taken]
    dup_within = len(planned_pairs) - len(set(planned_pairs))

    print(f"  GPU products               : {len(rows):,}")
    print(f"  to re-key                  : {len(rekey):,}")
    print(f"  chipset spec to refresh    : {len(spec_only):,}")
    print(f"  already migrated           : {already:,}")
    print(f"  skipped (unrelated drift)  : {len(skipped_drift):,}")
    print(f"  collisions                 : {len(collisions) + dup_within:,}")

    if skipped_drift:
        print("\n  skipped rows (left exactly as they are):")
        for pid, name, stored, ok, nk in skipped_drift[:8]:
            print(f"    #{pid} stored={stored} recomputed={ok}  {name[:44]}")

    if collisions or dup_within:
        print("\nABORT: these updates would violate UNIQUE (match_key, name):")
        for pid, name, stored, nk in collisions[:10]:
            print(f"  #{pid} -> {nk}  {name[:56]}")
        sys.exit(1)

    print("\n  sample:")
    for pid, name, stored, nk in rekey[:10]:
        print(f"    {stored[:40]:<40} -> {nk[:46]:<46} {name[:30]}")

    if not args.apply:
        print(f"\nDry run. Pass --apply to re-key {len(rekey):,} rows "
              f"and refresh {len(spec_only):,} chipset specs.")
        return

    cur.executemany(
        "UPDATE products SET match_key = %s WHERE id = %s",
        [(nk, pid) for pid, _, _, nk in rekey],
    )
    cur.executemany(
        """
        UPDATE products
        SET specs = COALESCE(specs, '{}'::jsonb)
                    || jsonb_build_object('chipset', %s::text, 'chipset_brand', %s::text)
        WHERE id = %s
        """,
        [(chip, n.extract_chipset_brand(chip), pid) for pid, chip in spec_only],
    )
    conn.commit()
    print(f"\nRe-keyed {len(rekey):,} and refreshed {len(spec_only):,} GPU product rows.")
    print("Prices untouched. Run database/refresh_mv.py so the view picks up the specs.")
    conn.close()


if __name__ == "__main__":
    main()
