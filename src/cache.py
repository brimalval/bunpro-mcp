from __future__ import annotations

import asyncio
import copy
import hashlib
from collections.abc import Callable
from typing import Any

from cachetools import TTLCache

TTL_SECONDS = 1800
MAX_SIZE = 128
TimerCallable = Callable[[], float]


class PendingReviewsCache:
    """Async-safe wrapper around cachetools.TTLCache for pending reviews."""

    class _LockGuard:
        def __init__(self, lock: asyncio.Lock) -> None:
            self._lock = lock

        async def __aenter__(self) -> None:
            await self._lock.acquire()

        async def __aexit__(self, exc_type, exc_value, traceback) -> None:
            self._lock.release()

    def __init__(
        self,
        *,
        ttl_seconds: int = TTL_SECONDS,
        max_size: int = MAX_SIZE,
        timer: TimerCallable | None = None,
    ) -> None:
        self._cache = TTLCache(maxsize=max_size, ttl=ttl_seconds, timer=timer)
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    def get(self, token: str) -> Any | None:
        key = self._hash_token(token)
        value = self._cache.get(key)
        if value is None:
            return None
        return copy.deepcopy(value)

    def set(self, token: str, value: Any) -> None:
        key = self._hash_token(token)
        self._cache[key] = copy.deepcopy(value)

    async def lock_for(self, token: str) -> _LockGuard:
        key = self._hash_token(token)
        lock = await self._lock_for_key(key)
        return PendingReviewsCache._LockGuard(lock)

    async def _lock_for_key(self, key: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def _hash_token(self, token: str) -> str:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return digest[:32]

    def _clear_cache(self) -> None:
        self._cache.clear()
        self._locks.clear()


_pending_reviews_cache: PendingReviewsCache | None = None


def get_pending_reviews_cache(
    *,
    ttl_seconds: int = TTL_SECONDS,
    max_size: int = MAX_SIZE,
    timer: TimerCallable | None = None,
) -> PendingReviewsCache:
    global _pending_reviews_cache
    if _pending_reviews_cache is None:
        _pending_reviews_cache = PendingReviewsCache(
            ttl_seconds=ttl_seconds,
            max_size=max_size,
            timer=timer,
        )
    return _pending_reviews_cache


def _clear_cache() -> None:
    if _pending_reviews_cache is None:
        return
    _pending_reviews_cache._clear_cache()


def _recreate_cache(
    *,
    ttl_seconds: int = TTL_SECONDS,
    max_size: int = MAX_SIZE,
    timer: TimerCallable | None = None,
) -> PendingReviewsCache:
    global _pending_reviews_cache
    _pending_reviews_cache = PendingReviewsCache(
        ttl_seconds=ttl_seconds,
        max_size=max_size,
        timer=timer,
    )
    return _pending_reviews_cache


__all__ = [
    "PendingReviewsCache",
    "get_pending_reviews_cache",
    "_clear_cache",
    "_recreate_cache",
]
