"""
Background-removal processor for product images — the cutout stage of the pipeline.

For every current image URL that doesn't yet have a cutout:
  1. download it, run rembg -> transparent PNG (across a pool of workers),
  2. if R2 is configured (.env.r2): upload the PNG to R2 and store the public
     Worker URL as cutout_path; otherwise store a local /media path,
  3. record source_url -> cutout_path in the image_cutouts table.

Idempotent (skips URLs already in image_cutouts) and safe to re-run. Connects to
whatever DB the environment points at — local Postgres or Neon (production) — so
`run_pipeline.py` can call it automatically after loading, and new products get
cutouts with zero manual steps.

Usage:
  python scripts/remove_backgrounds.py                     # all pending
  python scripts/remove_backgrounds.py --category "GPU"
  python scripts/remove_backgrounds.py --workers 6
"""

import argparse
import hashlib
import io
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
import psycopg2

load_dotenv(".env.r2")
load_dotenv()

MEDIA_DIR = Path(__file__).resolve().parent.parent / "backend" / "media" / "cutouts"
MODEL = "isnet-general-use"
UA = "Mozilla/5.0 (compatible; DaamKoto-image-processor/1.0; educational project)"

# R2 is used when credentials are present; otherwise cutouts are served locally.
R2_ENABLED = bool(os.getenv("R2_ACCESS_KEY_ID"))
R2_BUCKET = os.getenv("R2_BUCKET", "daamkoto-images")
R2_PUBLIC_BASE = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")

_session = None
_s3 = None


def _worker_init():
    global _session, _s3
    os.environ.setdefault("OMP_NUM_THREADS", "2")  # keep N workers from thrashing
    from rembg import new_session
    _session = new_session(MODEL)
    if R2_ENABLED:
        import boto3
        from botocore.config import Config
        _s3 = boto3.client(
            "s3", endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4", retries={"max_attempts": 4}),
        )


def _fetch(url: str) -> bytes:
    safe = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=~%")
    req = urllib.request.Request(safe, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _process(url: str):
    """Worker: download + cut out one image, upload to R2 if enabled."""
    global _session, _s3
    if _session is None:
        _worker_init()
    from rembg import remove
    from PIL import Image

    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    out_path = MEDIA_DIR / f"{h}.png"
    key = f"cutouts/{h}.png"
    try:
        raw = _fetch(url)
        cut = remove(raw, session=_session)
        im = Image.open(io.BytesIO(cut)).convert("RGBA")
        im.save(out_path, "PNG", optimize=True)
        if R2_ENABLED:
            _s3.upload_file(str(out_path), R2_BUCKET, key,
                            ExtraArgs={"ContentType": "image/png",
                                       "CacheControl": "public, max-age=31536000"})
            cutout_path = f"{R2_PUBLIC_BASE}/{key}"
        else:
            cutout_path = f"/media/{key}"
        return (url, cutout_path, im.width, im.height, None)
    except Exception as e:  # noqa: BLE001
        return (url, None, None, None, str(e)[:80])


def db():
    """Connect to the DB the environment points at (local Postgres or Neon)."""
    url = os.getenv("DATABASE_URL") or os.getenv("NEON_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""), sslmode=os.getenv("DB_SSLMODE", "prefer"),
    )


def pending_urls(conn, category, force, limit):
    where = ["m.image_url IS NOT NULL"]
    params = []
    if category:
        where.append("UPPER(p.category) = UPPER(%s)")
        params.append(category)
    if not force:
        where.append("ic.source_url IS NULL")
    sql = f"""
        SELECT DISTINCT m.image_url FROM mv_current_prices m
        JOIN products p ON p.id = m.product_id
        LEFT JOIN image_cutouts ic ON ic.source_url = m.image_url
        WHERE {" AND ".join(where)}
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


def main():
    ap = argparse.ArgumentParser(description="Remove backgrounds from product images")
    ap.add_argument("--category", help="Only this category, e.g. 'GPU'")
    ap.add_argument("--limit", type=int, help="Cap number of images this run")
    ap.add_argument("--force", action="store_true", help="Re-process even if a cutout exists")
    ap.add_argument("--workers", type=int, default=6, help="Parallel worker processes")
    args = ap.parse_args()

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    conn = db(); conn.autocommit = True
    urls = pending_urls(conn, args.category, args.force, args.limit)
    if not urls:
        print("Nothing to process — all current images already have cutouts.")
        return
    dest = f"R2 ({R2_PUBLIC_BASE})" if R2_ENABLED else "local /media"
    print(f"{len(urls)} image(s) across {args.workers} workers -> {dest}")

    done = failed = 0
    total = len(urls)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as ex:
        for i, (url, cutout_path, w, h, err) in enumerate(ex.map(_process, urls), 1):
            if err is None:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO image_cutouts (source_url, cutout_path, width, height)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT (source_url) DO UPDATE SET cutout_path = EXCLUDED.cutout_path,
                             width = EXCLUDED.width, height = EXCLUDED.height, created_at = NOW()""",
                        (url, cutout_path, w, h))
                done += 1
            else:
                failed += 1
                print(f"  FAIL {url[:70]} — {err}")
            if i % 100 == 0 or i == total:
                print(f"  [{i}/{total}] {done} ok, {failed} failed")
    conn.close()
    print(f"\nDone. {done} cutouts written, {failed} failed.")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
