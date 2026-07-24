"""
Emit the GitHub Actions matrix of categories to scrape.

A workflow matrix is fixed when the file is written, so a targeted dispatch
("just re-run gpu") cannot narrow it without generating the list at run time.

scheduler.CATEGORIES stays the single source of truth, but it is read with `ast`
rather than imported: scheduler.py pulls in psycopg2 and dotenv at module level,
and this runs in a bare job that has no dependencies installed. Parsing the
literal keeps the prepare step dependency-free and instant.

Usage (in a workflow step):
  run: python scripts/build_matrix.py
  env:
    INPUT_CATEGORIES: ${{ github.event.inputs.categories }}
"""

import ast
import json
import os
import sys
from pathlib import Path

SCHEDULER = Path(__file__).resolve().parent.parent / "scheduler.py"


def known_categories() -> list[str]:
    """Read the CATEGORIES literal out of scheduler.py without importing it."""
    tree = ast.parse(SCHEDULER.read_text(encoding="utf-8"), filename=str(SCHEDULER))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "CATEGORIES":
                value = ast.literal_eval(node.value)
                if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                    raise TypeError("CATEGORIES is not a list of strings")
                return value
    raise LookupError(f"No CATEGORIES assignment found in {SCHEDULER}")


def main() -> int:
    try:
        categories = known_categories()
    except Exception as exc:
        print(f"::error::could not read categories: {exc}", file=sys.stderr)
        return 1

    raw = (os.getenv("INPUT_CATEGORIES") or "").strip()
    if raw:
        requested = raw.split()
        unknown = [c for c in requested if c not in categories]
        if unknown:
            print(f"::error::unknown categories: {' '.join(unknown)}. "
                  f"Known: {' '.join(categories)}", file=sys.stderr)
            return 1
        categories = requested

    payload = json.dumps(categories)
    print(f"matrix: {payload}")

    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"categories={payload}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
