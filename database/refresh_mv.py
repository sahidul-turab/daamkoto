#!/usr/bin/env python3
"""
Refresh mv_current_prices after a scrape run.

Called automatically by run_pipeline.py after database/load.py completes.
Safe to run any time — CONCURRENTLY means readers are never blocked.

Usage:
  python database/refresh_mv.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Must match database/load.py — the loader and the refresh serialise on it.
_LOAD_LOCK_KEY = 20260724


def main():
    # Prefer a cloud connection string (Neon) when present; else discrete DB_*.
    dsn = os.getenv("DATABASE_URL") or os.getenv("NEON_URL")
    if dsn:
        conn = psycopg2.connect(dsn)
    else:
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )
    conn.autocommit = True
    with conn.cursor() as cur:
        # Same advisory lock the loader takes. Categories run in parallel now, so
        # without this a refresh can start while another category is still
        # writing and the two deadlock against each other.
        #
        # REFRESH ... CONCURRENTLY cannot run inside a transaction, so this is a
        # session-level lock rather than a transactional one, and must be
        # released explicitly - hence the try/finally.
        print("Waiting for load lock ...", end=" ", flush=True)
        cur.execute("SELECT pg_advisory_lock(%s)", (_LOAD_LOCK_KEY,))
        try:
            print("refreshing mv_current_prices ...", end=" ", flush=True)
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_prices;")
            print("done.")
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_LOAD_LOCK_KEY,))
    conn.close()


if __name__ == "__main__":
    main()
