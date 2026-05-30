"""StarTech SSD scraper — URL: /ssd"""

import argparse, asyncio, io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.startech.com.bd"
START_URL = f"{BASE_URL}/ssd"
PAGE_DELAY = 2.5

def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", raw)
    try: return float(digits)
    except ValueError: return None

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".p-item", timeout=15_000)
    except PlaywrightTimeout: return []
    cards = await page.query_selector_all(".p-item")
    products = []
    for card in cards:
        name_el = await card.query_selector(".p-item-name a")
        if not name_el: name_el = await card.query_selector("h4 a, .product-name a")
        name = (await name_el.inner_text()).strip() if name_el else None
        href = await name_el.get_attribute("href") if name_el else None
        product_url = href if href and href.startswith("http") else (BASE_URL + href if href else None)
        price_el = await card.query_selector(".p-item-price span")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None
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
        inline_specs = {}
        for li in await card.query_selector_all(".p-item-details ul li"):
            text = (await li.inner_text()).strip()
            for part in text.split(","):
                if ":" in part:
                    label, _, value = part.strip().partition(":")
                    inline_specs[label.strip()] = value.strip()
        if name:
            card_text = (await card.inner_text()).lower()
            pc_bundle_only = any(w in card_text for w in ("bundle only", "bundle with pc", "only bundle", "pc bundle"))
            products.append({"name": name, "price_bdt": price,
                "in_stock": in_stock if price is not None else False,
                "stock_status": stock_status if price is not None else "out_of_stock",
                "product_url": product_url, "inline_specs": inline_specs,
                "source": "StarTech",
                "pc_bundle_only": pc_bundle_only, "scraped_at": datetime.now(timezone.utc).isoformat()})
    return products

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (compatible; PCCompareBD-scraper/1.0; educational project)")
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
        out_path = out_dir / f"startech_ssd_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(all_products)} records -> {out_path}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\nTotal: {len(all_products)} | In stock: {len(in_stock)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
