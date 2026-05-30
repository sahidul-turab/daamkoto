import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await ctx.new_page()
        print("Loading Skyland homepage...")
        await page.goto("https://www.skyland.com.bd", wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(3000)
        
        links = await page.query_selector_all("a")
        skyland_links = []
        for link in links:
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()
            if href.startswith("https://www.skyland.com.bd"):
                skyland_links.append((text, href))
            elif href.startswith("/"):
                skyland_links.append((text, "https://www.skyland.com.bd" + href))
                
        # Sort and remove duplicates
        skyland_links = sorted(list(set(skyland_links)))
        print(f"Found {len(skyland_links)} links:")
        for text, href in skyland_links:
            # Let's filter by keywords that might indicate HDD, portable HDD, fans
            lower_text = text.lower()
            lower_href = href.lower()
            keywords = ["disk", "hdd", "external", "portable", "fan", "cooler", "casing"]
            if any(k in lower_text or k in lower_href for k in keywords):
                print(f"  {text} -> {href}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
