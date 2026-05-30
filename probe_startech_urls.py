"""Find correct StarTech category URLs for missing categories."""
import asyncio, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

CANDIDATES = [
    # SSD
    "https://www.startech.com.bd/component/ssd",
    "https://www.startech.com.bd/component/solid-state-drive",
    "https://www.startech.com.bd/component/solid-state-drive-ssd",
    "https://www.startech.com.bd/storage/ssd",
    "https://www.startech.com.bd/storage/solid-state-drive",
    # Laptop RAM
    "https://www.startech.com.bd/laptop-components/laptop-ram",
    "https://www.startech.com.bd/laptop-components/ram",
    "https://www.startech.com.bd/laptop/laptop-component/ram",
    "https://www.startech.com.bd/laptop-component/laptop-ram",
    # Casing Fan
    "https://www.startech.com.bd/component/casing-fan",
    "https://www.startech.com.bd/component/case-fan",
    "https://www.startech.com.bd/component/casing-cooler",
    "https://www.startech.com.bd/component/fan",
    "https://www.startech.com.bd/component/pc-fan",
    "https://www.startech.com.bd/component/cooling-fan",
    # Portable HDD
    "https://www.startech.com.bd/component/portable-hdd",
    "https://www.startech.com.bd/storage/portable-hdd",
    "https://www.startech.com.bd/component/external-hdd",
    "https://www.startech.com.bd/storage/external-hard-drive",
    "https://www.startech.com.bd/storage/portable-hard-disk",
    # Portable SSD
    "https://www.startech.com.bd/component/portable-ssd",
    "https://www.startech.com.bd/storage/portable-ssd",
    "https://www.startech.com.bd/storage/external-ssd",
    "https://www.startech.com.bd/component/external-ssd",
]

_STEALTH = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"

async def check(browser, url):
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width":1280,"height":900},
    )
    await ctx.add_init_script(_STEALTH)
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        if "cannot be found" in title.lower() or "404" in title:
            await ctx.close()
            return "404"
        try:
            await page.wait_for_selector(".p-item", timeout=8000)
            n = len(await page.query_selector_all(".p-item"))
            # Get first product URL
            a = await page.query_selector(".p-item a.p-item-img")
            href = await a.get_attribute("href") if a else ""
            await ctx.close()
            return f"OK {n} products | first: {href}"
        except PWTimeout:
            await ctx.close()
            return f"NO CARDS | title: {title}"
    except Exception as e:
        await ctx.close()
        return f"ERR: {e}"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        for url in CANDIDATES:
            result = await check(browser, url)
            status = "OK " if result.startswith("OK") else "   "
            print(f"  {status}{url}")
            print(f"       {result}")
        await browser.close()

asyncio.run(main())
