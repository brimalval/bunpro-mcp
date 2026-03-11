from __future__ import annotations

import asyncio
import copy
import hashlib
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import AsyncContextManager, Protocol

from cachetools import TTLCache

TTL_SECONDS = 1800
MAX_SIZE = 128
TimerCallable = Callable[[], float]


class _CacheProtocol(Protocol):
    def get(self, key: str) -> object | None: ...

    def __setitem__(self, key: str, value: object) -> None: ...

    def clear(self) -> None: ...


class PendingReviewsCache:
    """Async-safe wrapper around cachetools.TTLCache for pending reviews."""

    def __init__(
        self,
        *,
        ttl_seconds: int = TTL_SECONDS,
        max_size: int = MAX_SIZE,
        timer: TimerCallable | None = None,
    ) -> None:
        timer_callable = timer or time.monotonic
        self._cache: _CacheProtocol = TTLCache(
            maxsize=max_size,
            ttl=ttl_seconds,
            timer=timer_callable,
        )
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_lock: asyncio.Lock = asyncio.Lock()

    def get(self, token: str) -> object | None:
        key = self._hash_token(token)
        value = self._cache.get(key)
        if value is None:
            return None
        return copy.deepcopy(value)

    def set(self, token: str, value: object) -> None:
        key = self._hash_token(token)
        self._cache[key] = copy.deepcopy(value)

    def clear(self) -> None:
        self._cache.clear()
        self._locks.clear()

    def lock_for(self, token: str) -> AsyncContextManager[None]:
        key = self._hash_token(token)
        return self._lock_context(key)

    @asynccontextmanager
    async def _lock_context(self, key: str) -> AsyncIterator[None]:
        lock = await self._lock_for_key(key)
        async with lock:
            yield

    async def _lock_for_key(self, key: str) -> asyncio.Lock:
        async with self._locks_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def _hash_token(self, token: str) -> str:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return digest[:32]


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
    _pending_reviews_cache.clear()


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
