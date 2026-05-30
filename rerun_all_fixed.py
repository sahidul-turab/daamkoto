"""
Re-run scrapers + full pipeline for all retailers that had OOS detection fixes.
Runs sequentially, category by category, retailer by retailer.

Estimated time: 1.5–3 hours depending on catalog sizes.
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PYTHON = sys.executable


def run(cmd, label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    t = time.time()
    result = subprocess.run([PYTHON] + cmd, capture_output=False)
    elapsed = time.time() - t
    print(f"  Done in {elapsed:.0f}s  (exit code {result.returncode})")
    return result.returncode == 0


# ─── Which retailers to re-scrape ────────────────────────────────────────────
# These all had the OpenCart button-only OOS detection bug.
# Techland / TrustTech / ComputerSource / PotakaIT / UCC also improved —
# include them too so their stock_status field is populated from fresh data.
RETAILERS_TO_SCRAPE = [
    "creatus",      # confirmed OOS issue (extreme discount prices)
    "skyland",      # same pattern
    "ultratech",    # same pattern
    "binarylogic",  # buy_btn only (same issue)
    "selltech",     # cart_btn only
    "pchouse",      # buy-btn only
    "techland",     # text-based but now has stock_status + upcoming
    "trusttech",    # was correct; now outputs stock_status
    "computersource", # was correct; now outputs stock_status
    "potakait",     # good detection; now outputs stock_status
    "ucc",          # text-based; now outputs stock_status
]

# All categories in the system
CATEGORIES = [
    "ram",
    "laptop_ram",
    "gpu",
    "processor",
    "motherboard",
    "ssd",
    "portable_ssd",
    "hdd",
    "portable_hdd",
    "psu",
    "cooler",
    "casing_cooler",
    "casing",
]

DB_CATEGORY = {
    "ram":           "RAM DESKTOP",
    "laptop_ram":    "RAM LAPTOP",
    "gpu":           "GPU",
    "processor":     "PROCESSOR",
    "motherboard":   "MOTHERBOARD",
    "ssd":           "SSD",
    "portable_ssd":  "PORTABLE SSD",
    "hdd":           "HDD",
    "portable_hdd":  "PORTABLE HDD",
    "psu":           "PSU",
    "cooler":        "CPU COOLER",
    "casing_cooler": "CASING COOLER",
    "casing":        "CASING",
}


def latest_raw(retailer, cat):
    files = sorted(
        Path("data/raw").glob(f"{retailer}_{cat}_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return files[-1] if files else None


total_start = time.time()
failed = []

for cat in CATEGORIES:
    print(f"\n\n{'#'*60}")
    print(f"  CATEGORY: {cat.upper()}")
    print(f"{'#'*60}")

    # Step 1: Scrape each retailer for this category
    for retailer in RETAILERS_TO_SCRAPE:
        scraper = Path(f"scrapers/{retailer}/scrape_{cat}.py")
        if not scraper.exists():
            print(f"  [skip] No scraper: {scraper}")
            continue

        ok = run(
            [str(scraper), "--save"],
            f"Scrape {retailer.title()} {cat.upper()}",
        )
        if not ok:
            failed.append(f"{retailer} {cat} scrape")

    # Step 2: Normalize each new raw file
    for retailer in RETAILERS_TO_SCRAPE:
        raw = latest_raw(retailer, cat)
        if not raw:
            continue
        ok = run(
            ["cleaning/normalize.py", "--input", str(raw), "--category", cat],
            f"Normalize {retailer.title()} {cat.upper()}",
        )
        if not ok:
            failed.append(f"{retailer} {cat} normalize")

    # Step 3: Match across all retailers for this category
    ok = run(
        ["cleaning/matcher.py", "--category", cat],
        f"Match {cat.upper()} across all retailers",
    )
    if not ok:
        failed.append(f"{cat} match")
        continue

    # Step 4: Load into PostgreSQL
    matched = f"data/processed/matched_{cat}_products.json"
    ok = run(
        ["database/load.py", "--category", DB_CATEGORY[cat], "--input", matched],
        f"Load {DB_CATEGORY[cat]} into PostgreSQL",
    )
    if not ok:
        failed.append(f"{cat} load")

# Step 5: Refresh materialized view once at the end
run(["database/refresh_mv.py"], "Refresh mv_current_prices")

elapsed = time.time() - total_start
print(f"\n\n{'='*60}")
print(f"  ALL DONE — total time: {elapsed/60:.1f} min")
if failed:
    print(f"  FAILED steps ({len(failed)}):")
    for f in failed:
        print(f"    - {f}")
else:
    print("  No failures.")
print(f"{'='*60}")
