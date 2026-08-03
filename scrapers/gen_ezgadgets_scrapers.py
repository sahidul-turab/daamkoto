"""
Generate the EZ Gadgets (ggezgadgets.com) scrapers — WooCommerce / Woodmart theme.

EZ Gadgets is the first WooCommerce shop in the project; every other retailer is
OpenCart or a bespoke theme, so none of the existing generators fit.

Why these scrapers read an API instead of the DOM
-------------------------------------------------
The shop leaves WooCommerce's public Store API open, and it returns the same
catalogue the category pages render — verified field-by-field against all 13
graphics cards, prices identical. Two reasons to prefer it:

  * Politeness. One JSON call returns 100 products. The keyboard category needs
    2 requests instead of 10 full Woodmart page loads with their JS, CSS and
    images. Across all 14 categories that is ~10 cheap requests per sweep in
    place of 38 heavy ones — the same concern that keeps `max-parallel` at 4 in
    the daily workflow.
  * It is WooCommerce's own data rather than the theme's rendered archive, so a
    Woodmart upgrade cannot silently change what we parse.

The DOM scraper is kept as a fallback and runs if the API is unavailable. It
prints a loud warning when that happens: a shop closing the Store API must not
look like a normal run.

Field notes
-----------
  * Prices are integer minor units — "549900" with currency_minor_unit 2 is
    ৳5,499.00. Divide, never parse the display string.
  * Variable products carry `price_range`; `prices.price` is already its low
    end. We store that low "from" price and keep the high end in inline_specs
    so the raw archive stays lossless.
  * `sku` is deliberately NOT mapped to `mpn`. These SKUs are the shop's own
    codes ("EWX75V2"), not manufacturer part numbers, and the matcher treats an
    MPN as an exact-match key — feeding it a proprietary code risks fusing two
    unrelated products.
  * Names arrive HTML-encoded ("27&#8243;", "Keyboard &#038; Mouse") because
    WordPress stores post titles as HTML. 5.6% of this catalogue is affected, so
    they are unescaped on the way in. Scraping the DOM hid this — textContent
    decodes entities — and it matters beyond looks: the name feeds the fuzzy
    matcher and becomes the canonical product name shown in the UI.

Usage:
  python scrapers/gen_ezgadgets_scrapers.py
"""

from pathlib import Path

BASE_URL = "https://ggezgadgets.com"
SOURCE = "EZGadgets"

# (category slug used by the pipeline, site category slug, human label)
#
# Every entry was confirmed against the live site: the category page renders
# products and the Store API reports a non-zero count for the same slug. EZ
# Gadgets is a peripherals-led shop, so core-component categories are thin
# (motherboard has one product) while keyboard and mouse run to 199 and 169.
# The ten categories we cover elsewhere but not here — laptop_ram, hdd,
# portable_ssd, portable_hdd, casing, casing_cooler, ups, webcam, gaming_chair,
# printer — have no listing on this site at all.
#
# Site slugs are resolved to numeric category ids at run time rather than
# hardcoded: the ids are opaque WordPress term ids and change if a category is
# ever recreated, whereas the slug is what appears in the public URL.
CATEGORIES = [
    ("ram",         "ram",           "RAM Desktop"),
    ("gpu",         "graphics-card", "GPU"),
    ("processor",   "processor",     "Processor"),
    ("motherboard", "motherboard",   "Motherboard"),
    ("psu",         "power-supply",  "PSU"),
    ("ssd",         "ssd",           "SSD"),
    ("cooler",      "cpu-coller",    "CPU Cooler"),   # sic — the shop's spelling
    ("monitor",     "monitor",       "Monitor"),
    ("keyboard",    "keyboard",      "Keyboard"),
    ("mouse",       "gaming-mouse",  "Mouse"),
    ("headset",     "headset",       "Headset"),
    ("speaker",     "speaker",       "Speaker"),
    ("mousepad",    "mousepad",      "Mouse Pad"),
    ("gamepad",     "gamepad",       "Gamepad"),
]

