"""
Emit the GitHub Actions matrix of categories to scrape.

A workflow matrix is fixed when the file is written, so a targeted dispatch
("just re-run gpu") cannot narrow it without generating the list at run time.
This reads the optional INPUT_CATEGORIES and falls back to the full list in
scheduler.py, which stays the single source of truth - adding a category there
automatically adds it to the nightly matrix.

Usage (in a workflow step):
  run: python scripts/build_matrix.py
  env:
    INPUT_CATEGORIES: ${{ github.event.inputs.categories }}
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scheduler import CATEGORIES  # noqa: E402  - single source of truth


def main() -> int:
    raw = (os.getenv("INPUT_CATEGORIES") or "").strip()

    if raw:
        requested = raw.split()
        unknown = [c for c in requested if c not in CATEGORIES]
        if unknown:
            print(f"::error::unknown categories: {' '.join(unknown)}. "
                  f"Known: {' '.join(CATEGORIES)}", file=sys.stderr)
            return 1
        categories = requested
    else:
        categories = list(CATEGORIES)

    payload = json.dumps(categories)
    print(f"matrix: {payload}")

    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"categories={payload}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
