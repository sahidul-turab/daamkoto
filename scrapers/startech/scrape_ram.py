"""
StarTech RAM scraper
Extracts: name, price (BDT), product URL from startech.com.bd/component/ram
Respects robots.txt: category pages are allowed; we sleep between pages.

Usage:
  python scrapers/startech/scrape_ram.py           # print only
  python scrapers/startech/scrape_ram.py --save    # print + save JSON to data/raw/
"""

import argparse
import asyncio
import io
import json
import re
import sys
import time

# Force UTF-8 output so Bengali taka symbol (৳) doesn't crash on Windows cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://www.startech.com.bd"
START_URL = f"{BASE_URL}/component/ram"
PAGE_DELAY = 2.5  # seconds between page requests (polite crawling)


def clean_price(raw: str) -> float | None:
    """Strip currency symbols/commas and return a float, or None if unparseable."""
    digits = re.sub(r"[^\d.]", "", raw)
    try:
        return float(digits)
    except ValueError:
        return None


async def scrape_page(page, url: str) -> list[dict]:
    """Navigate to a listing page and return all product dicts found."""
    await page.goto(url, wait_until="domcontentloaded")

    # StarTech loads products via JS — wait until at least one product card appears.
    # The selector '.p-item' matches each product card on their category pages.
    try:
        await page.wait_for_selector(".p-item", timeout=15_000)
    except PlaywrightTimeout:
        print(f"  [warn] No .p-item cards found on {url} — page may have changed structure.")
        return []

    cards = await page.query_selector_all(".p-item")
    products = []

    for card in cards:
        # --- Product name ---
        name_el = await card.query_selector(".p-item-name a")
        if not name_el:
            # fallback: any <a> inside the name container
            name_el = await card.query_selector("h4 a, .product-name a")
        name = (await name_el.inner_text()).strip() if name_el else None

        # --- Product URL ---
        href = await name_el.get_attribute("href") if name_el else None
        product_url = href if href and href.startswith("http") else (BASE_URL + href if href else None)

        # --- Price ---
        # StarTech shows a "new" (current) price and sometimes a strikethrough old price.
        price_el = await card.query_selector(".p-item-price span")
        if not price_el:
            price_el = await card.query_selector(".price-new, .special-price, .price")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None

        # --- Stock status ---
        stock_el = await card.query_selector(".p-item-add .btn, .stock-status, .out-of-stock")
        stock_text = (await stock_el.inner_text()).strip().lower() if stock_el else ""
        if any(w in stock_text for w in ("out", "unavailable")):
            stock_status = "out_of_stock"
        elif any(w in stock_text for w in ("upcoming", "pre order", "pre-order", "coming soon")):
            stock_status = "upcoming"
        elif "bundle" in stock_text or "only with" in stock_text:
            stock_status = "bundle_only"
        else:
            stock_status = "in_stock"
        in_stock = stock_status == "in_stock"

        # --- Inline specs from card bullet list (.p-item-details ul li) ---
        # Each <li> is a comma-separated "Label: Value, Label2: Value2" string.
        # e.g. "Capacity: 8GB, Type: DDR3"  or  "Frequency: 1600MHz, Voltage: 1.5V"
        # Capturing these saves us from needing the detail page for basic specs.
        inline_specs = {}
        spec_items = await card.query_selector_all(".p-item-details ul li")
        for li in spec_items:
            text = (await li.inner_text()).strip()
            for part in text.split(","):
                if ":" in part:
                    label, _, value = part.strip().partition(":")
                    inline_specs[label.strip()] = value.strip()

        if name:  # skip cards with no readable name
            card_text = (await card.inner_text()).lower()
            pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))
            products.append({
                "name": name,
                "price_bdt": price,
                "in_stock": in_stock if price is not None else False,
                "stock_status": stock_status if price is not None else "out_of_stock",
                "product_url": product_url,
                "inline_specs": inline_specs,
                "source": "StarTech",
                "pc_bundle_only": pc_bundle_only,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

    return products


def print_results(products: list[dict]) -> None:
    col_w = {"#": 4, "Price (BDT)": 12, "Stock": 8, "Name": 55}
    header = (f"{'#':<{col_w['#']}} {'Price (BDT)':<{col_w['Price (BDT)']}} "
              f"{'Stock':<{col_w['Stock']}} {'Name':<{col_w['Name']}}")
    sep = "-" * len(header)

    print(f"\n{'='*len(header)}")
    print(f"  StarTech RAM Listings  —  {len(products)} products found")
    print(f"{'='*len(header)}")
    print(header)
    print(sep)

    for i, p in enumerate(products, 1):
        price_str = f"{p['price_bdt']:,.0f}" if p["price_bdt"] else "N/A"
        stock_str = "Yes" if p["in_stock"] else "No"
        name_str = p["name"][:col_w["Name"]]
        print(f"{i:<{col_w['#']}} {price_str:<{col_w['Price (BDT)']}} "
              f"{stock_str:<{col_w['Stock']}} {name_str}")

    print(sep)
    in_stock = [p for p in products if p["in_stock"] and p["price_bdt"]]
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"\nCheapest in-stock: {cheapest['name'][:60]} — ৳{cheapest['price_bdt']:,.0f}")
        print(f"URL: {cheapest['product_url']}")


def save_results(products: list[dict]) -> Path:
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"startech_ram_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    return out_path


async def main(save: bool = False):
    all_products = []

    async with async_playwright() as pw:
        # headless=True means no browser window opens; set False if you want to watch it live
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; PCCompareBD-scraper/1.0; educational project)"
        )
        page = await context.new_page()

        # URL-based pagination: StarTech uses ?page=N on category pages.
        # We keep incrementing until a page returns 0 products (we've gone past the last page).
        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
            print(f"Scraping page {page_num}: {url}")
            products = await scrape_page(page, url)
            print(f"  Found {len(products)} products on this page.")

            if not products:
                print("  No products found — reached end of listings.")
                break

            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)  # polite delay between requests

        await browser.close()

    if save:
        path = save_results(all_products)
        print(f"\nSaved {len(all_products)} records: {path}")

    print_results(all_products)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape StarTech RAM listings")
    parser.add_argument("--save", action="store_true", help="Save results to data/raw/ as JSON")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
