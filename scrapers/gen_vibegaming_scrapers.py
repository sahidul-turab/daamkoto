"""
Generate Vibe Gaming's scrapers — one file per category.

Vibe Gaming is the first WooCommerce shop in the set (the other thirteen are
OpenCart or bespoke), so it gets its own generator rather than an entry in
gen_category_scrapers.py, which adapts an existing scraper of the same retailer
and has nothing to adapt here. This mirrors gen_opencart_scrapers.py, which owns
Skyland's and Creatus's category paths the same way.

CATEGORY_PATHS below is the single source of truth for which Vibe Gaming listing
feeds which DaamKoto category. Every path was confirmed in a real browser: HTTP
200 with at least five rendered cards.

Two things are worth knowing before editing the mapping.

1. A WooCommerce category archive includes its descendant terms. That is why
   `mouse` and `keyboards` are *not* used: `mouse` also returns the 166 mouse
   pads and 16 mouse accessories filed under it, which would put every mouse pad
   in DaamKoto's MOUSE category as well as MOUSE PAD, and `keyboards` likewise
   returns keycap sets, switches, barebones and wrist rests. Both are mapped to
   the shop's own product-type child terms instead. That trades coverage for
   cleanliness — the child terms miss 86 mice and 77 keyboards that are filed
   only on the parent — which is the trade CLAUDE.md already calls for: "a
   category polluted with consoles is worse than a category with fewer shops."

2. Three categories need two listings because the shop keeps two near-disjoint
   terms for the same thing (a legacy term and a current one). Overlap measured
   at 1/29 for casing coolers, 1/38 for gaming chairs and 129/197 for gamepads,
   so dropping either would lose real products. The generated scraper takes a
   list of listing URLs and de-duplicates by the shop's product id.

Usage:
  python scrapers/gen_vibegaming_scrapers.py            # write missing files
  python scrapers/gen_vibegaming_scrapers.py --force    # overwrite existing
  python scrapers/gen_vibegaming_scrapers.py --dry-run  # preview only
"""

import argparse
import sys
from pathlib import Path

BASE_URL = "https://vibegaming.com.bd"
RETAILER = "vibegaming"
SOURCE   = "VibeGaming"          # display name — must match load.py KNOWN_RETAILERS

SCRAPERS = Path(__file__).resolve().parent

# DaamKoto category -> one or more listing paths on vibegaming.com.bd.
# Counts in the comments are the shop's own result totals at the time of adding.
CATEGORY_PATHS: dict[str, list[str]] = {
    # ── Core components ──────────────────────────────────────────────────────
    # The shop files six M.2 SSDs under Component > RAM — see NAME_EXCLUSIONS.
    "ram":           ["/product-category/component/ram/"],                  # 33
    "gpu":           ["/product-category/component/graphics-card/"],        # 82
    "processor":     ["/product-category/component/processor/"],            # 52
    "motherboard":   ["/product-category/component/motherboard/"],          # 29
    "ssd":           ["/product-category/component/ssd/"],                  # 70
    "hdd":           ["/product-category/component/hard-disk-drive/"],      # 30
    "psu":           ["/product-category/component/power-supply/"],         # 78
    "casing":        ["/product-category/component/casing/"],               # 220
    "cooler":        ["/product-category/cpu-cooler/"],                     # 185
    "casing_cooler": ["/product-category/component/cooling-fans/",          # 21
                      "/product-category/component/case-fan/"],             # 9
    "ups":           ["/product-category/component/offline-ups/"],          # 20

    # ── Peripherals & lifestyle ──────────────────────────────────────────────
    "monitor":       ["/product-category/monitors/"],                       # 500
    "keyboard":      ["/product-category/keyboards/mechanical-keyboards/",  # 833
                      "/product-category/keyboards/wired-keyboard/",        # 766
                      "/product-category/keyboards/gaming-keyboards/",      # 561
                      "/product-category/keyboards/wireless-keyboard/",     # 484
                      "/product-category/keyboards/magnetic-keyboard/"],    # 79
    "mouse":         ["/product-category/mouse/wireless-mouse/",            # 606
                      "/product-category/mouse/wired-mouse/",               # 504
                      "/product-category/mouse/gaming-mouse/",              # 553
                      "/product-category/mouse/professional-mouse/"],       # 66
    "headset":       ["/product-category/headphones/"],                     # 641
    "speaker":       ["/product-category/speakers/"],                       # 200
    "mousepad":      ["/product-category/mouse/mouse-pad/"],                # 165
    "gamepad":       ["/product-category/gaming-peripherals/gamepad/",      # 177
                      "/product-category/general-categorygamepad/"],        # 149
    "gaming_chair":  ["/product-category/gaming-peripherals/gaming-chair/", # 26
                      "/product-category/gaming-chair-2/"],                 # 13
    "webcam":        ["/product-category/webcam/"],                         # 12
    "printer":       ["/product-category/office-equipment/printer/"],       # 87
}

