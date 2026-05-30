"""Generate new scrapers for new categories."""
from pathlib import Path

UCC_TEMPLATE = '''\
"""{cat} scraper for UCC — URL: {url_path}"""

import argparse, asyncio, io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.ucc.com.bd"
START_URL = f"{{BASE_URL}}{url_path}"
PAGE_DELAY = 2.5

def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\\d.]", "", raw.strip().split("\\n")[0])
    try: return float(digits) if digits else None
    except ValueError: return None

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".product-thumb", timeout=15_000)
    except PlaywrightTimeout: return []
    for y in [400, 800]:
        await page.evaluate(f"window.scrollTo(0, {{y}})")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(500)
    cards = await page.query_selector_all(".product-thumb")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in cards:
        name_el = await card.query_selector(".caption .name a")
        if not name_el: continue
        name = (await name_el.inner_text()).strip()
        if not name: continue
        href = await name_el.get_attribute("href") or ""
        product_url = href if href.startswith("http") else (BASE_URL + href if href else None)
        price_el = await card.query_selector(".price .price-normal")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None
        stock_el = await card.query_selector(".stats")
        stock_text = (await stock_el.inner_text()).strip().lower() if stock_el else ""
        in_stock = "in stock" in stock_text if stock_el else (price is not None)
        products.append({{"name": name, "price_bdt": price, "in_stock": in_stock,
            "product_url": product_url, "inline_specs": {{}},
            "source": "UCC", "scraped_at": scraped_at}})
    return products

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={{"width": 1280, "height": 900}})
        page = await context.new_page()
        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{{START_URL}}?page={{page_num}}"
            print(f"Scraping page {{page_num}}: {{url}}")
            products = await scrape_page(page, url)
            print(f"  Found {{len(products)}} products.")
            if not products: break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)
        await browser.close()
    if save:
        out_dir = Path("data/raw"); out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"ucc_{slug}_{{ts}}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
'''

ULTRATECH_TEMPLATE = '''\
"""{cat} scraper for UltraTech — URL: {url_path}"""

import argparse, asyncio, io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.ultratech.com.bd"
START_URL = f"{{BASE_URL}}{url_path}"
PAGE_DELAY = 2.5

def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\\d.]", "", raw.strip().split("\\n")[0])
    try: return float(digits) if digits else None
    except ValueError: return None

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".product-thumb", timeout=15_000)
    except PlaywrightTimeout: return []
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
        in_stock = price is not None
        products.append({{"name": name, "price_bdt": price, "in_stock": in_stock,
            "product_url": product_url, "inline_specs": {{}},
            "source": "UltraTech", "scraped_at": scraped_at}})
    return products

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={{"width": 1280, "height": 900}})
        page = await context.new_page()
        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{{START_URL}}?page={{page_num}}"
            print(f"Scraping page {{page_num}}: {{url}}")
            products = await scrape_page(page, url)
            print(f"  Found {{len(products)}} products.")
            if not products: break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)
        await browser.close()
    if save:
        out_dir = Path("data/raw"); out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"ultratech_{slug}_{{ts}}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
'''

BINARYLOGIC_TEMPLATE = '''\
"""{cat} scraper for BinaryLogic — URL: {url_path}"""

import argparse, asyncio, io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.binarylogic.com.bd"
START_URL = f"{{BASE_URL}}{url_path}"
PAGE_DELAY = 2.5

def clean_price(raw: str) -> float | None:
    prices = re.findall(r"\\d[\\d,]+", raw)
    if not prices: return None
    try: return float(prices[-1].replace(",", ""))
    except ValueError: return None

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".p-item", timeout=15_000)
    except PlaywrightTimeout: return []
    await page.wait_for_timeout(800)
    cards = await page.query_selector_all(".p-item")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in cards:
        name_el = await card.query_selector(".p-item-name a")
        if not name_el: continue
        name = (await name_el.inner_text()).strip()
        if not name: continue
        href = await name_el.get_attribute("href") or ""
        product_url = href if href.startswith("http") else (BASE_URL + href if href else None)
        price_el = await card.query_selector(".p-item-price")
        raw_price = (await price_el.inner_text()).strip() if price_el else None
        price = clean_price(raw_price) if raw_price else None
        in_stock = price is not None
        products.append({{"name": name, "price_bdt": price, "in_stock": in_stock,
            "product_url": product_url, "inline_specs": {{}},
            "source": "BinaryLogic", "scraped_at": scraped_at}})
    return products

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={{"width": 1280, "height": 900}})
        page = await context.new_page()
        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{{START_URL}}?page={{page_num}}"
            print(f"Scraping page {{page_num}}: {{url}}")
            products = await scrape_page(page, url)
            print(f"  Found {{len(products)}} products.")
            if not products: break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)
        await browser.close()
    if save:
        out_dir = Path("data/raw"); out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"binarylogic_{slug}_{{ts}}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
'''