# Archive paths for the DOM fallback only.
FALLBACK_PATHS = {
    "ram":         "product-category/pc-components/ram",
    "gpu":         "product-category/pc-components/graphics-card",
    "processor":   "product-category/pc-components/processor",
    "motherboard": "product-category/pc-components/motherboard",
    "psu":         "product-category/pc-components/power-supply",
    "ssd":         "product-category/pc-components/storage-pc-components/ssd",
    "cooler":      "product-category/cpu-coller",
    "monitor":     "product-category/monitor",
    "keyboard":    "product-category/peripherals/keyboard",
    "mouse":       "product-category/peripherals/gaming-mouse",
    "headset":     "product-category/peripherals/headset",
    "speaker":     "product-category/peripherals/speaker",
    "mousepad":    "product-category/mousepad",
    "gamepad":     "product-category/gamepad",
}


TEMPLATE = '''\
"""
EZ Gadgets {cat_label} scraper — WooCommerce Store API, with a DOM fallback.

Primary path : /wp-json/wc/store/v1/products?category=<id>&per_page=100
Fallback path: the Woodmart category archive, cards at `.wd-product`

Generated by scrapers/gen_ezgadgets_scrapers.py — edit the generator, not this.

Usage:
  python scrapers/ezgadgets/scrape_{cat_name}.py           # print only
  python scrapers/ezgadgets/scrape_{cat_name}.py --save    # save JSON to data/raw/
  python scrapers/ezgadgets/scrape_{cat_name}.py --dom     # force the fallback
"""

import argparse
import asyncio
import html
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL      = "{base_url}"
CATEGORY_SLUG = "{site_slug}"
ARCHIVE_URL   = f"{{BASE_URL}}/{fallback_path}/"

# Cloudflare fronts this shop. It served us plain 200s throughout development,
# but the requests still go through a real browser context so that any cookie or
# challenge it does set is carried automatically — the same reason the Ryans
# scraper uses Playwright rather than `requests`.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

PAGE_DELAY = 2.5    # seconds between requests — polite crawling
PER_PAGE   = 100    # Store API maximum
MAX_PAGES  = 60     # backstop against a paginator that never terminates


# ---------------------------------------------------------------------------
# Store API (primary)
# ---------------------------------------------------------------------------

async def resolve_category_id(ctx, slug: str) -> int | None:
    """Map a category slug to its WordPress term id."""
    page_num = 1
    while page_num <= 10:
        r = await ctx.request.get(
            f"{{BASE_URL}}/wp-json/wc/store/v1/products/categories"
            f"?per_page=100&page={{page_num}}"
        )
        if r.status != 200:
            return None
        rows = await r.json()
        if not rows:
            return None
        for row in rows:
            if row.get("slug") == slug:
                return row["id"]
        if len(rows) < 100:
            return None
        page_num += 1
        await asyncio.sleep(PAGE_DELAY)
    return None


def money(minor: str | int | None, minor_unit: int) -> float | None:
    """Store API prices are integer minor units: "549900" @ unit 2 -> 5499.00."""
    if minor is None or minor == "":
        return None
    try:
        val = int(minor) / (10 ** minor_unit)
    except (TypeError, ValueError):
        return None
    return val or None


def from_api(p: dict, scraped_at: str) -> dict | None:
    # WordPress stores post titles as HTML, so the API hands back "27&#8243;"
    # and "Keyboard &#038; Mouse". Decode before anything downstream sees it —
    # this name becomes the canonical product name and feeds the fuzzy matcher.
    name = html.unescape(p.get("name") or "").strip()
    if not name:
        return None

    prices = p.get("prices") or {{}}
    unit = prices.get("currency_minor_unit", 2)
    price = money(prices.get("price"), unit)

    inline_specs = {{}}
    rng = prices.get("price_range")
    if rng:
        # Variable product: `price` is already the low end. Record the span so
        # the archive shows this was a "from" price, not a single figure.
        lo = money(rng.get("min_amount"), unit)
        hi = money(rng.get("max_amount"), unit)
        if lo and hi and hi != lo:
            inline_specs["price_from"] = lo
            inline_specs["price_max"] = hi

    in_stock = bool(p.get("is_in_stock")) and price is not None
    images = p.get("images") or []

    return {{
        "image_url": (images[0].get("src") if images else None) or None,
        "name": name,
        "price_bdt": price,
        "in_stock": in_stock,
        "stock_status": "in_stock" if in_stock else "out_of_stock",
        "product_url": p.get("permalink"),
        "inline_specs": inline_specs,
        "source": "{source}",
        "pc_bundle_only": False,
        "scraped_at": scraped_at,
    }}


async def scrape_via_api(ctx) -> list[dict] | None:
    """Return records, or None if the Store API is unusable (caller falls back)."""
    cat_id = await resolve_category_id(ctx, CATEGORY_SLUG)
    if cat_id is None:
        print(f"  [api] could not resolve category slug {{CATEGORY_SLUG!r}}")
        return None
    print(f"  [api] category {{CATEGORY_SLUG!r}} -> id {{cat_id}}")

    products: list[dict] = []
    seen: set[int] = set()
    scraped_at = datetime.now(timezone.utc).isoformat()

    page_num = 1
    while page_num <= MAX_PAGES:
        url = (f"{{BASE_URL}}/wp-json/wc/store/v1/products"
               f"?category={{cat_id}}&per_page={{PER_PAGE}}&page={{page_num}}")
        print(f"Fetching page {{page_num}}: {{url}}")
        r = await ctx.request.get(url)
        if r.status != 200:
            if page_num == 1:
                print(f"  [api] HTTP {{r.status}} on the first page")
                return None
            # A later page failing would silently truncate the category, which
            # looks identical to a shop that shrank. Refuse the partial result.
            print(f"  [api] HTTP {{r.status}} on page {{page_num}} — partial result rejected")
            return None

        rows = await r.json()
        print(f"  Found {{len(rows)}} products.")
        if not rows:
            break

        for row in rows:
            pid = row.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            rec = from_api(row, scraped_at)
            if rec:
                products.append(rec)

        if len(rows) < PER_PAGE:
            break
        page_num += 1
        await asyncio.sleep(PAGE_DELAY)

    return products


# ---------------------------------------------------------------------------
# DOM archive (fallback)
# ---------------------------------------------------------------------------

def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\\d.]", "", raw.strip().split("\\n")[0])
    try:
        val = float(digits) if digits else None
        return val if val else None
    except ValueError:
        return None


# One evaluate() per card instead of a dozen query_selector round trips.
CARD_JS = """el => {{
    const a = el.querySelector('.wd-entities-title a') || el.querySelector('h3 a');
    if (!a) return null;
    const name = a.textContent.trim();
    if (!name) return null;

    const priceEl = el.querySelector('.price');
    const amounts = priceEl
        ? [...priceEl.querySelectorAll('.woocommerce-Price-amount')].map(e => e.textContent.trim())
        : [];
    const insEl = priceEl ? priceEl.querySelector('ins') : null;
    const insAmount = insEl
        ? (insEl.querySelector('.woocommerce-Price-amount') || insEl).textContent.trim()
        : null;

    // Woodmart lazy-loads listing images and, when a product has a gallery,
    // renders slides carrying data-image-url with no <img> at all.
    let image = '';
    for (const img of el.querySelectorAll('img')) {{
        const v = img.getAttribute('data-src') || img.getAttribute('data-lazy')
               || img.getAttribute('src') || '';
        if (!v || v.startsWith('data:') || v.toLowerCase().endsWith('.svg')) continue;
        try {{ image = new URL(v, document.baseURI).href; }} catch (e) {{}}
        if (image) break;
    }}
    if (!image) {{
        const slide = el.querySelector('.wd-product-grid-slide[data-image-url]');
        if (slide) {{
            try {{ image = new URL(slide.getAttribute('data-image-url'), document.baseURI).href; }}
            catch (e) {{}}
        }}
    }}

    const cls = el.className || '';
    return {{
        name,
        product_url: a.href || null,
        amounts,
        ins_amount: insAmount,
        is_variable: cls.includes('product-type-variable'),
        out_of_stock: cls.includes('outofstock'),
        image_url: image || null,
    }};
}}"""


def pick_price(rec: dict) -> tuple[float | None, float | None]:
    """Return (price, price_max). price_max is set only for a variable range.

    Read the amount elements, never `.price` text: the sale markup interleaves
    screen-reader copy ("Original price was: ...") with the numbers.
      plain    -> one amount
      on sale  -> <del> old, <ins> new; take <ins>
      variable -> "low - high"; take low, the "from" price, and keep high
    """
    if rec.get("ins_amount"):
        price = clean_price(rec["ins_amount"])
        if price:
            return price, None

    amounts = [p for p in (clean_price(a) for a in rec.get("amounts") or []) if p]
    if not amounts:
        return None, None
    if rec.get("is_variable") and len(amounts) > 1:
        return min(amounts), max(amounts)
    return amounts[0], None


async def scrape_archive_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    try:
        await page.wait_for_selector(".wd-product", timeout=15_000)
    except PlaywrightTimeout:
        return []

    for y in [400, 900, 1600]:
        await page.evaluate(f"window.scrollTo(0, {{y}})")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(500)

    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in await page.query_selector_all(".wd-product"):
        rec = await card.evaluate(CARD_JS)
        if not rec:
            continue

        price, price_max = pick_price(rec)
        in_stock = (not rec["out_of_stock"]) and price is not None

        inline_specs = {{}}
        if price_max is not None:
            inline_specs["price_from"] = price
            inline_specs["price_max"] = price_max

        products.append({{
            "image_url": rec["image_url"],
            "name": rec["name"],
            "price_bdt": price,
            "in_stock": in_stock,
            "stock_status": "in_stock" if in_stock else "out_of_stock",
            "product_url": rec["product_url"],
            "inline_specs": inline_specs,
            "source": "{source}",
            "pc_bundle_only": False,
            "scraped_at": scraped_at,
        }})

    return products


async def scrape_via_dom(ctx) -> list[dict]:
    page = await ctx.new_page()
    products: list[dict] = []
    seen: set[str] = set()

    page_num = 1
    while page_num <= MAX_PAGES:
        url = ARCHIVE_URL if page_num == 1 else f"{{ARCHIVE_URL}}page/{{page_num}}/"
        print(f"Scraping page {{page_num}}: {{url}}")
        found = await scrape_archive_page(page, url)
        print(f"  Found {{len(found)}} products.")
        if not found:
            print("  No products — reached end.")
            break

        fresh = [p for p in found if p["product_url"] not in seen]
        if not fresh:
            print("  Page repeated earlier results — stopping.")
            break
        seen.update(p["product_url"] for p in fresh)
        products.extend(fresh)

        page_num += 1
        await asyncio.sleep(PAGE_DELAY)

    await page.close()
    return products


# ---------------------------------------------------------------------------

async def main(save: bool = False, force_dom: bool = False):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={{"width": 1400, "height": 1000}},
        )
        # Load a real page first so Cloudflare hands out whatever cookies it
        # wants before we start issuing API calls.
        warmup = await ctx.new_page()
        await warmup.goto(ARCHIVE_URL, wait_until="domcontentloaded", timeout=90_000)
        await warmup.wait_for_timeout(2000)
        await warmup.close()

        all_products = None
        if not force_dom:
            all_products = await scrape_via_api(ctx)

        if all_products is None:
            if not force_dom:
                print("\\n" + "!" * 62)
                print("!! Store API unavailable — falling back to DOM scraping.")
                print("!! If this persists the shop has closed /wp-json; the DOM")
                print("!! path is slower and theme-coupled, so check it still parses.")
                print("!" * 62 + "\\n")
            all_products = await scrape_via_dom(ctx)

        await browser.close()

    if save:
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"ezgadgets_{cat_name}_{{timestamp}}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {{cheapest['name'][:70]}}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape EZ Gadgets {cat_label} listings")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--dom", action="store_true",
                        help="Skip the Store API and scrape the category archive")
    args = parser.parse_args()
    asyncio.run(main(save=args.save, force_dom=args.dom))
'''


def generate() -> None:
    out_dir = Path("scrapers/ezgadgets")
    out_dir.mkdir(parents=True, exist_ok=True)
    for cat_name, site_slug, cat_label in CATEGORIES:
        out_path = out_dir / f"scrape_{cat_name}.py"
        out_path.write_text(
            TEMPLATE.format(
                base_url=BASE_URL,
                site_slug=site_slug,
                fallback_path=FALLBACK_PATHS[cat_name],
                cat_name=cat_name,
                cat_label=cat_label,
                source=SOURCE,
            ),
            encoding="utf-8",
        )
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    generate()
