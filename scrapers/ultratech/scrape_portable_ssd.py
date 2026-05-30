"""Portable SSD scraper for UltraTech — URL: /portable-ssd"""

import argparse, asyncio, io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.ultratech.com.bd"
START_URL = f"{BASE_URL}/portable-ssd"
PAGE_DELAY = 2.5

def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", raw.strip().split("\n")[0])
    try: return float(digits) if digits else None
    except ValueError: return None

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".product-thumb", timeout=15_000)
    except PlaywrightTimeout: return []
    for y in [400, 800]:
        await page.evaluate(f"window.scrollTo(0, {y})")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(500)
    cards = await page.query_selector_all(".product-thumb")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in cards:
        name_el = await card.query_selector(".caption .name a")
        if not name_el:
            name_el = await card.query_selector("img")
            name = (await name_el.get_attribute("alt") or "").strip() if name_el else None
        else:
            name = (await name_el.inner_text()).strip()
        if not name: continue
        link_el = await card.query_selector(".caption .name a, .product-img")
        href = await link_el.get_attribute("href") if link_el else ""
        product_url = href if href and href.startswith("http") else (BASE_URL + href if href else None)
        price_el = await card.query_selector(".price .price-new")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None
        price_old_el = await card.query_selector(".price-old")
        raw_old = (await price_old_el.inner_text()).strip() if price_old_el else None
        old_price = clean_price(raw_old) if raw_old else None
        extreme_discount = bool(old_price and price and price < old_price * 0.10)
        cart_btn = await card.query_selector(".btn-cart, [onclick*='cart.add']")
        card_text = (await card.inner_text()).lower()
        if (extreme_discount or
                any(w in card_text for w in ("out of stock", "out-of-stock", "stock out"))):
            stock_status = "out_of_stock"
        elif cart_btn is not None and price is not None:
            stock_status = "in_stock"
        else:
            stock_status = "out_of_stock"
        in_stock = stock_status == "in_stock"
        pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))
        products.append({"name": name, "price_bdt": price, "in_stock": in_stock,
            "stock_status": stock_status,
            "product_url": product_url, "inline_specs": {},
            "source": "UltraTech",
            "pc_bundle_only": pc_bundle_only, "scraped_at": scraped_at})
    return products

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{START_URL}?page={page_num}"
            print(f"Scraping page {page_num}: {url}")
            products = await scrape_page(page, url)
            print(f"  Found {len(products)} products.")
            if not products: break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)
        await browser.close()
    if save:
        out_dir = Path("data/raw"); out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"ultratech_portable_ssd_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
