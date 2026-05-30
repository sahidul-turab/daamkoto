"""Quick probe of TrustTech /categories/* URLs."""
import asyncio, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE = "https://www.trusttechbd.com"
SLUGS = [
    ("categories/ram",           "RAM Desktop"),
    ("categories/laptop-ram",    "RAM Laptop"),
    ("categories/graphics-card", "GPU"),
    ("categories/processor",     "Processor"),
    ("categories/motherboard",   "Motherboard"),
    ("categories/ssd",           "SSD"),
    ("categories/portable-ssd",  "Portable SSD"),
    ("categories/hdd",           "HDD"),
    ("categories/portable-hdd",  "Portable HDD"),
    ("categories/power-supply",  "PSU"),
    ("categories/cpu-cooler",    "CPU Cooler"),
    ("categories/case-fan",      "Casing Cooler"),
    ("categories/casing",        "Casing"),
]

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        for slug, label in SLUGS:
            url = f"{BASE}/{slug}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(1500)
                els = await page.query_selector_all(".product-card")
                print(f"  {'FOUND '+str(len(els)):>12}  {label:<16}  {slug}")
            except PlaywrightTimeout:
                print(f"  {'TIMEOUT':>12}  {label:<16}  {slug}")
        await browser.close()

asyncio.run(main())
