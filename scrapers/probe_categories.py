"""
Probe which category URL slugs return products on a given site.
Usage: python scrapers/probe_categories.py --site skyland
"""
import argparse
import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

SITES = {
    "skyland":       "https://www.skyland.com.bd",
    "creatus":       "https://www.creatus.com.bd",
    "computersource":"https://computersource.com.bd",
    "trusttech":     "https://www.trusttechbd.com",
}

# (slug, category_name, selector)
# selector = CSS selector that indicates products are present
CANDIDATES = [
    ("desktop-ram",    "RAM Desktop",    ".product-thumb"),
    ("ram",            "RAM Desktop",    ".product-thumb"),
    ("laptop-ram",     "RAM Laptop",     ".product-thumb"),
    ("graphics-card",  "GPU",            ".product-thumb"),
    ("processor",      "Processor",      ".product-thumb"),
    ("motherboard",    "Motherboard",    ".product-thumb"),
    ("ssd",            "SSD",            ".product-thumb"),
    ("portable-ssd",   "Portable SSD",   ".product-thumb"),
    ("hdd",            "HDD",            ".product-thumb"),
    ("portable-hdd",   "Portable HDD",   ".product-thumb"),
    ("power-supply",   "PSU",            ".product-thumb"),
    ("cpu-cooler",     "CPU Cooler",     ".product-thumb"),
    ("case-fan",       "Casing Cooler",  ".product-thumb"),
    ("casing",         "Casing",         ".product-thumb"),
    # TrustTech uses /categories/ prefix
    ("categories/ram",            "RAM Desktop",   ".product-card"),
    ("categories/laptop-ram",     "RAM Laptop",    ".product-card"),
    ("categories/graphics-card",  "GPU",           ".product-card"),
    ("categories/processor",      "Processor",     ".product-card"),
    ("categories/motherboard",    "Motherboard",   ".product-card"),
    ("categories/ssd",            "SSD",           ".product-card"),
    ("categories/portable-ssd",   "Portable SSD",  ".product-card"),
    ("categories/hdd",            "HDD",           ".product-card"),
    ("categories/portable-hdd",   "Portable HDD",  ".product-card"),
    ("categories/power-supply",   "PSU",           ".product-card"),
    ("categories/cpu-cooler",     "CPU Cooler",    ".product-card"),
    ("categories/case-fan",       "Casing Cooler", ".product-card"),
    ("categories/casing",         "Casing",        ".product-card"),
    # ComputerSource uses /category prefix
    ("ram",           "RAM Desktop",   ".product"),
    ("processor",     "Processor",     ".product"),
    ("motherboard",   "Motherboard",   ".product"),
    ("ssd",           "SSD",           ".product"),
    ("hdd",           "HDD",           ".product"),
    ("power-supply",  "PSU",           ".product"),
    ("cpu-cooler",    "CPU Cooler",    ".product"),
    ("casing",        "Casing",        ".product"),
]


async def probe(base_url: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        seen_slugs = set()
        for slug, label, selector in CANDIDATES:
            if slug in seen_slugs:
                continue
            url = f"{base_url}/{slug}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                els = await page.query_selector_all(selector)
                count = len(els)
                if count > 0:
                    print(f"  FOUND  {count:3d} items  {label:<16}  {url}")
                    seen_slugs.add(slug)
                else:
                    print(f"  empty          {label:<16}  {url}")
            except PlaywrightTimeout:
                print(f"  TIMEOUT        {label:<16}  {url}")
            except Exception as e:
                print(f"  ERROR          {label:<16}  {url}  ({e})")
        await browser.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=list(SITES.keys()), required=True)
    args = parser.parse_args()
    base = SITES[args.site]
    print(f"\nProbing {args.site} ({base})\n")
    await probe(base)

if __name__ == "__main__":
    asyncio.run(main())
