"""
In-memory response cache for the FastAPI layer.

Three properties matter for perceived speed, and a plain TTL dict only gives
the first one:

  1. Hit  — repeat request, entry still fresh → return immediately.
  2. Stale hit — entry expired but still usable. We return the stale value
     *now* and refresh it on a background thread. The user never waits for the
     database just because a timer ran out. Entries stay usable up to
     `stale_ttl` past expiry; beyond that they are dropped.
  3. Single-flight — when N requests miss the same key at once (very common on
     a cold start, when everyone lands on the default category), only one of
     them runs the query. The rest wait on the same result instead of piling N
     identical aggregations onto the database.

Prices only change when the scraper pipeline runs, so serving a few-minute-old
product list is always acceptable; `_run_pipeline_bg` invalidates everything
when fresh data lands.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

# Background workers for stale refreshes. Small on purpose: a refresh is never
# urgent (a stale value already went out), and the DB pool has 10 connections.
_refresh_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache-refresh")


class TTLCache:
    """Thread-safe fixed-size cache with stale-while-revalidate and single-flight."""

    def __init__(self, ttl: int, max_size: int = 500, stale_ttl: int | None = None):
        self._ttl = ttl
        # How long past expiry a value may still be served while it refreshes.
        # Defaults to 12x the TTL — long enough that a backend restart or a slow
        # database never forces a user to wait behind a cold query.
        self._stale_ttl = stale_ttl if stale_ttl is not None else ttl * 12
        self._max_size = max_size
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        # key → lock, so concurrent misses on the same key collapse into one query
        self._inflight: dict[str, threading.Lock] = {}
        self._refreshing: set[str] = set()

    # ── basic get/set (unchanged semantics: only ever returns fresh values) ──

    def get(self, key: str) -> Any | None:
        entry = self._peek(key)
        if entry is None:
            return None
        value, age = entry
        return value if age <= self._ttl else None

    def set(self, key: str, val: Any) -> None:
        with self._lock:
            if key not in self._store and len(self._store) >= self._max_size:
                oldest = min(self._store, key=lambda k: self._store[k][0])
                del self._store[oldest]
            self._store[key] = (time.monotonic(), val)

    def make_key(self, *args, **kwargs) -> str:
        return json.dumps((args, sorted(kwargs.items())), default=str, sort_keys=True)

    def invalidate_all(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Number of entries held, fresh or stale. Used by the health endpoint."""
        with self._lock:
            return len(self._store)

    # ── the fast path ───────────────────────────────────────────────────────

    def get_or_load(self, key: str, loader: Callable[[], Any]) -> Any:
        """
        Return the cached value for `key`, computing it via `loader` if needed.

        Fresh  → returned as-is.
        Stale  → returned immediately; `loader` re-runs on a background thread.
        Miss   → `loader` runs inline, and concurrent callers for the same key
                 wait for that single call rather than each running their own.
        """
        entry = self._peek(key)
        if entry is not None:
            value, age = entry
            if age <= self._ttl:
                return value
            self._schedule_refresh(key, loader)
            return value

        # True miss — single-flight so a stampede costs one query, not N.
        lock = self._acquire_inflight_lock(key)
        with lock:
            entry = self._peek(key)
            if entry is not None:
                value, age = entry
                if age <= self._ttl:
                    return value
            try:
                value = loader()
                # Store before releasing: a waiter that arrives in the gap
                # between release and set would otherwise miss and re-run the
                # very query this lock exists to collapse.
                self.set(key, value)
                return value
            finally:
                self._release_inflight_lock(key)

    def warm(self, key: str, loader: Callable[[], Any]) -> None:
        """Populate `key` if it is missing. Used by the startup warmup."""
        if self._peek(key) is None:
            try:
                self.set(key, loader())
            except Exception:
                pass  # warmup is best-effort; never block or crash startup

    # ── internals ───────────────────────────────────────────────────────────

    def _peek(self, key: str) -> tuple[Any, float] | None:
        """Return (value, age_seconds) if present and not beyond the stale window."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, val = entry
            age = time.monotonic() - ts
            if age > self._ttl + self._stale_ttl:
                del self._store[key]
                return None
            return val, age

    def _acquire_inflight_lock(self, key: str) -> threading.Lock:
        with self._lock:
            lock = self._inflight.get(key)
            if lock is None:
                lock = threading.Lock()
                self._inflight[key] = lock
            return lock

    def _release_inflight_lock(self, key: str) -> None:
        with self._lock:
            self._inflight.pop(key, None)

    def _schedule_refresh(self, key: str, loader: Callable[[], Any]) -> None:
        """Kick off one background refresh per key; ignore repeat requests."""
        with self._lock:
            if key in self._refreshing:
                return
            self._refreshing.add(key)

        def _refresh() -> None:
            try:
                self.set(key, loader())
            except Exception:
                # Keep the stale value rather than evicting it — a stale price
                # list beats an error page while the database is unreachable.
                pass
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        try:
            _refresh_pool.submit(_refresh)
        except RuntimeError:  # pool shut down during interpreter teardown
            with self._lock:
                self._refreshing.discard(key)


# Shared cache instances — import these in main.py.
# TTL = how long a value is served without any refresh at all.
# Past that it is still served instantly while it refreshes in the background,
# so these numbers control freshness, not latency.
product_list_cache = TTLCache(ttl=300, max_size=2000)  # 5 min  — product search results
brands_cache       = TTLCache(ttl=900, max_size=100)   # 15 min — brand lists change rarely
spec_cache         = TTLCache(ttl=900, max_size=400)   # 15 min — spec dropdown values
seller_specs_cache = TTLCache(ttl=900, max_size=2000)  # 15 min — per-product seller specs
history_cache      = TTLCache(ttl=600, max_size=2000)  # 10 min — price history
meta_cache         = TTLCache(ttl=900, max_size=32)    # 15 min — categories, retailers
deals_cache        = TTLCache(ttl=600, max_size=64)    # 10 min — deals feed


ALL_CACHES = (
    product_list_cache, brands_cache, spec_cache,
    seller_specs_cache, history_cache, meta_cache, deals_cache,
)


def invalidate_everything() -> None:
    """Drop every cached response — called after a scrape run loads new prices."""
    for cache in ALL_CACHES:
        cache.invalidate_all()
