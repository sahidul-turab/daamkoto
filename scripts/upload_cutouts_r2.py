"""
Upload all cutout PNGs to Cloudflare R2 (S3-compatible object storage).

Reads R2 credentials from the environment (see .env.r2). Uploads every file in
backend/media/cutouts/ to  <bucket>/cutouts/<name>.png  in parallel, sets the
Content-Type so browsers render them, and skips files already present (idempotent
— safe to re-run if the connection drops).

The public URL of each file becomes:
    {R2_PUBLIC_BASE}/cutouts/<name>.png

Usage:
  # put creds in the environment (or a .env.r2 file loaded below), then:
  python scripts/upload_cutouts_r2.py
  python scripts/upload_cutouts_r2.py --workers 24
"""

import argparse
import glob
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

# Load R2 creds from .env.r2 if present (kept out of git), else the process env.
load_dotenv(".env.r2")
load_dotenv()

import boto3
from botocore.config import Config

ENDPOINT = os.environ["R2_ENDPOINT"]
KEY = os.environ["R2_ACCESS_KEY_ID"]
SECRET = os.environ["R2_SECRET_ACCESS_KEY"]
BUCKET = os.environ.get("R2_BUCKET", "daamkoto-images")

CUTOUT_DIR = Path("backend/media/cutouts")

_counter = 0
_lock = threading.Lock()
_total = 0


def _client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=KEY,
        aws_secret_access_key=SECRET,
        config=Config(signature_version="s3v4", retries={"max_attempts": 4, "mode": "standard"}),
    )


# One client per thread (boto3 clients aren't thread-safe to share).
_local = threading.local()


def _get_client():
    if not hasattr(_local, "c"):
        _local.c = _client()
    return _local.c


def existing_keys() -> set[str]:
    """List keys already in the bucket so re-runs skip them."""
    c = _client()
    keys: set[str] = set()
    token = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": "cutouts/", "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = c.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            keys.add(obj["Key"])
        if resp.get("IsTruncated"):
            token = resp["NextContinuationToken"]
        else:
            break
    return keys


def upload(path: str, skip: set[str]):
    global _counter
    key = "cutouts/" + os.path.basename(path)
    if key in skip:
        result = "skip"
    else:
        _get_client().upload_file(
            path, BUCKET, key, ExtraArgs={"ContentType": "image/png", "CacheControl": "public, max-age=31536000"}
        )
        result = "ok"
    with _lock:
        _counter += 1
        if _counter % 500 == 0 or _counter == _total:
            print(f"  [{_counter}/{_total}] uploaded", flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24, help="parallel upload threads")
    args = ap.parse_args()

    global _total
    files = sorted(glob.glob(str(CUTOUT_DIR / "*.png")))
    _total = len(files)
    if not files:
        print("No cutout PNGs found in backend/media/cutouts/")
        return
    print(f"{_total} files to upload to r2://{BUCKET}/cutouts/  ({args.workers} workers)")
    print("Checking what's already uploaded ...", flush=True)
    skip = existing_keys()
    print(f"  {len(skip)} already present, will skip those.", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(lambda p: upload(p, skip), files))

    print(f"\nDone. {_total} files processed.")
    print(f"Public base: {os.environ.get('R2_PUBLIC_BASE', '(set R2_PUBLIC_BASE)')}/cutouts/<name>.png")


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
