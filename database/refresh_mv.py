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


def main():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        print("Refreshing mv_current_prices ...", end=" ", flush=True)
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_prices;")
        print("done.")
    conn.close()


if __name__ == "__main__":
    main()
