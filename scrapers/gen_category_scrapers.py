"""
Generate a category's scrapers by adapting each retailer's existing ones.

Why this rather than a single template: only 5 of the 13 shops run stock
OpenCart. The other 8 each need their own selectors, pagination and stock logic,
all of which already exist and are proven in that retailer's current scrapers.

Comparing scrape_psu.py against scrape_gpu.py for the same shop shows only three
category-specific things:

    line 1     the docstring
    START_URL  (or CATEGORY_URL) - the listing path
    out_path   the data/raw/{retailer}_{category}_{ts}.json filename

Everything else - card selector, price parsing, stock detection, politeness
delay, pagination - is category-agnostic. So copying a known-good scraper and
rewriting those three things inherits eight shops' worth of hard-won selector
work instead of re-deriving it.

Usage:
  python scrapers/gen_category_scrapers.py monitor            # write files
  python scrapers/gen_category_scrapers.py monitor --dry-run  # preview only
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.category_urls import CATEGORY_PATHS  # noqa: E402

SCRAPERS = Path(__file__).resolve().parent

# Prefer copying from a simple, stable category. PSU and casing have plain
# listings; GPU is the fallback since every retailer has one.
SOURCE_PREFERENCE = ["scrape_psu.py", "scrape_casing.py", "scrape_gpu.py",
                     "scrape_ssd.py", "scrape_ram.py"]

URL_ASSIGN = re.compile(
    r'^(?P<indent>\s*)(?P<name>START_URL|CATEGORY_URL)(?P<pad>\s*)=\s*'
    r'f?"(?P<prefix>\{BASE_URL\})(?P<path>[^"]*)"',
    re.M,
)


def pick_source(retailer: str) -> Path | None:
    for candidate in SOURCE_PREFERENCE:
        p = SCRAPERS / retailer / candidate
        if p.exists():
            return p
    existing = sorted((SCRAPERS / retailer).glob("scrape_*.py"))
    return existing[0] if existing else None


def adapt(text: str, retailer: str, category: str, path: str, source_name: str) -> str:
    # 1. listing URL
    new_text, n = URL_ASSIGN.subn(
        lambda m: f'{m.group("indent")}{m.group("name")}{m.group("pad")}= '
                  f'f"{m.group("prefix")}{path}"',
        text,
        count=1,
    )
    if n == 0:
        raise ValueError(f"no START_URL/CATEGORY_URL found in {source_name}")

    # 2. output filename token: {retailer}_{oldcat}_{ts}.json -> new category
    src_cat = source_name.removeprefix("scrape_").removesuffix(".py")
    new_text, n2 = re.subn(
        rf'({retailer}_){src_cat}(_\{{)',
        rf'\g<1>{category}\g<2>',
        new_text,
    )
    if n2 == 0:
        # Some scrapers build the name differently; fall back to a looser swap.
        new_text, n2 = re.subn(rf'\b{src_cat}\b(?=_\{{|_")', category, new_text)
    if n2 == 0:
        raise ValueError(f"could not rewrite output filename in {source_name}")

    # 3. docstring — replace only the first line so usage notes stay accurate
    lines = new_text.split("\n")
    for i, line in enumerate(lines[:6]):
        if '"""' in line:
            lines[i] = (f'"""{retailer.title()} {category.replace("_", " ").title()} '
                        f'scraper — URL: {path}')
            if line.rstrip().endswith('"""') and line.count('"""') == 2:
                lines[i] += '"""'
            break
    new_text = "\n".join(lines)

    # Keep argparse help honest.
    new_text = re.sub(r'(description="[^"]*?)\b' + re.escape(src_cat) + r'\b',
                      rf'\1{category}', new_text, flags=re.I)
    return new_text


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate scrapers for a category")
    ap.add_argument("category", help="category key present in CATEGORY_PATHS")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing scrape_{category}.py")
    args = ap.parse_args()

    paths = CATEGORY_PATHS.get(args.category)
    if not paths:
        print(f"No URLs recorded for '{args.category}'. Known: "
              f"{', '.join(CATEGORY_PATHS)}", file=sys.stderr)
        return 2

    written = skipped = failed = 0
    for retailer, path in sorted(paths.items()):
        target = SCRAPERS / retailer / f"scrape_{args.category}.py"
        if target.exists() and not args.force:
            print(f"  [skip]  {target.relative_to(SCRAPERS.parent)} exists")
            skipped += 1
            continue

        source = pick_source(retailer)
        if source is None:
            print(f"  [FAIL]  {retailer}: no existing scraper to adapt")
            failed += 1
            continue

        try:
            out = adapt(source.read_text(encoding="utf-8"),
                        retailer, args.category, path, source.name)
        except ValueError as exc:
            print(f"  [FAIL]  {retailer}: {exc}")
            failed += 1
            continue

        if args.dry_run:
            url_line = next(ln for ln in out.split("\n")
                            if "START_URL" in ln or "CATEGORY_URL" in ln)
            print(f"  [dry]   {retailer:<15} from {source.name:<20} {url_line.strip()}")
        else:
            target.write_text(out, encoding="utf-8")
            print(f"  [write] {target.relative_to(SCRAPERS.parent)}  (from {source.name})")
        written += 1

    print(f"\n{written} generated, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
