"""
Second probe — alternative slugs for categories that returned 0 in probe_urls.py.
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Each entry: (retailer, category, url, selector, stealth)
CANDIDATES2 = [
    # StarTech SSD alternatives
    ("StarTech", "ssd", "https://www.startech.com.bd/component/ssd", ".p-item", False),
    ("StarTech", "ssd", "https://www.startech.com.bd/component/storage-devices", ".p-item", False),
    ("StarTech", "ssd_nvme", "https://www.startech.com.bd/component/nvme-ssd", ".p-item", False),
    ("StarTech", "ssd_sata", "https://www.startech.com.bd/component/sata-ssd", ".p-item", False),
    # StarTech PSU alternatives
    ("StarTech", "psu", "https://www.startech.com.bd/component/power-supply", ".p-item", False),
    ("StarTech", "psu", "https://www.startech.com.bd/component/ups-ips", ".p-item", False),
    # Ryans SSD alternatives
    ("Ryans", "ssd", "https://www.ryans.com/category/desktop-component-ssd", ".category-single-product", True),
    ("Ryans", "ssd", "https://www.ryans.com/category/desktop-component-storage", ".category-single-product", True),
    ("Ryans", "ssd_nvme", "https://www.ryans.com/category/desktop-component-nvme-ssd", ".category-single-product", True),
    # Ryans HDD alternatives
    ("Ryans", "hdd", "https://www.ryans.com/category/desktop-component-hdd", ".category-single-product", True),
    ("Ryans", "hdd", "https://www.ryans.com/category/desktop-component-storage-hard-disk-drive", ".category-single-product", True),
    # Techland SSD alternatives
    ("Techland", "ssd", "https://www.techlandbd.com/pc-components/solid-state-drive", "article.products-list__item", False),
    ("Techland", "ssd", "https://www.techlandbd.com/pc-components/storage", "article.products-list__item", False),
    # Techland HDD alternatives
    ("Techland", "hdd", "https://www.techlandbd.com/pc-components/hard-disk-drive", "article.products-list__item", False),
    # Techland casing alternatives
    ("Techland", "casing", "https://www.techlandbd.com/pc-components/casing-cabinet", "article.products-list__item", False),
    ("Techland", "casing", "https://www.techlandbd.com/pc-components/cabinet", "article.products-list__item", False),
    ("Techland", "casing", "https://www.techlandbd.com/casing", "article.products-list__item", False),
    # UCC alternatives
    ("UCC", "motherboard", "https://www.ucc.com.bd/motherboards", ".product-thumb", False),
    ("UCC", "ssd", "https://www.ucc.com.bd/solid-state-drives", ".product-thumb", False),
    ("UCC", "ssd", "https://www.ucc.com.bd/ssd", ".product-thumb", False),
    ("UCC", "hdd", "https://www.ucc.com.bd/hard-disk-drives", ".product-thumb", False),
    ("UCC", "hdd", "https://www.ucc.com.bd/hdd", ".product-thumb", False),
    ("UCC", "cooler", "https://www.ucc.com.bd/cpu-coolers", ".product-thumb", False),
    ("UCC", "casing", "https://www.ucc.com.bd/casings", ".product-thumb", False),
    ("UCC", "casing", "https://www.ucc.com.bd/pc-casing", ".product-thumb", False),
    # UltraTech HDD alternatives
    ("UltraTech", "hdd", "https://www.ultratech.com.bd/hard-disk-drives", ".product-thumb", False),
    ("UltraTech", "hdd", "https://www.ultratech.com.bd/hdd", ".product-thumb", False),
    # UltraTech PSU alternatives
    ("UltraTech", "psu", "https://www.ultratech.com.bd/power-supply", ".product-thumb", False),
    ("UltraTech", "psu", "https://www.ultratech.com.bd/power-supply-unit", ".product-thumb", False),
    # BinaryLogic alternatives
    ("BinaryLogic", "ssd", "https://www.binarylogic.com.bd/solid-state-drive", ".p-item", False),
    ("BinaryLogic", "hdd", "https://www.binarylogic.com.bd/hard-disk-drive", ".p-item", False),
    ("BinaryLogic", "psu", "https://www.binarylogic.com.bd/power-supply", ".p-item", False),
    ("BinaryLogic", "psu", "https://www.binarylogic.com.bd/power-supply-unit", ".p-item", False),
    ("BinaryLogic", "cooler", "https://www.binarylogic.com.bd/cpu-cooler", ".p-item", False),
    ("BinaryLogic", "casing", "https://www.binarylogic.com.bd/computer-casing", ".p-item", False),
    ("BinaryLogic", "casing", "https://www.binarylogic.com.bd/casing", ".p-item", False),
    # PotakaIT alternatives
    ("PotakaIT", "ssd", "https://www.potakait.com/ssd", ".product-item", False),
    ("PotakaIT", "psu", "https://www.potakait.com/power-supplies", ".product-item", False),
    ("PotakaIT", "psu", "https://www.potakait.com/psus", ".product-item", False),
    ("PotakaIT", "cooler", "https://www.potakait.com/cpu-coolers", ".product-item", False),
    ("PotakaIT", "cooler", "https://www.potakait.com/coolers", ".product-item", False),
    ("PotakaIT", "casing", "https://www.potakait.com/pc-cases", ".product-item", False),
    ("PotakaIT", "casing", "https://www.potakait.com/casings", ".product-item", False),
]

_STEALTH = """\
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}};
"""

async def probe(browser, retailer, cat, url, selector, stealth) -> int:
    try:
        if stealth:
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )
            await ctx.add_init_script(_STEALTH)
        else:
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=18_000)
        try:
            await page.wait_for_selector(selector, timeout=10_000)
            count = len(await page.query_selector_all(selector))
        except PlaywrightTimeout:
            count = 0
        await ctx.close()
        return count
    except Exception:
        return 0

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        for retailer, cat, url, selector, stealth in CANDIDATES2:
            count = await probe(browser, retailer, cat, url, selector, stealth)
            mark = "OK" if count > 0 else "--"
            print(f"  {mark} {retailer:<12} {cat:<15} {count:>3} cards  {url}")
            await asyncio.sleep(1.0)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
