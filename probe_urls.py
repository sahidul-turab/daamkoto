"""
Probe candidate category URLs across all retailers to find which ones return products.
Run once, then use results to configure scrapers.

Usage:  python probe_urls.py
"""

import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

CANDIDATES = {
    "StarTech": {
        "base": "https://www.startech.com.bd/component",
        "slugs": {
            "motherboard":  "motherboard",
            "ssd":          "solid-state-drive",
            "hdd":          "hard-disk-drive",
            "psu":          "power-supply-unit",
            "cooler":       "cpu-cooler",
            "casing":       "casing",
        },
        "selector": ".p-item",
        "stealth": False,
    },
    "Ryans": {
        "base": "https://www.ryans.com/category",
        "slugs": {
            "motherboard":  "desktop-component-motherboard",
            "ssd":          "desktop-component-solid-state-drive",
            "hdd":          "desktop-component-hard-disk-drive",
            "psu":          "desktop-component-power-supply",
            "cooler":       "desktop-component-cpu-cooler",
            "casing":       "desktop-component-casing",
        },
        "selector": ".category-single-product",
        "stealth": True,
    },
    "Techland": {
        "base": "https://www.techlandbd.com/pc-components",
        "slugs": {
            "motherboard":  "motherboard",
            "ssd":          "ssd",
            "hdd":          "hdd",
            "psu":          "power-supply",
            "cooler":       "cpu-cooler",
            "casing":       "casing",
        },
        "selector": "article.products-list__item",
        "stealth": False,
    },
    "UCC": {
        "base": "https://www.ucc.com.bd",
        "slugs": {
            "motherboard":  "motherboard",
            "ssd":          "ssd",
            "hdd":          "hard-disk-drive",
            "psu":          "power-supply-unit",
            "cooler":       "cpu-cooler",
            "casing":       "casing",
        },
        "selector": ".product-thumb",
        "stealth": False,
    },
    "UltraTech": {
        "base": "https://www.ultratech.com.bd",
        "slugs": {
            "motherboard":  "motherboard",
            "ssd":          "ssd",
            "hdd":          "hard-disk-drive",
            "psu":          "power-supply-unit",
            "cooler":       "cpu-cooler",
            "casing":       "casing",
        },
        "selector": ".product-thumb",
        "stealth": False,
    },
    "BinaryLogic": {
        "base": "https://www.binarylogic.com.bd",
        "slugs": {
            "motherboard":  "motherboard",
            "ssd":          "ssd",
            "hdd":          "hard-disk-drive",
            "psu":          "power-supply-unit",
            "cooler":       "cpu-cooler",
            "casing":       "casing",
        },
        "selector": ".p-item",
        "stealth": False,
    },
    "PotakaIT": {
        "base": "https://www.potakait.com",
        "slugs": {
            "motherboard":  "motherboards",
            "ssd":          "ssds",
            "hdd":          "hard-disk-drives",
            "psu":          "power-supplies",
            "cooler":       "cpu-coolers",
            "casing":       "pc-cases",
        },
        "selector": ".product-item",
        "stealth": False,
    },
}

_STEALTH = """\
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}};
"""

RESULTS = {}

async def probe_one(browser, retailer: str, cfg: dict, cat: str, slug: str) -> dict:
    url = f"{cfg['base']}/{slug}"
    try:
        if cfg["stealth"]:
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
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        try:
            await page.wait_for_selector(cfg["selector"], timeout=12_000)
            cards = await page.query_selector_all(cfg["selector"])
            count = len(cards)
        except PlaywrightTimeout:
            count = 0
        final_url = page.url
        await ctx.close()
        return {"url": url, "final_url": final_url, "count": count, "ok": count > 0}
    except Exception as e:
        return {"url": url, "final_url": "", "count": 0, "ok": False, "error": str(e)}


async def main():
    results = {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        for retailer, cfg in CANDIDATES.items():
            results[retailer] = {}
            for cat, slug in cfg["slugs"].items():
                print(f"  Probing {retailer}/{cat} ...", end=" ", flush=True)
                r = await probe_one(browser, retailer, cfg, cat, slug)
                results[retailer][cat] = r
                status = f"OK ({r['count']} cards)" if r["ok"] else f"MISS (0 cards)"
                print(status)
                await asyncio.sleep(1.5)
        await browser.close()

    print("\n" + "="*70)
    print("  RESULTS SUMMARY")
    print("="*70)
    for retailer, cats in results.items():
        print(f"\n  {retailer}")
        for cat, r in cats.items():
            mark = "✓" if r["ok"] else "✗"
            print(f"    {mark} {cat:<15} {r['url']}")

    with open("probe_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved full results -> probe_results.json")


if __name__ == "__main__":
    asyncio.run(main())
