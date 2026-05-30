"""
Visit one product page per category per retailer using Playwright,
extract the full spec table, and print a comprehensive spec audit.
"""
import asyncio
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# One representative product URL per category per retailer
SAMPLES = {
    "StarTech": {
        "RAM Desktop":   "https://www.startech.com.bd/ocpc-vs-8gb-ddr3-ram",
        "GPU":           "https://www.startech.com.bd/afox-gt-240-1gb-graphics-card",
        "Processor":     "https://www.startech.com.bd/amd-ryzen-3-2200g-processor",
        "Motherboard":   "https://www.startech.com.bd/colorful-battle-ax-b450m-t-m-2-v14-motherboard",
        "HDD":           "https://www.startech.com.bd/seagate-barracuda-2tb-7200rpm-hdd",
        "PSU":           "https://www.startech.com.bd/t-wolf-atx-350w-power-supply-with-cable",
        "CPU Cooler":    "https://www.startech.com.bd/deepcool-ck-11509-cpu-cooler",
        "Casing":        "https://www.startech.com.bd/antec-st10m-casing",
    },
    "Ryans": {
        "RAM Desktop":   "https://www.ryans.com/twinmos-4gb-ddr3-desktop-ram",
        "GPU":           "https://www.ryans.com/afox-geforce-gt-240-1gb-graphics-card",
        "Processor":     "https://www.ryans.com/amd-ryzen-3-2200g-processor",
        "Motherboard":   "https://www.ryans.com/afox-ih81d3-ma2-v2-motherboard",
        "PSU":           "https://www.ryans.com/value-top-s200i-real-200w-power-supply",
        "CPU Cooler":    "https://www.ryans.com/deepcool-ck-11509-air-cpu-cooler-dp-icap-11509",
        "Casing":        "https://www.ryans.com/antec-nx200-m-mid-tower-gaming-casing",
    },
    "Techland": {
        "RAM Desktop":   "https://www.techlandbd.com/biostar-ddr4-storming-v-desktop-ram",
        "GPU":           "https://www.techlandbd.com/msi-world-of-warcraft-midnight-void-edition-oc-gpu",
        "Processor":     "https://www.techlandbd.com/intel-core-i5-10500-10th-gen-processor",
        "Motherboard":   "https://www.techlandbd.com/asus-prime-b850m-f-csm-matx-amd-am5-motherboard",
        "HDD":           "https://www.techlandbd.com/toshiba-canvio-gaming-x2-hard-disk-drive-black",
        "PSU":           "https://www.techlandbd.com/lian-li-edge-850w-wh-power-supply",
        "CPU Cooler":    "https://www.techlandbd.com/deepcool-lt360-vision-argb-liquid-cpu-cooler",
        "Casing":        "https://www.techlandbd.com/corsair-icue-link-rx140-max-rgb-case-fan",
    },
}

_STEALTH = """\
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
window.chrome={runtime:{}};
"""

async def get_specs_startech(page, url: str) -> dict:
    """Extract spec table rows from StarTech product detail page."""
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".product-info-block, .specification, table", timeout=15000)
    except PWTimeout:
        pass
    await page.wait_for_timeout(2000)

    specs = {}

    # StarTech spec table: <table class="data-table"> or .specification table
    rows = await page.query_selector_all("table.data-table tr, .specification table tr, .tab-content table tr")
    for row in rows:
        cells = await row.query_selector_all("td, th")
        if len(cells) >= 2:
            key = (await cells[0].inner_text()).strip().rstrip(":")
            val = (await cells[1].inner_text()).strip()
            if key and val and key.lower() not in ("specification", ""):
                specs[key] = val

    # Also try definition list style
    if not specs:
        dts = await page.query_selector_all(".spec-table dt, .product-spec dt")
        dds = await page.query_selector_all(".spec-table dd, .product-spec dd")
        for dt, dd in zip(dts, dds):
            key = (await dt.inner_text()).strip()
            val = (await dd.inner_text()).strip()
            if key and val:
                specs[key] = val

    # Try the short-spec block (inline badge specs on listing card)
    if not specs:
        items = await page.query_selector_all(".p-item-detail li, .product-info li")
        for item in items:
            text = (await item.inner_text()).strip()
            if ":" in text:
                k, _, v = text.partition(":")
                specs[k.strip()] = v.strip()

    # Get product name & price
    name_el = await page.query_selector("h1, .product-name h1")
    name = (await name_el.inner_text()).strip() if name_el else url.split("/")[-1]

    price_el = await page.query_selector(".product-price .price-new, .price")
    price = (await price_el.inner_text()).strip() if price_el else "N/A"

    return {"name": name, "price": price, "specs": specs}


