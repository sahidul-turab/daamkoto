"""VibeGaming Motherboard scraper — WooCommerce.

Listing: /product-category/component/motherboard/

Cards are `section.product[data-product_id]`. Each one carries a hidden
`data-gtm4wp_product_data` JSON blob holding the exact numeric price, stock
status and product link, so the price needs no currency parsing and a sale price
is never confused with the struck-through original. That blob comes from an
analytics plugin, so every field it provides also has a markup fallback — if the
plugin is ever disabled the scraper must degrade to the rendered page, not
quietly report NULL prices.

Pagination is WooCommerce's /page/N/ suffix.

Usage:
  python scrapers/vibegaming/scrape_motherboard.py           # print only
  python scrapers/vibegaming/scrape_motherboard.py --save    # save JSON to data/raw/
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

BASE_URL = "https://vibegaming.com.bd"
START_URLS = [
    f"{BASE_URL}/product-category/component/motherboard/",
]
PAGE_DELAY = 2.5
# Safety valve. The largest listing here is ~35 pages; anything past this means
# pagination stopped terminating.
MAX_PAGES = 100

CARD_SELECTOR = "section.product[data-product_id]"

EXCLUDE_NAME = None


def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", raw.strip().split("\n")[0])
    try:
        val = float(digits) if digits else None
        return val if val else None
    except ValueError:
        return None


async def extract_image(card):
    """First real product-image URL on a listing card (absolute), or None.

    Reads common lazy-load attributes, skips inline-data / SVG icons, and
    resolves relative URLs against the page base URI in-browser.
    """
    for img in await card.query_selector_all("img"):
        url = await img.evaluate(
            """el => {
                const v = el.getAttribute('data-src') || el.getAttribute('data-original')
                       || el.getAttribute('data-lazy') || el.getAttribute('src') || '';
                if (!v || v.startsWith('data:') || v.toLowerCase().endsWith('.svg')) return '';
                try { return new URL(v, document.baseURI).href; } catch (e) { return ''; }
            }"""
        )
        if url:
            return url
    return None


async def gtm_payload(card) -> dict:
    """The card's analytics blob, or {} if the plugin did not render one."""
    el = await card.query_selector("[data-gtm4wp_product_data]")
    if not el:
        return {}
    raw = await el.get_attribute("data-gtm4wp_product_data")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


async def dom_price(card) -> float | None:
    """Current price from the rendered markup.

    A discounted card renders the old price in <del> and the current one in
    <ins>, so <ins> wins; otherwise take the first amount that is not inside a
    <del>. On a variable product's price range that is the low end.
    """
    el = await card.query_selector(".price ins .woocommerce-Price-amount")
    if el:
        price = clean_price(await el.inner_text())
        if price:
            return price
    for amount in await card.query_selector_all(".price .woocommerce-Price-amount"):
        if await amount.evaluate("e => !!e.closest('del')"):
            continue
        price = clean_price(await amount.inner_text())
        if price:
            return price
    return None


async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    try:
        await page.wait_for_selector(CARD_SELECTOR, timeout=15_000)
    except PlaywrightTimeout:
        return []

    for y in [400, 800, 1600]:
        await page.evaluate(f"window.scrollTo(0, {y})")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(500)

    cards = await page.query_selector_all(CARD_SELECTOR)
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        gtm = await gtm_payload(card)

        # Name: prefer the rendered heading. WordPress stores titles with HTML
        # entities ("&#8211;") that the browser decodes but the JSON blob does
        # not, and the name is what fuzzy matching keys on.
        name_el = await card.query_selector("h3.product-name a") or \
                  await card.query_selector(".heading-title a")
        name = (await name_el.inner_text()).strip() if name_el else ""
        if not name:
            name = str(gtm.get("item_name") or "").strip()
        if not name:
            continue

        if EXCLUDE_NAME and EXCLUDE_NAME.search(name):
            # Loud on purpose: a silently shrinking category is the failure
            # mode this repo keeps getting bitten by.
            print(f"    [excluded, wrong category] {name[:70]}")
            continue

        href = (await name_el.get_attribute("href")) if name_el else None
        product_url = href or gtm.get("productlink") or None
        if product_url and not product_url.startswith("http"):
            product_url = BASE_URL + product_url

        # Price: the blob is authoritative when present (already numeric and
        # already the current, post-discount figure).
        price = None
        raw_price = gtm.get("price")
        if raw_price not in (None, "", 0, "0"):
            try:
                price = float(raw_price) or None
            except (TypeError, ValueError):
                price = None
        if price is None:
            price = await dom_price(card)

        # Stock: blob first, else the card's own instock/outofstock class.
        stock_flag = str(gtm.get("stockstatus") or "").lower()
        if not stock_flag:
            classes = (await card.get_attribute("class") or "").lower()
            stock_flag = "outofstock" if "outofstock" in classes else (
                "instock" if "instock" in classes else "")
        # Anything that is not plainly in stock (backorder included) is not
        # something a buyer can have today.
        stock_status = "in_stock" if stock_flag == "instock" else "out_of_stock"
        if price is None:
            stock_status = "out_of_stock"
        in_stock = stock_status == "in_stock"

        card_text = (await card.inner_text()).lower()
        pc_bundle_only = any(w in card_text for w in
                             ("bundle only", "bundle with pc", "only bundle", "pc bundle"))

        products.append({
            "image_url": await extract_image(card),
            "name": name,
            "price_bdt": price,
            "in_stock": in_stock,
            "stock_status": stock_status,
            "product_url": product_url,
            "inline_specs": {},
            "source": "VibeGaming",
            "pc_bundle_only": pc_bundle_only,
            "scraped_at": scraped_at,
            "_product_id": await card.get_attribute("data-product_id"),
        })

    return products


async def scrape_listing(page, start_url: str, seen: set) -> list[dict]:
    """Page through one listing URL, skipping products already collected."""
    collected = []
    prev_ids: set = set()

    for page_num in range(1, MAX_PAGES + 1):
        url = start_url if page_num == 1 else f"{start_url}page/{page_num}/"
        print(f"  page {page_num}: {url}")
        products = await scrape_page(page, url)
        if not products:
            print("    no products — end of listing.")
            break

        page_ids = {p["_product_id"] for p in products}
        # An out-of-range page number can be served as page 1 again rather than
        # a 404; that repeat is the signal to stop.
        if page_ids and page_ids == prev_ids:
            print("    same products as previous page — end of listing.")
            break
        prev_ids = page_ids

        new = [p for p in products if p["_product_id"] not in seen]
        seen.update(page_ids)
        collected.extend(new)
        print(f"    {len(products)} found, {len(new)} new.")

        time.sleep(PAGE_DELAY)

    return collected


async def main(save: bool = False):
    all_products: list[dict] = []
    seen: set = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        for start_url in START_URLS:
            print(f"\nListing: {start_url}")
            all_products.extend(await scrape_listing(page, start_url, seen))

        await browser.close()

    for product in all_products:
        product.pop("_product_id", None)

    if save:
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"vibegaming_motherboard_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {cheapest['name'][:70]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape VibeGaming motherboard listings")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
