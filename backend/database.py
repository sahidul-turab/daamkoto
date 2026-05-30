"""
Database connection pool for the FastAPI backend.

Uses psycopg2's ThreadedConnectionPool so multiple simultaneous HTTP requests
can each get their own DB connection without waiting for each other.

The pool is created once at FastAPI startup (lifespan event) and closed on shutdown.
Every route that needs the DB calls get_db() as a context manager:

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(...)
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool: ThreadedConnectionPool | None = None


def init_pool(min_conn: int = 1, max_conn: int = 10) -> None:
    global _pool
    # Cloud hosts (Neon, Render, Supabase, Railway) expose a single
    # DATABASE_URL connection string. Prefer it when present; otherwise fall
    # back to the discrete DB_* vars used for local development.
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        _pool = ThreadedConnectionPool(min_conn, max_conn, dsn=dsn)
    else:
        _pool = ThreadedConnectionPool(
            min_conn,
            max_conn,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "pc_comparison"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )


def close_pool() -> None:
    if _pool:
        _pool.closeall()


@contextmanager
def get_db():
    """
    Yield a psycopg2 connection from the pool.
    Commits on success, rolls back on any exception, always returns the
    connection to the pool when done.
    """
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
