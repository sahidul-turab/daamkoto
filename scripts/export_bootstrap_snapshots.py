"""Publish fast-start product pages to Cloudflare R2.

The production API runs on Render's free tier and can take tens of seconds to
wake. These snapshots let a first-time visitor see database-generated products
from the existing Cloudflare Worker immediately while the browser wakes and
revalidates the API in the background.

Only the unfiltered first page is exported. Search and filters still use the
live API, which is normally awake by the time a visitor interacts with them.

Usage:
    python scripts/export_bootstrap_snapshots.py --upload
    python scripts/export_bootstrap_snapshots.py --output-dir data/bootstrap
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env.r2")
load_dotenv(ROOT / ".env")

from backend import database, queries  # noqa: E402


PAGE_SIZE = 20
SORTS = ("store_count_desc", "price_asc")
SNAPSHOT_PREFIX = "snapshots/v1"
HOME_CATEGORIES = (
    "GPU",
    "PROCESSOR",
    "MOTHERBOARD",
    "RAM DESKTOP",
    "SSD",
    "MONITOR",
    "KEYBOARD",
    "MOUSE",
)
HOME_PRODUCTS_PER_CATEGORY = 4


def category_slug(category: str) -> str:
    """Keep this identical to frontend-react/src/lib/bootstrap.ts."""
    return re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Cannot JSON-encode {type(value).__name__}")


def make_r2_client():
    import boto3
    from botocore.config import Config

    required = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing R2 environment variables: {', '.join(missing)}")

    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 4, "mode": "standard"},
        ),
    )


def write_local(output_dir: Path, key: str, body: bytes) -> None:
    path = output_dir / key.removeprefix(f"{SNAPSHOT_PREFIX}/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def upload_snapshot(client, bucket: str, key: str, body: bytes) -> None:
    client.put_object(
        Bucket=bucket,
        Key=key,
        # Store plain JSON. Cloudflare negotiates transport compression at the
        # edge; pre-compressing here and also setting Content-Encoding caused a
        # double-gzip response that browsers could not pass to response.json().
        Body=body,
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=300, stale-while-revalidate=86400",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload snapshots to the configured Cloudflare R2 bucket",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Also write readable JSON snapshots beneath this directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.upload and args.output_dir is None:
        raise SystemExit("Choose --upload and/or --output-dir")

    r2 = make_r2_client() if args.upload else None
    bucket = os.getenv("R2_BUCKET", "daamkoto-images")
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    published: list[dict[str, str]] = []
    home_sections_by_category: dict[str, dict[str, Any]] = {}

    database.init_pool(min_conn=1, max_conn=2)
    try:
        with database.get_db() as conn:
            categories = queries.get_categories(conn)
            for category in categories:
                slug = category_slug(category)
                for sort in SORTS:
                    products, total = queries.search_products(
                        conn,
                        category=category,
                        in_stock_only=True,
                        sort=sort,
                        limit=PAGE_SIZE,
                        offset=0,
                    )
                    payload = {
                        "version": 1,
                        "generated_at": generated_at,
                        "total": total,
                        "limit": PAGE_SIZE,
                        "offset": 0,
                        "products": products,
                    }

                    # Reuse the widest-availability page for the homepage feed.
                    # Some historic rows share a match_key, so dedupe before
                    # choosing the four cards a visitor sees.
                    if sort == "store_count_desc" and category in HOME_CATEGORIES:
                        seen: set[str] = set()
                        featured: list[dict[str, Any]] = []
                        for product in products:
                            identity = str(
                                product.get("match_key") or product.get("id")
                            ).casefold()
                            if identity in seen:
                                continue
                            seen.add(identity)
                            featured.append(product)
                            if len(featured) >= HOME_PRODUCTS_PER_CATEGORY:
                                break
                        home_sections_by_category[category] = {
                            "category": category,
                            "total": total,
                            "products": featured,
                        }
                    body = json.dumps(
                        payload,
                        default=json_default,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    key = f"{SNAPSHOT_PREFIX}/{slug}/{sort}.json"

                    if args.output_dir is not None:
                        write_local(args.output_dir, key, body)
                    if r2 is not None:
                        upload_snapshot(r2, bucket, key, body)

                    published.append({"category": category, "sort": sort, "key": key})
                    print(f"{category:<18} {sort:<20} {len(body) / 1024:7.1f} KiB")
    finally:
        database.close_pool()

    # A single small CDN object powers every homepage section. This avoids both
    # a Render cold start and eight parallel category snapshot requests.
    home_payload = {
        "version": 1,
        "generated_at": generated_at,
        "sections": [
            home_sections_by_category[category]
            for category in HOME_CATEGORIES
            if category in home_sections_by_category
        ],
    }
    home_body = json.dumps(
        home_payload,
        default=json_default,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    home_key = f"{SNAPSHOT_PREFIX}/home.json"
    if args.output_dir is not None:
        write_local(args.output_dir, home_key, home_body)
    if r2 is not None:
        upload_snapshot(r2, bucket, home_key, home_body)
    published.append({"category": "HOME", "sort": "featured", "key": home_key})
    print(f"{'HOME':<18} {'featured':<20} {len(home_body) / 1024:7.1f} KiB")

    manifest = json.dumps(
        {"version": 1, "generated_at": generated_at, "snapshots": published},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest_key = f"{SNAPSHOT_PREFIX}/manifest.json"
    if args.output_dir is not None:
        write_local(args.output_dir, manifest_key, manifest)
    if r2 is not None:
        upload_snapshot(r2, bucket, manifest_key, manifest)

    destination = "R2" if args.upload else str(args.output_dir)
    print(f"Published {len(published)} product snapshots to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