# Vibe Gaming stocks no laptop RAM, portable SSD or portable HDD listing, so
# those three DaamKoto categories get no scraper rather than an empty one.

# category -> regex of product names the shop filed in the wrong category.
#
# This is the one place a scraper here looks at *what* a product is, and it
# exists only because the shop's own taxonomy is wrong: six M.2 SSDs are filed
# under Component > RAM and carry no SSD term at all, so there is no principled
# way to drop them from the term data. Six of 33 rows is a fifth of the
# category, which would be plainly wrong to a user browsing RAM DESKTOP.
#
# Keep these patterns narrow enough that they can only ever match another
# product type — never a spec, brand or model of the category itself. The
# generated scraper prints a line for every row it drops, so a pattern that
# starts over-matching shows up in the run log instead of silently shrinking
# the category.
NAME_EXCLUSIONS: dict[str, str] = {
    "ram": r"\b(ssd|nvme|solid[\s-]state[\s-]drive)\b",
}

CAT_LABELS = {
    "ram": "RAM Desktop", "gpu": "GPU", "processor": "Processor",
    "motherboard": "Motherboard", "ssd": "SSD", "hdd": "HDD", "psu": "PSU",
    "casing": "Casing", "cooler": "CPU Cooler", "casing_cooler": "Casing Cooler",
    "ups": "UPS", "monitor": "Monitor", "keyboard": "Keyboard", "mouse": "Mouse",
    "headset": "Headset", "speaker": "Speaker", "mousepad": "Mouse Pad",
    "gamepad": "Gamepad", "gaming_chair": "Gaming Chair", "webcam": "Webcam",
    "printer": "Printer",
}