POTAKAIT_TEMPLATE = '''\
"""{cat} scraper for PotakaIT — URL: {url_path}"""

import argparse, asyncio, io, json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL  = "https://www.potakait.com"
START_URL = f"{{BASE_URL}}{url_path}"
PAGE_DELAY = 2.5

def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\\d.]", "", raw.strip().split("\\n")[0])
    try: return float(digits) if digits else None
    except ValueError: return None

async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded")
    try: await page.wait_for_selector(".product-item", timeout=15_000)
    except PlaywrightTimeout: return []
    await page.wait_for_timeout(800)
    cards = await page.query_selector_all(".product-item")
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in cards:
        name_el = await card.query_selector("h4.title a")
        if not name_el: continue
        name = (await name_el.inner_text()).strip()
        if not name: continue
        href = await name_el.get_attribute("href") or ""
        product_url = href if href.startswith("http") else (BASE_URL + href if href else None)
        price_els = await card.query_selector_all(".price-info .price")
        price = None
        for el in price_els:
            cls = await el.get_attribute("class") or ""
            if "old" not in cls:
                raw = (await el.inner_text()).strip()
                price = clean_price(raw)
                break
        card_cls = await card.get_attribute("class") or ""
        oos_el = await card.query_selector("[class*='out-of-stock'],[class*='outofstock'],[class*='sold-out'],[class*='stock-out']")
        card_text = (await card.inner_text()).lower()
        in_stock = (
            "out-of-stock" not in card_cls and oos_el is None
            and "out of stock" not in card_text and "stock out" not in card_text
            and price is not None
        )
        products.append({{"name": name, "price_bdt": price, "in_stock": in_stock,
            "product_url": product_url, "inline_specs": {{}},
            "source": "PotakaIT", "scraped_at": scraped_at}})
    return products

async def main(save: bool = False):
    all_products = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={{"width": 1280, "height": 900}})
        page = await context.new_page()
        page_num = 1
        while True:
            url = START_URL if page_num == 1 else f"{{START_URL}}?page={{page_num}}"
            print(f"Scraping page {{page_num}}: {{url}}")
            products = await scrape_page(page, url)
            print(f"  Found {{len(products)}} products.")
            if not products: break
            all_products.extend(products)
            page_num += 1
            time.sleep(PAGE_DELAY)
        await browser.close()
    if save:
        out_dir = Path("data/raw"); out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"potakait_{slug}_{{ts}}.json"
        with open(out_path, "w", encoding="utf-8") as f: json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")
    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--save", action="store_true")
    asyncio.run(main(save=parser.parse_args().save))
'''

TEMPLATES = {
    "ucc": UCC_TEMPLATE,
    "ultratech": ULTRATECH_TEMPLATE,
    "binarylogic": BINARYLOGIC_TEMPLATE,
    "potakait": POTAKAIT_TEMPLATE,
}

scrapers = [
    # (retailer, filename,                  cat_display,     slug,           url_path)
    ("ucc",         "scrape_laptop_ram.py",    "Laptop RAM",    "laptop_ram",    "/laptop-ram"),
    ("ucc",         "scrape_portable_hdd.py",  "Portable HDD",  "portable_hdd",  "/portable-hdd"),
    ("ucc",         "scrape_portable_ssd.py",  "Portable SSD",  "portable_ssd",  "/portable-ssd"),
    ("ultratech",   "scrape_laptop_ram.py",    "Laptop RAM",    "laptop_ram",    "/laptop-ram"),
    ("ultratech",   "scrape_casing_cooler.py", "Casing Cooler", "casing_cooler", "/case-fan"),
    ("ultratech",   "scrape_portable_hdd.py",  "Portable HDD",  "portable_hdd",  "/portable-hdd"),
    ("ultratech",   "scrape_portable_ssd.py",  "Portable SSD",  "portable_ssd",  "/portable-ssd"),
    ("binarylogic", "scrape_laptop_ram.py",    "Laptop RAM",    "laptop_ram",    "/laptop-ram"),
    ("binarylogic", "scrape_casing_cooler.py", "Casing Cooler", "casing_cooler", "/case-fan"),
    ("potakait",    "scrape_laptop_ram.py",    "Laptop RAM",    "laptop_ram",    "/laptop-ram"),
    ("potakait",    "scrape_casing_cooler.py", "Casing Cooler", "casing_cooler", "/casing-fan"),
    ("potakait",    "scrape_portable_ssd.py",  "Portable SSD",  "portable_ssd",  "/portable-ssd"),
]

for retailer, fname, cat, slug, url_path in scrapers:
    tmpl = TEMPLATES[retailer]
    content = tmpl.format(cat=cat, slug=slug, url_path=url_path)
    # Fix the slug reference in the f-string inside the template
    content = content.replace(f"ucc_{slug}_", f"ucc_{slug}_").replace(
        f"ultratech_{slug}_", f"ultratech_{slug}_").replace(
        f"binarylogic_{slug}_", f"binarylogic_{slug}_").replace(
        f"potakait_{slug}_", f"potakait_{slug}_")
    out = Path(f"scrapers/{retailer}/{fname}")
    out.write_text(content, encoding="utf-8")
    print(f"Created: {out}")

print("Done")
