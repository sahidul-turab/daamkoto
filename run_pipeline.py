"""
Full pipeline runner: scrape -> normalize -> match -> load.

Retailer steps:
  StarTech  : scrape -> enrich (RAM only) -> normalize
  All others: scrape -> normalize

Shared:
  match  -> data/processed/matched_{category}_products.json
  load   -> PostgreSQL

Usage:
  python run_pipeline.py                                     # all retailers, RAM
  python run_pipeline.py --category gpu                      # all retailers, GPU
  python run_pipeline.py --retailers startech ryans          # subset
  python run_pipeline.py --skip-scrape                       # normalize+match+load only
  python run_pipeline.py --skip-load                         # stop after match
  python run_pipeline.py --dry-run                           # no DB writes
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Retailers that have scrapers for each category
ALL_RETAILERS = [
    "startech",
    "ryans",
    "techland",
    "potakait",
    "ucc",
    "ultratech",
    "binarylogic",
    "skyland",
    "creatus",
    "selltech",
    "computersource",
    "trusttech",
    "pchouse",
]


def run(cmd: list[str], label: str) -> None:
    python = sys.executable
    full_cmd = [python] + cmd
    print(f"\n{'='*60}")
    print(f"  STEP: {label}")
    print(f"  CMD : {' '.join(full_cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(full_cmd)
    if result.returncode != 0:
        print(f"\nPipeline aborted: '{label}' exited with code {result.returncode}.")
        sys.exit(result.returncode)


def latest(pattern: str, required: bool = True) -> Path | None:
    files = sorted(Path("data/raw").glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        if required:
            raise FileNotFoundError(
                f"No file matching data/raw/{pattern}. "
                "Run the scraper first, or pass --skip-scrape."
            )
        return None
    return files[-1]


def scrape_and_normalize(retailer: str, cat: str, skip_scrape: bool, limit: int | None) -> Path | None:
    """
    Run scrape (optional) + normalize for one retailer.
    Returns the raw file path used, or None if skipped.
    """

    scraper_path = Path(f"scrapers/{retailer}/scrape_{cat}.py")

    if retailer == "startech":
        if not skip_scrape:
            if not scraper_path.exists():
                print(f"\n  [skip] No scraper for {retailer} {cat.upper()} — {scraper_path} not found.")
                return None
            run([f"scrapers/startech/scrape_{cat}.py", "--save"],
                f"Scrape StarTech {cat.upper()}")
            if cat == "ram":
                enrich_cmd = ["scrapers/startech/enrich.py", "--only-priced"]
                if limit:
                    enrich_cmd += ["--limit", str(limit)]
                run(enrich_cmd, "Enrich StarTech RAM (detail pages)")

        if cat == "ram":
            raw = latest("startech_ram_enriched_*.json")
        else:
            raw = latest(f"startech_{cat}_*.json")

    else:
        if not skip_scrape:
            if not scraper_path.exists():
                print(f"\n  [skip] No scraper for {retailer} {cat.upper()} — {scraper_path} not found.")
                return None
            run([f"scrapers/{retailer}/scrape_{cat}.py", "--save"],
                f"Scrape {retailer.title()} {cat.upper()}")
            raw = latest(f"{retailer}_{cat}_*.json")
        else:
            raw = latest(f"{retailer}_{cat}_*.json", required=False)

    if raw is None:
        print(f"\n  [skip] No {retailer} {cat.upper()} raw file — run scraper first.")
        return None

    run(
        ["cleaning/normalize.py", "--input", str(raw), "--category", cat],
        f"Normalize {retailer.title()} {cat.upper()}  ({raw.name})",
    )
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full scrape->load pipeline")
    parser.add_argument(
        "--retailers", nargs="+", default=ALL_RETAILERS,
        choices=ALL_RETAILERS,
        help="Which retailers to include (default: all)",
    )
    parser.add_argument(
        "--category",
        choices=["ram", "laptop_ram", "gpu", "processor", "motherboard",
                 "ssd", "portable_ssd", "hdd", "portable_hdd",
                 "psu", "cooler", "casing_cooler", "casing", "odd", "monitor"],
        default="ram",
        help="Product category (default: ram)",
    )
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip scraping; use existing raw files")
    parser.add_argument("--skip-load", action="store_true",
                        help="Stop after match, do not write to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run everything but pass --dry-run to the loader")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit StarTech enricher to N products (testing only)")
    args = parser.parse_args()

    cat = args.category

    for retailer in args.retailers:
        scrape_and_normalize(retailer, cat, args.skip_scrape, args.limit)

    # Shared: match across all normalized files
    run(
        ["cleaning/matcher.py", "--category", cat],
        f"Match {cat.upper()} products across retailers",
    )

    if not args.skip_load:
        db_category = {
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
            "odd":           "ODD",
            "monitor":       "MONITOR",
        }.get(cat, cat.upper())
        matched_file = f"data/processed/matched_{cat}_products.json"
        load_cmd = ["database/load.py", "--category", db_category, "--input", matched_file]
        if args.dry_run:
            load_cmd.append("--dry-run")
        run(load_cmd, f"Load {db_category} into PostgreSQL")

        if not args.dry_run:
            # Refresh the materialized view so the API sees the new prices immediately
            run(
                ["database/refresh_mv.py"],
                "Refresh mv_current_prices (pre-computed price lookup)",
            )

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
