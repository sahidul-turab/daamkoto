"""
Generate missing OpenCart-structure scrapers for a retailer.

Usage:
  python scrapers/gen_opencart_scrapers.py
"""
import os
from pathlib import Path

# (category_name, slug, output_filename, source_label)
SKYLAND_CATS = [
    ("laptop_ram",   "laptop-ram",   "scrape_laptop_ram.py",  "Skyland"),
    ("processor",    "processor",    "scrape_processor.py",   "Skyland"),
    ("motherboard",  "motherboard",  "scrape_motherboard.py", "Skyland"),
    ("ssd",          "ssd",          "scrape_ssd.py",         "Skyland"),
    ("portable_ssd", "portable-ssd", "scrape_portable_ssd.py","Skyland"),
    ("hdd",          "hard-disk",    "scrape_hdd.py",         "Skyland"),
    ("portable_hdd", "portable-hdd", "scrape_portable_hdd.py","Skyland"),
    ("psu",          "power-supply", "scrape_psu.py",         "Skyland"),
    ("cooler",       "cpu-cooler",   "scrape_cooler.py",      "Skyland"),
    ("casing_cooler","casing-fan",   "scrape_casing_cooler.py","Skyland"),
    ("casing",       "casing",       "scrape_casing.py",      "Skyland"),
]

CREATUS_CATS = [
    ("laptop_ram",   "laptop-ram",   "scrape_laptop_ram.py",  "Creatus"),
    ("processor",    "processor",    "scrape_processor.py",   "Creatus"),
    ("motherboard",  "motherboard",  "scrape_motherboard.py", "Creatus"),
    ("ssd",          "ssd",          "scrape_ssd.py",         "Creatus"),
    ("portable_ssd", "portable-ssd", "scrape_portable_ssd.py","Creatus"),
    ("hdd",          "hard-disk",    "scrape_hdd.py",         "Creatus"),
    ("portable_hdd", "portable-hdd", "scrape_portable_hdd.py","Creatus"),
    ("psu",          "power-supply", "scrape_psu.py",         "Creatus"),
    ("cooler",       "cpu-cooler",   "scrape_cooler.py",      "Creatus"),
    ("casing_cooler","casing-fan",   "scrape_casing_cooler.py","Creatus"),
    ("casing",       "casing",       "scrape_casing.py",      "Creatus"),
]

RETAILERS = {
    "skyland": ("https://www.skyland.com.bd", SKYLAND_CATS),
    "creatus": ("https://www.creatus.com.bd", CREATUS_CATS),
}

TEMPLATE = '''\
"""
{retailer_title} {cat_label} scraper — OpenCart structure.

Usage:
  python scrapers/{retailer}/scrape_{cat_name}.py           # print only
  python scrapers/{retailer}/scrape_{cat_name}.py --save    # save JSON to data/raw/
"""

import argparse
import asyncio
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "{base_url}"
START_URL = f"{{BASE_URL}}/{slug}"
PAGE_DELAY = 2.5


def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\\d.]", "", raw.strip().split("\\n")[0])
    try:
        val = float(digits) if digits else None
        return val if val else None
    except ValueError:
        return None


async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".product-thumb", timeout=15_000)
    except PlaywrightTimeout:
        return []

    for y in [400, 800]:
        await page.evaluate(f"window.scrollTo(0, {{y}})")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(500)

    cards = await page.query_selector_all(".product-thumb")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        name_el = await card.query_selector(".caption .name a")
        if not name_el:
            continue
        name = (await name_el.inner_text()).strip()
        if not name:
            continue

        href = await name_el.get_attribute("href") or ""
        product_url = href if href.startswith("http") else (BASE_URL + href if href else None)

        price_el = await card.query_selector(".price .price-new")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None

        in_stock = price is not None

        card_text = (await card.inner_text()).lower()
        pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))

        products.append({{
            "name": name,
            "price_bdt": price,
            "in_stock": in_stock,
            "product_url": product_url,
            "inline_specs": {{}},
            "source": "{source}",
            "pc_bundle_only": pc_bundle_only,
            "scraped_at": scraped_at,
        }})

    return products


async def main(save: bool = False):
    all_products = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={{"width": 1280, "height": 900}},
        )
        page = await context.new_page()

        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{{START_URL}}?page={{page_num}}"
            print(f"Scraping page {{page_num}}: {{url}}")
            products = await scrape_page(page, url)
            print(f"  Found {{len(products)}} products.")
            if not products:
                print("  No products — reached end.")
                break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)

        await browser.close()

    if save:
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{retailer}_{cat_name}_{{timestamp}}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {{cheapest[\'name\'][:70]}}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape {retailer_title} {cat_label} listings")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
'''

CAT_LABELS = {
    "laptop_ram":   "Laptop RAM",
    "processor":    "Processor",
    "motherboard":  "Motherboard",
    "ssd":          "SSD",
    "portable_ssd": "Portable SSD",
    "hdd":          "HDD",
    "portable_hdd": "Portable HDD",
    "psu":          "PSU",
    "cooler":       "CPU Cooler",
    "casing_cooler":"Casing Cooler",
    "casing":       "Casing",
}

def generate():
    for retailer, (base_url, cats) in RETAILERS.items():
        out_dir = Path(f"scrapers/{retailer}")
        out_dir.mkdir(exist_ok=True)
        for cat_name, slug, filename, source in cats:
            out_path = out_dir / filename
            if out_path.exists():
                print(f"  skip  {out_path} (already exists)")
                continue
            content = TEMPLATE.format(
                retailer=retailer,
                retailer_title=retailer.title(),
                cat_name=cat_name,
                cat_label=CAT_LABELS[cat_name],
                base_url=base_url,
                slug=slug,
                source=source,
            )
            out_path.write_text(content, encoding="utf-8")
            print(f"  wrote {out_path}")

if __name__ == "__main__":
    generate()
