"""Ryans PSU scraper — CF bypass, fresh context per page."""

import argparse, asyncio, io, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL     = "https://www.ryans.com"
CATEGORY_URL = f"{BASE_URL}/category/desktop-component-power-supply"
PAGE_DELAY   = 2.5

_STEALTH_SCRIPT = """\
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}};
"""

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".category-single-product", timeout=20_000)
    except PlaywrightTimeout: return []
    for y in [400, 900, 1400]:
        await page.evaluate(f"window.scrollTo(0, {y})")
        await page.wait_for_timeout(200)
    await page.wait_for_timeout(800)
    cards = await page.query_selector_all(".category-single-product")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in cards:
        btn = await card.query_selector(".product-preview-btn")
        if not btn: continue
        data_item_str = await btn.get_attribute("data-item")
        if not data_item_str: continue
        try: item = json.loads(data_item_str)
        except json.JSONDecodeError: continue
        name = (item.get("product_name") or "").strip()
        if not name: continue
        slug = item.get("product_slug") or ""
        product_url = f"{BASE_URL}/{slug}" if slug else None
        price1 = float(item.get("product_price1") or 0)
        price2 = float(item.get("product_price2") or 0)
        price = price2 if price2 > 0 else price1 if price1 > 0 else None
        is_exist    = str(item.get("product_is_exist",    "0")) == "1"
        is_upcoming = str(item.get("product_is_upcoming", "0")) == "1"
        in_stock = is_exist and not is_upcoming
        stock_status = ("upcoming" if is_upcoming else ("in_stock" if in_stock else "out_of_stock"))
        inline_specs = {}
        attrs_raw = item.get("attributes_list")
        if attrs_raw:
            try: inline_specs = json.loads(attrs_raw).get("data", {})
            except (json.JSONDecodeError, AttributeError): pass
        products.append({"name": name, "price_bdt": price,
            "in_stock": in_stock if price is not None else False,
            "stock_status": stock_status if price is not None else "out_of_stock",
            "product_url": product_url, "inline_specs": inline_specs,
            "source": "Ryans",
            "pc_bundle_only": False, "scraped_at": scraped_at})
    return products

async def _make_context(browser):
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900})
    await ctx.add_init_script(_STEALTH_SCRIPT)
    return ctx

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page_num = 1
        while True:
            url = CATEGORY_URL if page_num == 1 else f"{CATEGORY_URL}?page={page_num}"
            print(f"Scraping page {page_num}: {url}")
            ctx = await _make_context(browser)
            page = await ctx.new_page()
            products = await scrape_page(page, url)
            await ctx.close()
            print(f"  Found {len(products)} products.")
            if not products: break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)
        await browser.close()
    if save:
        out_dir = Path("data/raw"); out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"ryans_psu_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
