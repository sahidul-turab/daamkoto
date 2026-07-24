"""
Apply a .sql migration to whichever database the DB_* environment points at.

Migrations are run manually in this project (no auto-migrate at startup), and
psql is not always on PATH on Windows - so this is the portable way to do it.

Usage:
  # local (reads .env)
  python scripts/apply_migration.py database/migration_v7_cheapest_listing.sql

  # against Neon
  $env:DB_HOST="ep-....neon.tech"; $env:DB_NAME="neondb"; ...
  $env:PGSSLMODE="require"
  python scripts/apply_migration.py database/migration_v7_cheapest_listing.sql

Runs in one transaction: either the whole file applies or none of it does.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/apply_migration.py <path-to.sql>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"No such file: {path}", file=sys.stderr)
        return 2

    with open(path, encoding="utf-8") as fh:
        sql = fh.read()

    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "pc_comparison")
    user = os.getenv("DB_USER", "postgres")
    print(f"Applying {path}")
    print(f"   -> {user}@{host}/{name}")

    conn = psycopg2.connect(
        host=host,
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=name,
        user=user,
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=20,
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Applied.")
    except Exception as exc:
        print(f"FAILED, rolled back: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