async def get_specs_ryans(page, url: str) -> dict:
    """Extract spec table from Ryans product detail page."""
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".product-name, h1", timeout=15000)
    except PWTimeout:
        pass
    await page.wait_for_timeout(2000)

    specs = {}
    rows = await page.query_selector_all("table tr, .specification tr, .product-spec tr")
    for row in rows:
        cells = await row.query_selector_all("td, th")
        if len(cells) >= 2:
            key = (await cells[0].inner_text()).strip().rstrip(":")
            val = (await cells[1].inner_text()).strip()
            if key and val and len(key) < 60:
                specs[key] = val

    name_el = await page.query_selector("h1, .product-name")
    name = (await name_el.inner_text()).strip() if name_el else url.split("/")[-1]
    price_el = await page.query_selector(".product-price, .regular-price")
    price = (await price_el.inner_text()).strip() if price_el else "N/A"
    return {"name": name, "price": price, "specs": specs}


async def get_specs_techland(page, url: str) -> dict:
    """Extract spec table from Techland product detail page."""
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector("h1, .product-title", timeout=15000)
    except PWTimeout:
        pass
    await page.wait_for_timeout(2000)

    specs = {}
    rows = await page.query_selector_all("table tr, .specifications tr, dl dt")
    for row in rows:
        cells = await row.query_selector_all("td, th")
        if len(cells) >= 2:
            key = (await cells[0].inner_text()).strip().rstrip(":")
            val = (await cells[1].inner_text()).strip()
            if key and val and len(key) < 60:
                specs[key] = val

    # Definition list
    dts = await page.query_selector_all("dl dt")
    dds = await page.query_selector_all("dl dd")
    for dt, dd in zip(dts, dds):
        key = (await dt.inner_text()).strip()
        val = (await dd.inner_text()).strip()
        if key and val:
            specs[key] = val

    name_el = await page.query_selector("h1")
    name = (await name_el.inner_text()).strip() if name_el else url.split("/")[-1]
    return {"name": name, "price": "N/A", "specs": specs}


async def probe_retailer(browser, retailer: str, category: str, url: str) -> dict:
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    await ctx.add_init_script(_STEALTH)
    page = await ctx.new_page()

    try:
        if retailer == "StarTech":
            result = await get_specs_startech(page, url)
        elif retailer == "Ryans":
            result = await get_specs_ryans(page, url)
        else:
            result = await get_specs_techland(page, url)
    except Exception as e:
        result = {"name": url, "price": "ERR", "specs": {}, "error": str(e)}
    finally:
        await ctx.close()

    return result


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        all_results = {}
        for retailer, categories in SAMPLES.items():
            print(f"\n{'='*70}")
            print(f"  {retailer}")
            print(f"{'='*70}")
            all_results[retailer] = {}

            for category, url in categories.items():
                print(f"\n  [{category}] → {url}")
                result = await probe_retailer(browser, retailer, category, url)
                all_results[retailer][category] = result

                name = result.get("name", "")[:70]
                specs = result.get("specs", {})
                print(f"  Product : {name}")
                print(f"  Specs found: {len(specs)}")
                for k, v in list(specs.items())[:25]:
                    print(f"    {k:<35} {v[:60]}")
                if not specs:
                    print("  *** NO SPECS FOUND ***")

                await asyncio.sleep(1.5)

        await browser.close()

    # Cross-retailer spec key union per category
    print(f"\n\n{'='*70}")
    print("  SPEC KEY AUDIT — all keys seen per category across retailers")
    print(f"{'='*70}")

    categories = list(next(iter(SAMPLES.values())).keys())
    for cat in categories:
        all_keys = set()
        for retailer in SAMPLES:
            r = all_results.get(retailer, {}).get(cat, {})
            all_keys.update(r.get("specs", {}).keys())
        print(f"\n  {cat} ({len(all_keys)} unique spec keys):")
        for k in sorted(all_keys):
            print(f"    • {k}")


if __name__ == "__main__":
    asyncio.run(main())
