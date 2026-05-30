"""Find StarTech SSD, laptop RAM, portable storage URLs via sitemap + nav."""
import asyncio, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

_STEALTH = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"

MORE_CANDIDATES = [
    # SSD variations
    "https://www.startech.com.bd/component/ssd-solid-state-drive",
    "https://www.startech.com.bd/component/nvme-ssd",
    "https://www.startech.com.bd/component/m2-ssd",
    "https://www.startech.com.bd/laptop-components/ssd",
    "https://www.startech.com.bd/laptop-components/solid-state-drive",
    "https://www.startech.com.bd/laptop-components/laptop-ssd",
    # Laptop RAM
    "https://www.startech.com.bd/laptop-components/so-dimm-ram",
    "https://www.startech.com.bd/laptop-components/sodimm",
    "https://www.startech.com.bd/laptop/memory",
    "https://www.startech.com.bd/laptop/ram",
    # Portable
    "https://www.startech.com.bd/storage/external-hard-disk",
    "https://www.startech.com.bd/storage/external-ssd",
    "https://www.startech.com.bd/storage",
    "https://www.startech.com.bd/laptop-components/external-storage",
]

async def check(browser, url):
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        viewport={"width":1280,"height":900},
    )
    await ctx.add_init_script(_STEALTH)
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        if "cannot be found" in title.lower() or "404" in title:
            await ctx.close(); return "404"
        try:
            await page.wait_for_selector(".p-item", timeout=8000)
            n = len(await page.query_selector_all(".p-item"))
            await ctx.close()
            return f"OK {n} products"
        except PWTimeout:
            await ctx.close()
            return f"EXISTS (no .p-item) | title: {title[:60]}"
    except Exception as e:
        await ctx.close(); return f"ERR: {e}"

async def check_nav(browser):
    """Extract category links from StarTech navigation."""
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        viewport={"width":1280,"height":900},
    )
    await ctx.add_init_script(_STEALTH)
    page = await ctx.new_page()
    await page.goto("https://www.startech.com.bd", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    # Get all nav links
    links = await page.evaluate("""() => {
        return [...document.querySelectorAll('a[href]')]
            .map(a => a.href)
            .filter(h => h.includes('startech.com.bd/') && !h.endsWith('startech.com.bd/'))
            .filter(h => !h.includes('#') && !h.includes('?'))
    }""")
    await ctx.close()
    # Filter for storage/laptop/component paths, deduplicate
    seen = set()
    storage_links = []
    for l in links:
        path = l.replace("https://www.startech.com.bd","")
        if path in seen: continue
        seen.add(path)
        if any(kw in path.lower() for kw in ['ssd','storage','portable','laptop','ram','memory','external']):
            storage_links.append(path)
    return sorted(storage_links)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])

        print("=== StarTech navigation links containing ssd/storage/laptop/ram ===")
        nav_links = await check_nav(browser)
        for l in nav_links:
            print(f"  {l}")

        print("\n=== Additional URL candidates ===")
        for url in MORE_CANDIDATES:
            result = await check(browser, url)
            mark = "OK " if result.startswith("OK") else "   "
            print(f"  {mark}{url}")
            print(f"       → {result}")

        await browser.close()

asyncio.run(main())
