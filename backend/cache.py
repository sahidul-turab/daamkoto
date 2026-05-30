"""
Simple in-memory TTL cache for FastAPI route responses.

Used to avoid hitting the database on every single filter change — most
product queries repeat within a browsing session. No external dependency needed.
"""
from __future__ import annotations

import json
import time
import threading
from typing import Any


class TTLCache:
    """Thread-safe fixed-size TTL cache backed by a plain dict."""

    def __init__(self, ttl: int, max_size: int = 500):
        self._ttl = ttl
        self._max_size = max_size
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, val = entry
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            return val

    def set(self, key: str, val: Any) -> None:
        with self._lock:
            if len(self._store) >= self._max_size:
                oldest = min(self._store, key=lambda k: self._store[k][0])
                del self._store[oldest]
            self._store[key] = (time.monotonic(), val)

    def make_key(self, *args, **kwargs) -> str:
        return json.dumps((args, sorted(kwargs.items())), default=str, sort_keys=True)

    def invalidate_all(self) -> None:
        with self._lock:
            self._store.clear()


# Shared cache instances — import these in main.py
product_list_cache = TTLCache(ttl=300, max_size=500)   # 5 min — product search results
brands_cache       = TTLCache(ttl=600, max_size=100)   # 10 min — brand lists change rarely
spec_cache         = TTLCache(ttl=600, max_size=200)   # 10 min — spec dropdown values
seller_specs_cache = TTLCache(ttl=600, max_size=2000)  # 10 min — per-product seller specs
history_cache      = TTLCache(ttl=300, max_size=2000)  # 5 min  — price history