TEMPLATE = '''\
"""VibeGaming {cat_label} scraper — WooCommerce.

{listing_doc}

Cards are `section.product[data-product_id]`. Each one carries a hidden
`data-gtm4wp_product_data` JSON blob holding the exact numeric price, stock
status and product link, so the price needs no currency parsing and a sale price
is never confused with the struck-through original. That blob comes from an
analytics plugin, so every field it provides also has a markup fallback — if the
plugin is ever disabled the scraper must degrade to the rendered page, not
quietly report NULL prices.

Pagination is WooCommerce's /page/N/ suffix.

Usage:
  python scrapers/{retailer}/scrape_{cat_name}.py           # print only
  python scrapers/{retailer}/scrape_{cat_name}.py --save    # save JSON to data/raw/
"""

import argparse
import asyncio
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "{base_url}"
START_URLS = [
{start_urls}
]
PAGE_DELAY = 2.5
# Safety valve. The largest listing here is ~35 pages; anything past this means
# pagination stopped terminating.
MAX_PAGES = 100

CARD_SELECTOR = "section.product[data-product_id]"
{exclusion_block}


def clean_price(raw: str) -> float | None:
    digits = re.sub(r"[^\\d.]", "", raw.strip().split("\\n")[0])
    try:
        val = float(digits) if digits else None
        return val if val else None
    except ValueError:
        return None


async def extract_image(card):
    """First real product-image URL on a listing card (absolute), or None.

    Reads common lazy-load attributes, skips inline-data / SVG icons, and
    resolves relative URLs against the page base URI in-browser.
    """
    for img in await card.query_selector_all("img"):
        url = await img.evaluate(
            """el => {{
                const v = el.getAttribute('data-src') || el.getAttribute('data-original')
                       || el.getAttribute('data-lazy') || el.getAttribute('src') || '';
                if (!v || v.startsWith('data:') || v.toLowerCase().endsWith('.svg')) return '';
                try {{ return new URL(v, document.baseURI).href; }} catch (e) {{ return ''; }}
            }}"""
        )
        if url:
            return url
    return None


async def gtm_payload(card) -> dict:
    """The card's analytics blob, or {{}} if the plugin did not render one."""
    el = await card.query_selector("[data-gtm4wp_product_data]")
    if not el:
        return {{}}
    raw = await el.get_attribute("data-gtm4wp_product_data")
    if not raw:
        return {{}}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {{}}
    return data if isinstance(data, dict) else {{}}


async def dom_price(card) -> float | None:
    """Current price from the rendered markup.

    A discounted card renders the old price in <del> and the current one in
    <ins>, so <ins> wins; otherwise take the first amount that is not inside a
    <del>. On a variable product's price range that is the low end.
    """
    el = await card.query_selector(".price ins .woocommerce-Price-amount")
    if el:
        price = clean_price(await el.inner_text())
        if price:
            return price
    for amount in await card.query_selector_all(".price .woocommerce-Price-amount"):
        if await amount.evaluate("e => !!e.closest('del')"):
            continue
        price = clean_price(await amount.inner_text())
        if price:
            return price
    return None


async def scrape_page(page, url: str) -> list[dict]:
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    try:
        await page.wait_for_selector(CARD_SELECTOR, timeout=15_000)
    except PlaywrightTimeout:
        return []

    for y in [400, 800, 1600]:
        await page.evaluate(f"window.scrollTo(0, {{y}})")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(500)

    cards = await page.query_selector_all(CARD_SELECTOR)
    products = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for card in cards:
        gtm = await gtm_payload(card)

        # Name: prefer the rendered heading. WordPress stores titles with HTML
        # entities ("&#8211;") that the browser decodes but the JSON blob does
        # not, and the name is what fuzzy matching keys on.
        name_el = await card.query_selector("h3.product-name a") or \\
                  await card.query_selector(".heading-title a")
        name = (await name_el.inner_text()).strip() if name_el else ""
        if not name:
            name = str(gtm.get("item_name") or "").strip()
        if not name:
            continue

        if EXCLUDE_NAME and EXCLUDE_NAME.search(name):
            # Loud on purpose: a silently shrinking category is the failure
            # mode this repo keeps getting bitten by.
            print(f"    [excluded, wrong category] {{name[:70]}}")
            continue

        href = (await name_el.get_attribute("href")) if name_el else None
        product_url = href or gtm.get("productlink") or None
        if product_url and not product_url.startswith("http"):
            product_url = BASE_URL + product_url

        # Price: the blob is authoritative when present (already numeric and
        # already the current, post-discount figure).
        price = None
        raw_price = gtm.get("price")
        if raw_price not in (None, "", 0, "0"):
            try:
                price = float(raw_price) or None
            except (TypeError, ValueError):
                price = None
        if price is None:
            price = await dom_price(card)

        # Stock: blob first, else the card's own instock/outofstock class.
        stock_flag = str(gtm.get("stockstatus") or "").lower()
        if not stock_flag:
            classes = (await card.get_attribute("class") or "").lower()
            stock_flag = "outofstock" if "outofstock" in classes else (
                "instock" if "instock" in classes else "")
        # Anything that is not plainly in stock (backorder included) is not
        # something a buyer can have today.
        stock_status = "in_stock" if stock_flag == "instock" else "out_of_stock"
        if price is None:
            stock_status = "out_of_stock"
        in_stock = stock_status == "in_stock"

        card_text = (await card.inner_text()).lower()
        pc_bundle_only = any(w in card_text for w in
                             ("bundle only", "bundle with pc", "only bundle", "pc bundle"))

        products.append({{
            "image_url": await extract_image(card),
            "name": name,
            "price_bdt": price,
            "in_stock": in_stock,
            "stock_status": stock_status,
            "product_url": product_url,
            "inline_specs": {{}},
            "source": "{source}",
            "pc_bundle_only": pc_bundle_only,
            "scraped_at": scraped_at,
            "_product_id": await card.get_attribute("data-product_id"),
        }})

    return products


async def scrape_listing(page, start_url: str, seen: set) -> list[dict]:
    """Page through one listing URL, skipping products already collected."""
    collected = []
    prev_ids: set = set()

    for page_num in range(1, MAX_PAGES + 1):
        url = start_url if page_num == 1 else f"{{start_url}}page/{{page_num}}/"
        print(f"  page {{page_num}}: {{url}}")
        products = await scrape_page(page, url)
        if not products:
            print("    no products — end of listing.")
            break

        page_ids = {{p["_product_id"] for p in products}}
        # An out-of-range page number can be served as page 1 again rather than
        # a 404; that repeat is the signal to stop.
        if page_ids and page_ids == prev_ids:
            print("    same products as previous page — end of listing.")
            break
        prev_ids = page_ids

        new = [p for p in products if p["_product_id"] not in seen]
        seen.update(page_ids)
        collected.extend(new)
        print(f"    {{len(products)}} found, {{len(new)}} new.")

        time.sleep(PAGE_DELAY)

    return collected


async def main(save: bool = False):
    all_products: list[dict] = []
    seen: set = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={{"width": 1280, "height": 900}},
        )
        page = await context.new_page()

        for start_url in START_URLS:
            print(f"\\nListing: {{start_url}}")
            all_products.extend(await scrape_listing(page, start_url, seen))

        await browser.close()

    for product in all_products:
        product.pop("_product_id", None)

    if save:
        out_dir = Path("data/raw")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{retailer}_{cat_name}_{{timestamp}}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"\\nSaved {{len(all_products)}} records -> {{out_path}}")

    in_stock = [p for p in all_products if p["in_stock"] and p["price_bdt"]]
    print(f"\\nTotal: {{len(all_products)}} | In stock: {{len(in_stock)}}")
    if in_stock:
        cheapest = min(in_stock, key=lambda p: p["price_bdt"])
        print(f"Cheapest: {{cheapest['name'][:70]}}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape VibeGaming {cat_name} listings")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(save=args.save))
'''


