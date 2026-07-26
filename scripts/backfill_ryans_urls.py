"""
Backfill missing Ryans product URLs into a database (local or Neon).

Why this exists
---------------
Ryans dropped `product_slug` from their card `data-item` JSON, so for a while
every Ryans listing was loaded with product_url = NULL and clicking a Ryans
price in the UI went nowhere. The scrapers are fixed (they now read the real
link from the card image anchor), but existing rows stay NULL until refreshed.

What it does (safely)
---------------------
For each category it scrapes Ryans, normalises, then performs a pure in-place
UPDATE keyed on `match_key`:

    UPDATE prices SET product_url = <url>
    WHERE product's match_key = <mk> AND retailer = Ryans AND product_url IS NULL

This is deliberately an UPDATE, not a scrape->match->load: it can NEVER create
duplicate products, never touches other retailers, and never changes a price.
It only fills the missing URL metadata. A match_key that maps to more than one
distinct URL (variant collision) is skipped rather than guessed.

Target DB
---------
Prefers NEON_URL / DATABASE_URL (Neon, carries sslmode); else falls back to the
discrete DB_* vars from .env (local). Pass --neon to force Neon from .env.neon.

Cloudflare
----------
Ryans is behind Cloudflare and rate-limits aggressive clients. --wait-for-cf
polls politely until the site is reachable before starting, so this can be
launched and left to run itself once a rate-limit lifts.

Usage
-----
    python scripts/backfill_ryans_urls.py --neon --wait-for-cf
    python scripts/backfill_ryans_urls.py --categories gpu processor --neon
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

from dotenv import dotenv_values  # noqa: E402
import psycopg2  # noqa: E402

PY_EXE = sys.executable
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# category slug -> DB category name (mirrors run_pipeline.py)
DB_NAME = {
    "ram": "RAM DESKTOP", "laptop_ram": "RAM LAPTOP", "gpu": "GPU",
    "processor": "PROCESSOR", "motherboard": "MOTHERBOARD", "ssd": "SSD",
    "portable_ssd": "PORTABLE SSD", "hdd": "HDD", "portable_hdd": "PORTABLE HDD",
    "psu": "PSU", "cooler": "CPU COOLER", "casing_cooler": "CASING COOLER",
    "casing": "CASING", "monitor": "MONITOR", "keyboard": "KEYBOARD",
    "mouse": "MOUSE", "headset": "HEADSET", "ups": "UPS", "speaker": "SPEAKER",
    "webcam": "WEBCAM", "gaming_chair": "GAMING CHAIR", "printer": "PRINTER",
    "mousepad": "MOUSE PAD",
}
_PROBE_URL = "https://www.ryans.com/category/desktop-component-graphics-card"


def log(msg: str) -> None:
    print(msg, flush=True)


def dsn(force_neon: bool) -> str | None:
    if force_neon:
        return dotenv_values(str(ROOT / ".env.neon")).get("NEON_URL")
    return (os.getenv("NEON_URL") or os.getenv("DATABASE_URL")
            or dotenv_values(str(ROOT / ".env.neon")).get("NEON_URL"))


def sh(cmd: list[str], timeout: int = 2400) -> subprocess.CompletedProcess:
    return subprocess.run([PY_EXE] + cmd, env=CHILD_ENV, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def cf_clear() -> bool:
    """True when Ryans serves real product cards (not a Cloudflare challenge)."""
    try:
        r = subprocess.run(["curl", "-s", "-A", _UA, _PROBE_URL],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return r.stdout.count("category-single-product") > 0
    except Exception:
        return False


def wait_for_cf(max_minutes: int, interval_s: int = 1200) -> bool:
    deadline = time.time() + max_minutes * 60
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        if cf_clear():
            log(f"  Cloudflare clear (attempt {attempt}).")
            return True
        log(f"  Cloudflare blocking (attempt {attempt}); waiting {interval_s // 60} min…")
        time.sleep(interval_s)
    return cf_clear()


def build_url_map(clean_path: str) -> tuple[dict[str, str], int]:
    """match_key -> url, keeping only keys that map to exactly one distinct URL."""
    records = json.load(open(clean_path, encoding="utf-8"))
    by_key: dict[str, set[str]] = {}
    for rec in records:
        mk = rec.get("match_key")
        url = rec.get("product_url")
        if mk and url:
            by_key.setdefault(mk, set()).add(url)
    unambiguous = {mk: next(iter(urls)) for mk, urls in by_key.items() if len(urls) == 1}
    ambiguous = sum(1 for urls in by_key.values() if len(urls) > 1)
    return unambiguous, ambiguous


def backfill_category(cat: str, conn, ryans_id: int) -> str:
    scraper = f"scrapers/ryans/scrape_{cat}.py"
    if not os.path.exists(scraper):
        return "no scraper"
    sh([scraper, "--save"])
    raws = sorted(glob.glob(f"data/raw/ryans_{cat}_*.json"))
    if not raws:
        return "no raw file"
    raw = raws[-1]
    try:
        n_raw = len(json.load(open(raw, encoding="utf-8")))
    except Exception:
        n_raw = 0
    if n_raw == 0:
        return "0 scraped (Cloudflare?)"

    sh(["cleaning/normalize.py", "--input", raw, "--category", cat])
    clean = f"data/processed/ryans_{cat}_clean.json"
    if not os.path.exists(clean):
        return f"scraped {n_raw}, normalize produced no clean file"

    url_map, ambiguous = build_url_map(clean)
    if not url_map:
        return f"scraped {n_raw}, no usable match_key->url pairs"

    updated = 0
    with conn.cursor() as cur:
        for mk, url in url_map.items():
            cur.execute(
                """
                UPDATE prices p
                SET product_url = %s
                FROM products pr
                WHERE p.product_id = pr.id
                  AND pr.match_key = %s
                  AND p.retailer_id = %s
                  AND (p.product_url IS NULL OR p.product_url = '')
                """,
                (url, mk, ryans_id),
            )
            updated += cur.rowcount
    conn.commit()
    return f"scraped {n_raw}, keys={len(url_map)} (ambiguous {ambiguous}), rows_filled={updated}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill Ryans product URLs")
    ap.add_argument("--categories", nargs="+", default=list(DB_NAME),
                    choices=list(DB_NAME))
    ap.add_argument("--neon", action="store_true", help="Force Neon from .env.neon")
    ap.add_argument("--wait-for-cf", action="store_true",
                    help="Poll politely until Cloudflare lets us through, then run")
    ap.add_argument("--max-wait-min", type=int, default=240)
    args = ap.parse_args()

    target = dsn(args.neon)
    if not target:
        log("No database URL found (NEON_URL / DATABASE_URL / .env.neon). Aborting.")
        sys.exit(1)
    host = target.split("@")[-1].split("/")[0][:40] if "@" in target else "local"
    log(f"Target DB: {host}")

    if args.wait_for_cf and not wait_for_cf(args.max_wait_min):
        log("Cloudflare still blocking after max wait — nothing scraped. Try again later.")
        sys.exit(2)

    conn = psycopg2.connect(target)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM retailers WHERE name = 'Ryans'")
        row = cur.fetchone()
        if not row:
            log("No 'Ryans' retailer row in this DB. Aborting.")
            sys.exit(1)
        ryans_id = row[0]
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE product_url IS NULL OR product_url=''), "
            "COUNT(*) FROM mv_current_prices WHERE retailer='Ryans'"
        )
        n0, t0 = cur.fetchone()
    log(f"BEFORE: Ryans current listings null_url={n0}/{t0}\n")

    for cat in args.categories:
        log(f"[{cat}] …")
        try:
            result = backfill_category(cat, conn, ryans_id)
        except Exception as exc:  # never let one category kill the run
            conn.rollback()
            result = f"ERROR {exc!r}"
        log(f"[{cat}] {result}")

    log("\nRefreshing materialized view…")
    r = sh(["database/refresh_mv.py"], timeout=600)
    log(f"  refresh rc={r.returncode} {(r.stderr or '')[-200:]}")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE product_url IS NULL OR product_url=''), "
            "COUNT(*) FROM mv_current_prices WHERE retailer='Ryans'"
        )
        n1, t1 = cur.fetchone()
    conn.close()
    log(f"\nAFTER: Ryans current listings null_url={n1}/{t1}  (filled {n0 - n1})")


if __name__ == "__main__":
    main()
