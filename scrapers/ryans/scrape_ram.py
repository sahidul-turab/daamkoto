"""
Ryans RAM scraper
Extracts: name, price (BDT), stock status, product URL, and inline specs from ryans.com

Key design notes:
- Ryans is behind Cloudflare's JS challenge ("Just a moment...") which auto-solves
  in ~5 seconds. We wait 8s after navigation and then look for product cards.
- We patch navigator.webdriver and pass --disable-blink-features=AutomationControlled
  to avoid being blocked by fingerprinting checks.
- All product data is in a `data-item` JSON attribute on `.product-preview-btn`
  inside each `.category-single-product` card — no separate XHR calls needed.
- Price logic: product_price2 (discounted) takes precedence over product_price1 (regular)
- Stock: product_is_exist == "1" AND product_is_upcoming == "0"

Usage:
  python scrapers/ryans/scrape_ram.py           # print only
  python scrapers/ryans/scrape_ram.py --save    # print + save JSON to data/raw/
"""

import argparse
import asyncio
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://www.ryans.com"
CATEGORY_URL = f"{BASE_URL}/category/desktop-component-desktop-ram"
PAGE_DELAY = 2.5  # seconds between page requests (polite crawling)

# Patches applied before every page load — makes the browser look less like a bot
_STEALTH_SCRIPT = """\
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}};
"""


async def scrape_page(page, url: str) -> list[dict]:
    """Navigate to a category listing page and return all product dicts found."""
    await page.goto(url, wait_until="domcontentloaded")

    # Cloudflare JS challenge auto-resolves in 3-8s then navigates to the real page.
    # wait_for_selector with a 20s timeout covers both fast and slow CF resolutions.
    try:
        await page.wait_for_selector(".category-single-product", timeout=20_000)
    except PlaywrightTimeout:
        print(f"  [warn] No .category-single-product cards found on {url}")
        return []

    # Brief scroll to ensure all cards are rendered
    for y in [400, 900, 1400]:
        await page.evaluate(f"window.scrollTo(0, {y})")
        await page.wait_for_timeout(200)
    await page.wait_for_timeout(800)

    cards = await page.query_selector_all(".category-single-product")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        # The first .product-preview-btn in each card carries the data-item JSON blob
        btn = await card.query_selector(".product-preview-btn")
        if not btn:
            continue

        data_item_str = await btn.get_attribute("data-item")
        if not data_item_str:
            continue

        try:
            item = json.loads(data_item_str)
        except json.JSONDecodeError:
            continue

        name = (item.get("product_name") or "").strip()
        if not name:
            continue

        slug = item.get("product_slug") or ""
        product_url = f"{BASE_URL}/{slug}" if slug else None

        # Discounted price (price2) wins; fall back to regular price (price1)
        price1 = float(item.get("product_price1") or 0)
        price2 = float(item.get("product_price2") or 0)
        price = price2 if price2 > 0 else price1 if price1 > 0 else None

        # product_is_exist: "1" = in stock; product_is_upcoming: "1" = not yet on sale
        is_exist = str(item.get("product_is_exist", "0")) == "1"
        is_upcoming = str(item.get("product_is_upcoming", "0")) == "1"
        in_stock = is_exist and not is_upcoming
        stock_status = ("upcoming" if is_upcoming else ("in_stock" if in_stock else "out_of_stock"))

        product_code_inv = item.get("product_code_inv")

        # attributes_list is a doubly-encoded JSON string: parse it to get spec key/values
        inline_specs = {}
        attrs_raw = item.get("attributes_list")
        if attrs_raw:
            try:
                attrs_data = json.loads(attrs_raw).get("data", {})
                inline_specs = attrs_data
            except (json.JSONDecodeError, AttributeError):
                pass

        products.append({
            "name": name,
            "price_bdt": price,
            "in_stock": in_stock if price is not None else False,
            "stock_status": stock_status if price is not None else "out_of_stock",
            "product_url": product_url,
            "product_code_inv": product_code_inv,
            "inline_specs": inline_specs,
            "source": "Ryans",
            "pc_bundle_only": False,
            "scraped_at": scraped_at,
        })

    return products


def print_results(products: list[dict]) -> None:
    col_w = {"#": 4, "Price (BDT)": 12, "Stock": 8, "Name": 55}
    header = (f"{'#':<{col_w['#']}} {'Price (BDT)':<{col_w['Price (BDT)']}} "
              f"{'Stock':<{col_w['Stock']}} {'Name':<{col_w['Name']}}")
    sep = "-" * len(header)

    print(f"\n{'='*len(header)}")
    print(f"  Ryans RAM Listings  —  {len(products)} products found")
    print(f"{'='*len(header)}")
    print(header)
    print(sep)

    for i, p in enumerate(products, 1):
        price_str = f"{p['price_bdt']:,.0f}" if p["price_bdt"] else "N/A"
        stock_str = "Yes" if p["in_stock"] else "No"
        print(f"{i:<{col_w['#']}} {price_str:<{col_w['Price (BDT)']}} "
              f"{stock_str:<{col_w['Stock']}} {p['name'][:col_w['Name']]}")

    print(sep)
    in_stock_priced = [p for p in products if p["in_stock"] and p["price_bdt"]]
    if in_stock_priced:
        cheapest = min(in_stock_priced, key=lambda p: p["price_bdt"])
        print(f"\nCheapest in-stock: {cheapest['name'][:60]} — ৳{cheapest['price_bdt']:,.0f}")
        print(f"URL: {cheapest['product_url']}")


def save_results(products: list[dict]) -> Path:
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"ryans_ram_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    return out_path


async def _make_context(browser):
    """Return a fresh browser context with stealth patches applied."""
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    await context.add_init_script(_STEALTH_SCRIPT)
    return context


async def main(save: bool = False):
    all_products = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page_num = 1
        while True:
            url = CATEGORY_URL if page_num == 1 else f"{CATEGORY_URL}?page={page_num}"
            print(f"Scraping page {page_num}: {url}")

            # Fresh context per page: cookies from prior pages cause CF to re-challenge
            context = await _make_context(browser)
            page = await context.new_page()
            products = await scrape_page(page, url)
            await context.close()

            print(f"  Found {len(products)} products.")

            if not products:
                print("  No products found — reached end of listings.")
                break

            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)

        await browser.close()

    if save:
        path = save_results(all_products)
        print(f"\nSaved {len(all_products)} records → {path}")

    print_results(all_products)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Ryans RAM listings")
    parser.add_argument("--save", action="store_true", help="Save results to data/raw/ as JSON")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