def render(cat_name: str, paths: list[str]) -> str:
    start_urls = "\n".join(f'    f"{{BASE_URL}}{p}",' for p in paths)

    pattern = NAME_EXCLUSIONS.get(cat_name)
    if pattern:
        exclusion_block = (
            "\n# Products this shop filed under the wrong category. Narrow by design —\n"
            "# it can only match another product type, never a spec of this one.\n"
            "# Every drop is printed, so over-matching shows up in the run log.\n"
            f"EXCLUDE_NAME = re.compile(r\"{pattern}\", re.I)"
        )
    else:
        exclusion_block = "\nEXCLUDE_NAME = None"
    if len(paths) == 1:
        listing_doc = f"Listing: {paths[0]}"
    else:
        joined = "\n".join(f"  · {p}" for p in paths)
        listing_doc = (
            f"Listings ({len(paths)}, de-duplicated by the shop's product id):\n{joined}"
        )
    return TEMPLATE.format(
        retailer=RETAILER,
        source=SOURCE,
        base_url=BASE_URL,
        cat_name=cat_name,
        cat_label=CAT_LABELS[cat_name],
        listing_doc=listing_doc,
        start_urls=start_urls,
        exclusion_block=exclusion_block,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Vibe Gaming scrapers")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("categories", nargs="*", default=None,
                    help="limit to these categories (default: all)")
    args = ap.parse_args()

    wanted = args.categories or sorted(CATEGORY_PATHS)
    unknown = [c for c in wanted if c not in CATEGORY_PATHS]
    if unknown:
        print(f"Unknown categories: {', '.join(unknown)}", file=sys.stderr)
        return 2

    out_dir = SCRAPERS / RETAILER
    out_dir.mkdir(exist_ok=True)

    written = skipped = 0
    for cat_name in wanted:
        target = out_dir / f"scrape_{cat_name}.py"
        if target.exists() and not args.force:
            print(f"  [skip]  {target.relative_to(SCRAPERS.parent)} exists")
            skipped += 1
            continue
        content = render(cat_name, CATEGORY_PATHS[cat_name])
        if args.dry_run:
            print(f"  [dry]   {target.relative_to(SCRAPERS.parent)}  "
                  f"({len(CATEGORY_PATHS[cat_name])} listing(s))")
        else:
            target.write_text(content, encoding="utf-8")
            print(f"  [write] {target.relative_to(SCRAPERS.parent)}  "
                  f"({len(CATEGORY_PATHS[cat_name])} listing(s))")
        written += 1

    print(f"\n{written} generated, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
