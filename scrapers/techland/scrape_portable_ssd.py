"""
Techland Portable Ssd scraper
Extracts: name, price (BDT), stock, product URL from techlandbd.com/pc-components/external-ssd

Markup as of the Oct 2026 redesign (Laravel Livewire, server-rendered):
- Product cards: div.products-list__item (was article.products-list__item)
- Name: h2 inside the card's title link (was h4 a)
- Price: div.font-bold inside .mt-auto. The green "Save: ৳2,500" badge is also
  bold and also holds a ৳ amount, so the price must be read from the footer.
  The struck-through old price carries .line-through and is ignored.
- Stock: a .v2-stock-pill ("Out of Stock", "Pre-Order", ...) replaces the
  Add to Cart button. No pill + an Add to Cart button means in stock.
- Pagination: ?page=N URLs (was click-only), so every page is a plain load.
- Cloudflare: a browser context's *second* navigation gets a 403 "Sorry, you
  have been blocked", while a fresh context (or plain curl) loads the same URL.
  So each page gets its own context, the same trick Ryans needs.

Every Techland listing holds products, so zero products is a failure: the
scraper exits 1 and run_pipeline.py reports the retailer as skipped instead of
recording a successful empty run. The old selectors silently returned zero for
83 days after the redesign.

Usage:
  python scrapers/techland/scrape_portable_ssd.py           # print only
  python scrapers/techland/scrape_portable_ssd.py --save    # save JSON to data/raw/
"""

import argparse
import asyncio
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.techlandbd.com"
START_URL = f"{BASE_URL}/pc-components/external-ssd"
PAGE_DELAY = 2.5
CARD = ".products-list__item"


def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", raw.split("\n")[0])
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


async def extract_image(card):
    """First real product-image URL on a listing card (absolute), or None.

    Reads common lazy-load attributes, skips inline-data / SVG icons, and
    resolves relative URLs against the page base URI in-browser, so it needs no
    per-site base URL and works across every retailer's markup.
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


def classify_stock(pill_text: str, has_cart_button: bool) -> str:
    text = pill_text.lower()
    if any(w in text for w in ("upcoming", "up coming", "pre order", "pre-order", "coming soon")):
        return "upcoming"
    if "out of stock" in text or "stock out" in text:
        return "out_of_stock"
    if "in stock" in text or (not text and has_cart_button):
        return "in_stock"
    return "out_of_stock"


async def extract_products_from_page(page) -> list[dict]:
    cards = await page.query_selector_all(CARD)
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        title_el = await card.query_selector("h2")
        if not title_el:
            continue
        name = (await title_el.inner_text()).strip()
        if not name:
            continue

        link_el = await card.query_selector("a:has(h2)")
        href = (await link_el.get_attribute("href") or "") if link_el else ""
        product_url = href if href.startswith("http") else (BASE_URL + href if href else None)

        price_el = await card.query_selector(".mt-auto div.font-bold:not(.line-through)")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None

        pill_el = await card.query_selector(".v2-stock-pill")
        pill_text = (await pill_el.inner_text()).strip() if pill_el else ""
        cart_el = await card.query_selector("button[wire\\:click^='addedToCart']")
        stock_status = classify_stock(pill_text, cart_el is not None)
        in_stock = stock_status == "in_stock"

        card_text = (await card.inner_text()).lower()
        pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))
        products.append({
            "image_url": await extract_image(card),
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
    return await page.evaluate("""() => {
        const nums = [...document.querySelectorAll('[wire\\\\:click^="gotoPage("]')]
            .map(b => parseInt((b.getAttribute('wire:click').match(/\\d+/) || ['1'])[0], 10));
        return nums.length > 0 ? Math.max(...nums) : 1;
    }""")


async def main(save: bool = False):
    all_products = []
    seen_urls = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        total_pages = 1
        page_num = 1
        while page_num <= total_pages:
            url = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
            print(f"Scraping page {page_num}/{total_pages}: {url}")
            # Fresh context per page — reusing one gets a Cloudflare 403 on page 2.
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_selector(CARD, timeout=15_000)
            except PlaywrightTimeout:
                print(f"  [warn] No {CARD} cards on {url} ({await page.title()!r}) -- stopping.")
                await context.close()
                break

            if page_num == 1:
                total_pages = await get_total_pages(page)
                print(f"Total pages: {total_pages}")

            products = [p for p in await extract_products_from_page(page)
                        if p["product_url"] not in seen_urls]
            await context.close()
            seen_urls.update(p["product_url"] for p in products)
            print(f"  Found {len(products)} products.")
            if not products:
                break
            all_products.extend(products)

            page_num += 1
            if page_num <= total_pages:
                await asyncio.sleep(PAGE_DELAY)

        await browser.close()

    if save:
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"techland_portable_ssd_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {cheapest['name'][:70]}")

    if not all_products:
        print("\nFAILED: zero products -- the site may have changed structure.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Techland Portable Ssd listings")
    parser.add_argument("--save", action="store_true", help="Save results to data/raw/")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
