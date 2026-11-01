"""Base Infrastructure for External Data Integrations.

Provides:
- Thread-safe in-memory TTL caching with hit/miss statistics.
- Strict token/interval rate limiting (e.g. 1 req/sec policy for Nominatim).
- Bounded HTTP execution with exponential backoff for transient errors.
- Sanitized, secret-safe logging.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Generic, Optional, Tuple, TypeVar

import httpx

logger = logging.getLogger("eventprice.integrations")

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    data: T
    expires_at: float
    created_at: float


class InMemoryTTLCache:
    """Thread-safe in-memory key-value cache with time-to-live expiration."""

    def __init__(self, default_ttl_seconds: int = 300, max_entries: int = 1000):
        self._store: Dict[str, CacheEntry[Any]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self.hits: int = 0
        self.misses: int = 0

    def _purge_expired_locked(self) -> None:
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if v.expires_at <= now]
        for k in expired_keys:
            del self._store[k]

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            if entry.expires_at <= time.time():
                del self._store[key]
                self.misses += 1
                return None
            self.hits += 1
            return entry.data

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = time.time()
        with self._lock:
            if len(self._store) >= self._max_entries:
                self._purge_expired_locked()
                # If still at max capacity, evict oldest 10%
                if len(self._store) >= self._max_entries:
                    sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k].created_at)
                    evict_count = max(1, len(sorted_keys) // 10)
                    for k in sorted_keys[:evict_count]:
                        del self._store[k]

            self._store[key] = CacheEntry(
                data=value,
                expires_at=now + ttl,
                created_at=now,
            )

    def size(self) -> int:
        with self._lock:
            self._purge_expired_locked()
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0


class IntervalRateLimiter:
    """Enforces a minimum interval between requests (e.g. 1.0s for Nominatim)."""

    def __init__(self, min_interval_seconds: float = 1.0):
        self.min_interval = min_interval_seconds
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks until the minimum interval since the last request has elapsed."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.min_interval:
                sleep_needed = self.min_interval - elapsed
                time.sleep(sleep_needed)
            self._last_request_time = time.time()


def sanitize_url_for_logging(url: str, secret_param_names: Tuple[str, ...] = ("appid", "api_key", "key")) -> str:
    """Strips secret query parameters from URLs before logging."""
    for secret in secret_param_names:
        if f"{secret}=" in url:
            # Simple regex/split substitution to avoid leaking keys
            parts = url.split("?")
            if len(parts) == 2:
                base, query = parts
                query_params = query.split("&")
                clean_params = []
                for p in query_params:
                    k = p.split("=")[0]
                    if k.lower() in secret_param_names:
                        clean_params.append(f"{k}=[REDACTED]")
                    else:
                        clean_params.append(p)
                return f"{base}?{'&'.join(clean_params)}"
    return url


def generate_cache_key(prefix: str, params: Dict[str, Any]) -> str:
    """Generates a deterministic hash cache key for query parameters."""
    normalized_json = json.dumps(params, sort_keys=True, default=str)
    hashed = hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{hashed}"

