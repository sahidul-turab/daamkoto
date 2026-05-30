"""
Bundle-only enrichment pass.

Visits each product's detail page and checks for bundle-only restrictions
(e.g. "Price valid only with PC bundle" on UltraTech, "ONLY BUNDLE WITH PC"
on Creatus). Updates pc_bundle_only=True in-place on the JSON file.

Usage:
  python scrapers/enrich_bundle.py data/raw/creatus_ram_*.json
  python scrapers/enrich_bundle.py data/raw/ultratech_ram_*.json
  python scrapers/enrich_bundle.py data/raw/creatus_ram_*.json data/raw/ultratech_ram_*.json

Only visits detail pages for products that have a product_url and are currently
marked pc_bundle_only=False (skips already-confirmed bundles and products
with no URL). Polite: 1–2 s delay between requests.
"""

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BUNDLE_KEYWORDS = ("bundle only", "bundle with pc", "only bundle", "pc bundle")
PAGE_DELAY = 1.5  # seconds between detail page requests


async def check_bundle(page, url: str) -> bool:
    """Visit a product detail page and return True if it's bundle-only."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_timeout(800)
        body_text = (await page.inner_text("body")).lower()
        return any(kw in body_text for kw in BUNDLE_KEYWORDS)
    except (PlaywrightTimeout, Exception):
        return False


async def enrich_file(path: Path, browser) -> int:
    """Enrich one raw JSON file. Returns number of products flagged bundle_only."""
    products = json.loads(path.read_text(encoding="utf-8"))
    to_check = [p for p in products if p.get("product_url") and not p.get("pc_bundle_only")]
    print(f"\n{path.name}: {len(products)} products, {len(to_check)} to check")

    if not to_check:
        print("  Nothing to check — skipping.")
        return 0

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    page = await context.new_page()

    flagged = 0
    for i, product in enumerate(to_check, 1):
        url = product["product_url"]
        is_bundle = await check_bundle(page, url)
        if is_bundle:
            product["pc_bundle_only"] = True
            flagged += 1
            print(f"  [{i}/{len(to_check)}] BUNDLE: {product['name'][:70]}")
        else:
            if i % 20 == 0:
                print(f"  [{i}/{len(to_check)}] checked so far, {flagged} bundle found...")
        await asyncio.sleep(PAGE_DELAY)

    await context.close()

    path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Done: {flagged} bundle-only products flagged in {path.name}")
    return flagged


async def main(files: list[Path]) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        total_flagged = 0
        for f in files:
            total_flagged += await enrich_file(f, browser)
        await browser.close()

    print(f"\nEnrichment complete. Total bundle-only products flagged: {total_flagged}")
    if total_flagged == 0:
        print("  (No bundle-only products found — the restriction may not be visible on detail pages,")
        print("   or these specific products don't have bundle restrictions.)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich raw JSON with pc_bundle_only from detail pages")
    parser.add_argument("files", nargs="+", help="Raw JSON files to enrich (glob patterns supported)")
    args = parser.parse_args()

    paths = []
    for pattern in args.files:
        matched = sorted(Path(".").glob(pattern))
        if not matched:
            # Try as literal path
            p = Path(pattern)
            if p.exists():
                matched = [p]
        paths.extend(matched)

    if not paths:
        print("No files matched.")
        sys.exit(1)

    # Use the most recent file when multiple match a glob
    seen_stems = set()
    deduped = []
    for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
        stem = "_".join(p.stem.split("_")[:3])  # e.g. creatus_ram_2026...
        base = p.stem.rsplit("_", 2)[0]         # creatus_ram
        if base not in seen_stems:
            seen_stems.add(base)
            deduped.append(p)

    print(f"Files to enrich: {[str(p) for p in deduped]}")
    asyncio.run(main(deduped))
