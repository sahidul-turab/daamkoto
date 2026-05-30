"""
Trust Tech BD RAM scraper — custom Vue-based storefront.

Card: .product-card
Name: a.product-name (href for URL), a.product-name h6 (text)
Price: .product-card-bottom .product-price  (format: "BDT 9,000.00")
Stock: price presence (all cards show price = in stock)
Pagination: ?page=N

Note: page mixes desktop and laptop RAM listings — normalizer will
      classify them by name content.

Usage:
  python scrapers/trusttech/scrape_ram.py           # print only
  python scrapers/trusttech/scrape_ram.py --save    # save JSON to data/raw/
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

BASE_URL  = "https://www.trusttechbd.com"
START_URL = f"{BASE_URL}/categories/ram"
PAGE_DELAY = 2.5


def clean_price(raw: str) -> float | None:
    # Handles "BDT 9,000.00" and "BDT 9,000.00 BDT 12,000.00" (old price in span)
    # Take the first number found (current price, not strikethrough previous price)
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", raw.strip())
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
        return val if val > 0 else None
    except ValueError:
        return None


async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".product-card", timeout=15_000)
    except PlaywrightTimeout:
        return []

    await page.wait_for_timeout(1500)

    cards = await page.query_selector_all(".product-card")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        # Name comes from h6 inside the anchor with class product-name
        name_el = await card.query_selector("a.product-name h6")
        if not name_el:
            continue
        name = (await name_el.inner_text()).strip()
        if not name:
            continue

        link_el = await card.query_selector("a.product-name")
        href = await link_el.get_attribute("href") if link_el else ""
        product_url = href if href and href.startswith("http") else (BASE_URL + href if href else None)

        # Price is in the bottom section (avoid the cloned price-clone div)
        price_el = await card.query_selector(".product-card-bottom .product-price")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None

        card_text = (await card.inner_text()).lower()
        if any(w in card_text for w in ("out of stock", "out-of-stock")) or price is None:
            stock_status = "out_of_stock"
        else:
            stock_status = "in_stock"
        in_stock = stock_status == "in_stock"

        pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))
        products.append({
            "name": name,
            "price_bdt": price,
            "in_stock": in_stock,
            "stock_status": stock_status,
            "product_url": product_url,
            "inline_specs": {},
            "source": "TrustTech",
            "pc_bundle_only": pc_bundle_only,
            "scraped_at": scraped_at,
        })

    return products


async def main(save: bool = False):
    all_products = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
            print(f"Scraping page {page_num}: {url}")
            products = await scrape_page(page, url)
            print(f"  Found {len(products)} products.")
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
        out_path = out_dir / f"trusttech_ram_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {cheapest['name'][:70]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Trust Tech BD RAM listings")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
