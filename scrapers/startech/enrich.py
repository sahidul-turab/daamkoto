"""
StarTech product detail enricher.

The listing scraper gives us: name, price, URL.
This script visits each product's detail page and adds:
  - mpn          (Model Part Number — universal identifier, e.g. "MMV8GD316C11U")
  - specs        (full key-value spec table as a dict)

Why a separate script?
  Visiting 400+ detail pages takes time. Keeping it separate means you can
  re-scrape listings cheaply any time and only run enrichment when needed.
  It also means a crash here never corrupts the raw listing data.

Usage:
  python scrapers/startech/enrich.py                        # latest raw file, all products
  python scrapers/startech/enrich.py --limit 10             # test with first 10 products
  python scrapers/startech/enrich.py --only-priced          # skip out-of-stock (no MPN needed for matching if no price)
  python scrapers/startech/enrich.py --input data/raw/startech_ram_20260526_171742.json
"""

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Force UTF-8 output so Unicode characters (Bengali taka, arrows) don't crash on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PAGE_DELAY = 2.0  # seconds between detail page requests


async def fetch_details(page, url: str) -> dict:
    """
    Visit a StarTech product detail page and extract MPN + full spec table.

    Confirmed HTML structure (from live page inspection + screenshots):
      MPN   : <li id="mpn">MPN: MMV8GD316C11U</li>  in .short-description ul
      Specs : .specification-tab table  →  <tr> with <td class="name"> / <td class="value">
              Rows with <td class="heading-row"> are section headers — skip them.
      Header: .product-info-table .product-info-group  →  Product Code, Brand, Status
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_selector(".short-description", timeout=10_000)
    except PlaywrightTimeout:
        return {"mpn": None, "specs": {}}

    # ── MPN ───────────────────────────────────────────────────────────────
    mpn = None
    mpn_el = await page.query_selector("li#mpn")
    if mpn_el:
        text = (await mpn_el.inner_text()).strip()
        mpn = text.split(":", 1)[-1].strip()

    # ── Specification tab table (the clean two-column table in Image 2) ───
    # <td class="name"> = label,  <td class="value"> = value
    # <td class="heading-row"> = section header, skip it
    specs = {}
    rows = await page.query_selector_all(".specification-tab table tr")
    for row in rows:
        if await row.query_selector("td.heading-row"):
            continue  # section header row (e.g. "Key Features", "Warranty Information")
        name_el = await row.query_selector("td.name")
        value_el = await row.query_selector("td.value")
        if name_el and value_el:
            label = (await name_el.inner_text()).strip()
            value = (await value_el.inner_text()).strip().replace("\n", " ")
            if label and value:
                specs[label] = value

    # ── Product header info (Product Code, Brand, Status) ─────────────────
    info_rows = await page.query_selector_all(".product-info-table tr.product-info-group")
    for row in info_rows:
        label_el = await row.query_selector(".product-info-label")
        value_el = await row.query_selector(".product-info-data")
        if label_el and value_el:
            label = (await label_el.inner_text()).strip()
            value = (await value_el.inner_text()).strip()
            if label in ("Product Code", "Brand", "Status", "Regular Price"):
                specs[label] = value

    return {"mpn": mpn, "specs": specs}


async def enrich(records: list[dict], limit: int | None, only_priced: bool) -> list[dict]:
    targets = records
    if only_priced:
        targets = [r for r in records if r.get("price_bdt") is not None]
    if limit:
        targets = targets[:limit]

    # Build a URL → index map so we can update in-place
    url_set = {r["product_url"] for r in targets if r.get("product_url")}
    enriched_cache: dict[str, dict] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; PCCompareBD-scraper/1.0; educational project)"
        )
        page = await context.new_page()

        for i, url in enumerate(url_set, 1):
            print(f"  [{i}/{len(url_set)}] {url}")
            details = await fetch_details(page, url)
            enriched_cache[url] = details
            time.sleep(PAGE_DELAY)

        await browser.close()

    # Merge enrichment back into records
    result = []
    for r in records:
        url = r.get("product_url")
        if url and url in enriched_cache:
            d = enriched_cache[url]
            result.append({**r, "mpn": d["mpn"], "specs": d["specs"]})
        else:
            result.append({**r, "mpn": None, "specs": {}})

    return result


def find_latest_raw_file() -> Path:
    files = sorted(Path("data/raw").glob("startech_ram_*.json"), reverse=True)
    # Skip already-enriched files
    files = [f for f in files if "enriched" not in f.name]
    if not files:
        raise FileNotFoundError("No raw files found. Run the scraper first.")
    return files[0]


def main():
    parser = argparse.ArgumentParser(description="Enrich StarTech listings with MPN + specs")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None,
                        help="Only enrich the first N products (for testing)")
    parser.add_argument("--only-priced", action="store_true",
                        help="Skip products with no price (saves time; unpriceable = no match needed)")
    args = parser.parse_args()

    input_path = args.input or find_latest_raw_file()
    print(f"Loading: {input_path}")
    with open(input_path, encoding="utf-8") as f:
        records = json.load(f)

    targets = [r for r in records if r.get("price_bdt")] if args.only_priced else records
    target_label = f"{len(targets)} {'priced' if args.only_priced else 'total'} products"
    if args.limit:
        target_label = f"first {min(args.limit, len(targets))} of {target_label}"
    print(f"Enriching {target_label}...")

    enriched = asyncio.run(enrich(records, args.limit, args.only_priced))

    out_dir = Path("data/raw")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"startech_ram_enriched_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    found_mpn = sum(1 for r in enriched if r.get("mpn"))
    print(f"\nMPN found for {found_mpn}/{len(enriched)} products.")
    print(f"Saved: {out_path}")
    print(f"Next:  python cleaning/normalize.py --input {out_path}")


if __name__ == "__main__":
    main()
