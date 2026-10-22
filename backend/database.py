"""
Database connection pool for the FastAPI backend.

Uses psycopg2's ThreadedConnectionPool so multiple simultaneous HTTP requests
can each get their own DB connection without waiting for each other.

The pool is created once at FastAPI startup (lifespan event) and closed on shutdown.
Every route that needs the DB calls get_db() as a context manager:

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(...)

Neon suspends an idle compute after ~5 minutes, which kills every pooled
connection without psycopg2 noticing. A dead connection handed to a request
fails it with "connection already closed" — and the pool can hold ten of them,
so after a quiet spell up to ten visitors in a row got an error. get_db()
therefore pings any connection that sat idle past _IDLE_PING_SECONDS and
replaces it if the ping fails. Busy connections skip the ping.
"""

import os
import threading
import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool: ThreadedConnectionPool | None = None
_max_conn = 10
_IDLE_PING_SECONDS = 60
_last_used: dict[int, float] = {}   # id(conn) -> time.monotonic() of last return
_last_used_lock = threading.Lock()


def init_pool(min_conn: int = 1, max_conn: int = 10) -> None:
    global _pool, _max_conn
    _max_conn = max_conn
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


def _checkout():
    """A live connection from the pool, discarding any that died while idle."""
    for _ in range(_max_conn + 1):
        conn = _pool.getconn()
        with _last_used_lock:
            last = _last_used.pop(id(conn), None)
        if not conn.closed:
            if last is not None and time.monotonic() - last < _IDLE_PING_SECONDS:
                return conn
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()
                return conn
            except psycopg2.Error:
                pass
        _pool.putconn(conn, close=True)
    raise psycopg2.OperationalError("no live database connection available")


@contextmanager
def get_db():
    """
    Yield a psycopg2 connection from the pool.
    Commits on success, rolls back on any exception, always returns the
    connection to the pool when done.
    """
    conn = _checkout()
    try:
        yield conn
        conn.commit()
    except Exception:
        if not conn.closed:
            conn.rollback()
        raise
    finally:
        if not conn.closed:
            with _last_used_lock:
                _last_used[id(conn)] = time.monotonic()
        _pool.putconn(conn, close=bool(conn.closed))
