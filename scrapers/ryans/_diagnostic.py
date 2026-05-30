"""Diagnostic v9 — dump full page source and try longer wait strategies."""
import asyncio, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright
from pathlib import Path

RAM_URL = "https://www.ryans.com/category/desktop-component-desktop-ram"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        # Track all network requests
        requests_log = []
        page.on("request", lambda r: requests_log.append((r.method, r.url)))

        await page.goto("https://www.ryans.com", wait_until="domcontentloaded")
        await page.goto(RAM_URL, wait_until="networkidle", timeout=45_000)

        # Wait even longer
        await page.wait_for_timeout(5000)

        # Scroll through the page slowly
        for y in [300, 600, 900, 1200, 1500]:
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_timeout(500)

        await page.wait_for_timeout(2000)

        # Save full HTML to file
        html = await page.content()
        Path("data").mkdir(exist_ok=True)
        Path("data/_ryans_debug.html").write_text(html, encoding="utf-8")
        print(f"Saved full HTML: {len(html)} chars → data/_ryans_debug.html")

        # Search for product-like patterns in the HTML
        import re
        product_patterns = [
            r'class="[^"]*product[^"]*"',
            r'data-product',
            r'"product_id"',
            r'"item_id"',
            r'৳\s*[\d,]+',
        ]
        for pattern in product_patterns:
            matches = re.findall(pattern, html)
            print(f"\nPattern '{pattern}': {len(matches)} matches")
            for m in matches[:5]:
                print(f"  {m}")

        # Log unique fetch/XHR requests
        print("\n=== Network requests (non-static) ===")
        seen = set()
        for method, url in requests_log:
            if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.woff', '.ico', 'analytics', 'gtm', 'google']):
                continue
            if url not in seen:
                seen.add(url)
                print(f"  {method} {url}")

        await browser.close()

asyncio.run(main())
