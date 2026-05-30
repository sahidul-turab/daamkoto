"""
Deep probe: fix Techland spec selectors + check Ryans attributes_list + StarTech new categories.
"""
import asyncio, io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

_STEALTH = """\
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
window.chrome={runtime:{}};
"""

async def new_ctx(browser):
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    await ctx.add_init_script(_STEALTH)
    return ctx

# ─── Techland — find the real spec selector ───────────────────────────────

TECHLAND_SAMPLES = {
    "RAM Desktop":  "https://www.techlandbd.com/biostar-ddr4-storming-v-desktop-ram",
    "GPU":          "https://www.techlandbd.com/msi-world-of-warcraft-midnight-void-edition-oc-gpu",
    "CPU Cooler":   "https://www.techlandbd.com/deepcool-lt360-vision-argb-liquid-cpu-cooler",
    "PSU":          "https://www.techlandbd.com/lian-li-edge-850w-wh-power-supply",
    "HDD":          "https://www.techlandbd.com/toshiba-canvio-gaming-x2-hard-disk-drive-black",
    "Motherboard":  "https://www.techlandbd.com/asus-prime-b850m-f-csm-matx-amd-am5-motherboard",
}

async def probe_techland_selectors(page, url: str) -> dict:
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # Dump first 400 chars of page body to see structure
    body_snippet = await page.evaluate("() => document.body.innerText.slice(0, 800)")

    # Try various selector strategies
    results = {}

    # Strategy 1: All <tr> rows, pick cells where 2nd cell has no child style tags
    rows = await page.query_selector_all("tr")
    strat1 = {}
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 2:
            key = (await cells[0].inner_text()).strip()
            # Get textContent directly (excludes style blocks)
            val = await cells[1].evaluate("el => [...el.childNodes].filter(n=>n.nodeType===3||n.nodeName!=='STYLE').map(n=>n.textContent).join(' ').trim()")
            if key and val and len(key) < 60 and len(val) > 0 and "fon" not in val[:10]:
                strat1[key] = val[:80]
    results["strat1_tr_textNode"] = strat1

    # Strategy 2: Look for spec-specific divs with data attributes
    spec_els = await page.query_selector_all("[class*='spec'] td, [class*='Spec'] td, [id*='spec'] td")
    strat2 = {}
    for i in range(0, len(spec_els)-1, 2):
        k = (await spec_els[i].inner_text()).strip()
        v = (await spec_els[i+1].inner_text()).strip()
        if k and v and "fon" not in v[:5]:
            strat2[k] = v[:80]
    results["strat2_spec_class"] = strat2

    # Strategy 3: Look for dl/dt/dd pattern
    dts = await page.query_selector_all("dt")
    dds = await page.query_selector_all("dd")
    strat3 = {}
    for dt, dd in zip(dts, dds):
        k = (await dt.inner_text()).strip()
        v = (await dd.inner_text()).strip()
        if k and v:
            strat3[k] = v[:80]
    results["strat3_dl"] = strat3

    # Strategy 4: Evaluate JavaScript to extract specs from the page's React/Next state
    spec_json = await page.evaluate("""() => {
        // Try Next.js __NEXT_DATA__
        const nd = document.getElementById('__NEXT_DATA__');
        if (nd) {
            try {
                const d = JSON.parse(nd.textContent);
                return JSON.stringify(d).slice(0, 3000);
            } catch(e) {}
        }
        return null;
    }""")
    results["next_data_snippet"] = spec_json[:500] if spec_json else None

    # Strategy 5: Get all visible text in cells without style content
    clean_rows = await page.evaluate("""() => {
        const rows = [...document.querySelectorAll('tr')];
        return rows.map(r => {
            const cells = [...r.querySelectorAll('td')];
            return cells.map(td => {
                // Clone and remove style/script tags
                const clone = td.cloneNode(true);
                clone.querySelectorAll('style,script').forEach(el=>el.remove());
                return clone.innerText.trim();
            });
        }).filter(r => r.length >= 2 && r[0] && r[1] && !r[1].includes('fon'));
    }""")
    strat5 = {}
    for row in clean_rows[:30]:
        if len(row) >= 2 and len(row[0]) < 60:
            strat5[row[0]] = row[1][:80]
    results["strat5_clean_clone"] = strat5

    results["body_snippet"] = body_snippet[:400]
    return results


# ─── Ryans — check attributes_list content ────────────────────────────────

