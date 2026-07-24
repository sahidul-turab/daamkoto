"""
Fail fast if the pipeline cannot reach the database.

Run this before a sweep starts. A full sweep is ~2.7 hours, and every scraper
writes to data/raw/ before anything touches PostgreSQL - so a bad credential
would otherwise surface at the very end, after all the scraping work is wasted.

Reads the same DB_* environment variables as database/load.py, so if this
passes, the loader will connect too.

Usage:
  python scripts/db_check.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "pc_comparison")
    user = os.getenv("DB_USER", "postgres")

    # Never print the password, and keep the host readable in public CI logs.
    print(f"Connecting to {user}@{host}/{name} (sslmode={os.getenv('PGSSLMODE', 'default')})")

    try:
        conn = psycopg2.connect(
            host=host,
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=name,
            user=user,
            password=os.getenv("DB_PASSWORD", ""),
            connect_timeout=15,
        )
    except Exception as exc:
        print(f"FAILED: could not connect - {exc}", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM products")
            products = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM prices")
            prices = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM retailers")
            retailers = cur.fetchone()[0]
    except Exception as exc:
        print(f"FAILED: connected, but schema looks wrong - {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(f"OK: {products:,} products / {prices:,} prices / {retailers} retailers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
