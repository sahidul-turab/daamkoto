"""
Techland Processor scraper
Extracts: name, price (BDT), stock, product URL from techlandbd.com/pc-components/processor

Same structure as scrape_gpu.py — Tailwind CSS SPA with click-based pagination.

Usage:
  python scrapers/techland/scrape_processor.py           # print only
  python scrapers/techland/scrape_processor.py --save    # save JSON to data/raw/
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

BASE_URL  = "https://www.techlandbd.com"
START_URL = f"{BASE_URL}/pc-components/processor"
PAGE_DELAY = 2.5


def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", raw.split("\n")[0])
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


async def extract_products_from_page(page) -> list[dict]:
    cards = await page.query_selector_all("article.products-list__item")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        name_el = await card.query_selector("h4 a")
        if not name_el:
            continue
        name = (await name_el.inner_text()).strip()
        if not name:
            label = await name_el.get_attribute("aria-label") or ""
            name = label.replace("product details", "").strip()
        if not name:
            continue

        href = await name_el.get_attribute("href") or ""
        product_url = href if href.startswith("http") else (BASE_URL + href if href else None)

        price_el = await card.query_selector("span.text-base.font-bold")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None

        stock_el = await card.query_selector(".text-right p")
        stock_text = (await stock_el.inner_text()).strip().lower() if stock_el else ""
        if "in stock" in stock_text:
            stock_status = "in_stock"
        elif any(w in stock_text for w in ("upcoming", "pre order", "pre-order", "coming soon")):
            stock_status = "upcoming"
        else:
            stock_status = "out_of_stock"
        in_stock = stock_status == "in_stock"

        card_text = (await card.inner_text()).lower()
        pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))
        products.append({
            "name": name,
            "price_bdt": price,
            "in_stock": in_stock if price is not None else False,
            "stock_status": stock_status if price is not None else "out_of_stock",
            "product_url": product_url,
            "inline_specs": {},
            "source": "Techland",
            "pc_bundle_only": pc_bundle_only,
            "scraped_at": scraped_at,
        })

    return products


async def get_total_pages(page) -> int:
    count = await page.evaluate("""() => {
        const btns = [...document.querySelectorAll('button')]
            .filter(b => /^\\d+$/.test(b.innerText.trim()));
        const nums = btns.map(b => parseInt(b.innerText.trim(), 10));
        return nums.length > 0 ? Math.max(...nums) : 1;
    }""")
    return count


async def click_page(page, page_num: int) -> bool:
    clicked = await page.evaluate(f"""(num) => {{
        const btns = [...document.querySelectorAll('button')]
            .filter(b => b.innerText.trim() === String(num));
        if (btns.length > 0) {{ btns[0].click(); return true; }}
        return false;
    }}""", page_num)
    return clicked


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

        print(f"Loading: {START_URL}")
        await page.goto(START_URL, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector("article.products-list__item", timeout=15_000)
        except PlaywrightTimeout:
            print("ERROR: No product cards found. The site may have changed structure.")
            await browser.close()
            return

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)

        total_pages = await get_total_pages(page)
        print(f"Total pages: {total_pages}")

        for page_num in range(1, total_pages + 1):
            print(f"Scraping page {page_num}/{total_pages}...")

            products = await extract_products_from_page(page)
            print(f"  Found {len(products)} products.")
            all_products.extend(products)

            if page_num < total_pages:
                clicked = await click_page(page, page_num + 1)
                if not clicked:
                    print(f"  Could not find button for page {page_num + 1} -- stopping.")
                    break
                await page.wait_for_timeout(int(PAGE_DELAY * 1000))
                try:
                    await page.wait_for_selector("article.products-list__item", timeout=10_000)
                except PlaywrightTimeout:
                    print(f"  Products didn't reload on page {page_num + 1} -- stopping.")
                    break

        await browser.close()

    if save:
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"techland_processor_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {cheapest['name'][:70]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Techland Processor listings")
    parser.add_argument("--save", action="store_true", help="Save results to data/raw/")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