RYANS_SAMPLES = {
    "RAM":       "https://www.ryans.com/category/desktop-component-desktop-ram",
    "GPU":       "https://www.ryans.com/category/desktop-component-graphics-card",
    "Processor": "https://www.ryans.com/category/desktop-component-processor",
}

async def probe_ryans_attrs(page, url: str) -> dict:
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".category-single-product", timeout=20000)
    except PWTimeout:
        return {}
    await page.wait_for_timeout(1000)

    # Get first product's data-item JSON
    btn = await page.query_selector(".product-preview-btn")
    if not btn:
        return {}
    raw = await btn.get_attribute("data-item")
    if not raw:
        return {}
    try:
        item = json.loads(raw)
    except Exception:
        return {}

    # Parse attributes_list
    attrs_raw = item.get("attributes_list", "")
    attrs = {}
    if attrs_raw:
        try:
            parsed = json.loads(attrs_raw)
            attrs = parsed.get("data", {})
        except Exception:
            pass

    return {
        "product_name": item.get("product_name", ""),
        "attributes_list_keys": list(attrs.keys()),
        "attributes_sample": {k: str(v)[:80] for k, v in list(attrs.items())[:15]},
        "all_item_keys": list(item.keys()),
    }


# ─── StarTech new category URLs ───────────────────────────────────────────

STARTECH_NEW = {
    "SSD":          "https://www.startech.com.bd/component/ssd",
    "Laptop RAM":   "https://www.startech.com.bd/laptop-components/laptop-ram",
    "Casing Cooler":"https://www.startech.com.bd/component/casing-fan",
    "Portable HDD": "https://www.startech.com.bd/component/portable-hdd",
    "Portable SSD": "https://www.startech.com.bd/component/portable-ssd",
}

async def check_startech_category(page, url: str) -> str:
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(".p-item", timeout=10000)
        count = len(await page.query_selector_all(".p-item"))
        # Get first product URL
        first = await page.query_selector(".p-item a")
        href = await first.get_attribute("href") if first else ""
        return f"OK — {count} items, first: {href}"
    except PWTimeout:
        title = await page.title()
        return f"TIMEOUT/NO CARDS — page title: {title}"


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # ── 1. Techland spec selectors ─────────────────────────────────
        print("\n" + "="*70)
        print("  TECHLAND SPEC SELECTOR PROBE")
        print("="*70)

        for cat, url in TECHLAND_SAMPLES.items():
            print(f"\n[{cat}] {url}")
            ctx = await new_ctx(browser)
            page = await ctx.new_page()
            res = await probe_techland_selectors(page, url)
            await ctx.close()

            print(f"  Body snippet: {res.get('body_snippet','')[:200]}")
            for strat in ["strat5_clean_clone", "strat1_tr_textNode", "strat3_dl"]:
                d = res.get(strat, {})
                if d:
                    print(f"\n  [{strat}] → {len(d)} specs:")
                    for k, v in list(d.items())[:12]:
                        print(f"    {k:<35} {v}")
                    break
            else:
                print("  *** No strategy found specs ***")
            nd = res.get("next_data_snippet")
            if nd:
                print(f"\n  __NEXT_DATA__ found: {nd[:200]}")
            await asyncio.sleep(1)

        # ── 2. Ryans attributes_list ───────────────────────────────────
        print("\n\n" + "="*70)
        print("  RYANS ATTRIBUTES_LIST PROBE")
        print("="*70)

        for cat, url in RYANS_SAMPLES.items():
            print(f"\n[{cat}] {url}")
            ctx = await new_ctx(browser)
            page = await ctx.new_page()
            res = await probe_ryans_attrs(page, url)
            await ctx.close()

            if res:
                print(f"  Product: {res.get('product_name','')[:60]}")
                print(f"  All item keys: {res.get('all_item_keys')}")
                print(f"  Attributes keys: {res.get('attributes_list_keys')}")
                print(f"  Attributes sample:")
                for k, v in res.get("attributes_sample", {}).items():
                    print(f"    {k:<35} {v}")
            else:
                print("  *** No data found ***")
            await asyncio.sleep(2)

        # ── 3. StarTech new category URLs ──────────────────────────────
        print("\n\n" + "="*70)
        print("  STARTECH NEW CATEGORY URL CHECK")
        print("="*70)

        for cat, url in STARTECH_NEW.items():
            ctx = await new_ctx(browser)
            page = await ctx.new_page()
            result = await check_startech_category(page, url)
            await ctx.close()
            print(f"  {cat:<18} {url}")
            print(f"    → {result}")
            await asyncio.sleep(1)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
