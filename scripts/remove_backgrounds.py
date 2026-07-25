"""
Background-removal processor for product images.

Retailer photos ship with a solid white background baked into the JPEG/WEBP.
This script removes that background (rembg) so the product can float on the
dark UI, and self-hosts the result as a transparent PNG.

Flow (idempotent):
  1. Read distinct image URLs from mv_current_prices that don't yet have a cutout.
  2. Download each, run rembg -> transparent PNG (across a pool of workers).
  3. Save to backend/media/cutouts/<sha1(url)>.png
  4. Record source_url -> cutout_path in the image_cutouts table (main process).

rembg is heavy (onnxruntime + a ~170 MB model on first run) and CPU-bound, so
this runs OFFLINE — never inside the web backend, which only serves the finished
PNGs as static files. Work is split across --workers processes; each loads one
rembg session.

Usage:
  python scripts/remove_backgrounds.py                     # all pending, parallel
  python scripts/remove_backgrounds.py --category "GPU"
  python scripts/remove_backgrounds.py --workers 8
  python scripts/remove_backgrounds.py --force             # re-process everything
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

load_dotenv()

MEDIA_DIR = Path(__file__).resolve().parent.parent / "backend" / "media" / "cutouts"
MODEL = "isnet-general-use"  # sharper on hard product edges; matches the RAM run
UA = "Mozilla/5.0 (compatible; DaamKoto-image-processor/1.0; educational project)"

# One rembg session per worker process, created lazily on first task.
_session = None


def _worker_init():
    global _session
    # Cap each worker's onnxruntime/OpenMP threads so N workers actually run in
    # parallel instead of each grabbing all cores and thrashing. Must be set
    # before onnxruntime is imported (which new_session does).
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("ORT_DISABLE_ALL_OPTIMIZATION", "0")
    from rembg import new_session
    _session = new_session(MODEL)


def _fetch(url: str) -> bytes:
    # Some retailers store paths with literal spaces / unsafe chars; percent-encode
    # while leaving already-valid reserved characters intact.
    safe = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=~%")
    req = urllib.request.Request(safe, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _process(url: str):
    """Worker task: download + cut out one image. Returns a result tuple."""
    global _session
    if _session is None:  # safety if initializer was skipped
        _worker_init()
    from rembg import remove
    from PIL import Image

    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    out_path = MEDIA_DIR / f"{h}.png"
    cutout_path = f"/media/cutouts/{h}.png"
    try:
        raw = _fetch(url)
        cut = remove(raw, session=_session)
        im = Image.open(io.BytesIO(cut)).convert("RGBA")
        im.save(out_path, "PNG", optimize=True)
        return (url, cutout_path, im.width, im.height, None)
    except Exception as e:  # noqa: BLE001 — one bad image shouldn't stop the run
        return (url, None, None, None, str(e)[:80])


def db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "pc_comparison"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
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
        SELECT DISTINCT m.image_url
        FROM mv_current_prices m
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
    ap.add_argument("--workers", type=int, default=6, help="Parallel worker processes (default 6)")
    args = ap.parse_args()

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    conn = db()
    conn.autocommit = True
    urls = pending_urls(conn, args.category, args.force, args.limit)
    if not urls:
        print("Nothing to process — all current images already have cutouts.")
        return
    print(f"{len(urls)} image(s) across {args.workers} workers. Model: {MODEL}")

    done = failed = 0
    total = len(urls)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as ex:
        for i, (url, cutout_path, w, h, err) in enumerate(ex.map(_process, urls), 1):
            if err is None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO image_cutouts (source_url, cutout_path, width, height)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (source_url)
                        DO UPDATE SET cutout_path = EXCLUDED.cutout_path,
                                      width = EXCLUDED.width, height = EXCLUDED.height,
                                      created_at = NOW()
                        """,
                        (url, cutout_path, w, h),
                    )
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
