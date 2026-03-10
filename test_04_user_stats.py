from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Protocol

from src.tools.user_stats import (
    get_jlpt_progress,
    get_srs_forecast,
    get_user_stats,
)

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-04-user-stats.log")
TOKEN_SOURCES: tuple[str, ...] = ("BUNPRO_FRONTEND_API_TOKEN", "BUNPRO_JWT")


class Emitter(Protocol):
    def __call__(self, message: str, *, error: bool = False) -> None: ...


def _ensure_log_path() -> None:
    EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _iterate_tokens() -> Iterable[tuple[str, str]]:
    for key in TOKEN_SOURCES:
        value = os.environ.get(key)
        if value and value.strip():
            yield key, value.strip()


def _short_repr(value: object, *, max_length: int = 200) -> str:
    text = repr(value)
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


async def _test_user_stats(emit: Emitter) -> None:
    emit("[1/4] get_user_stats()")
    stats = await get_user_stats()
    emit(f"   Username: {stats.get('username', 'N/A')}")
    emit(f"   Total reviews: {stats.get('total_reviews', 'N/A')}")
    emit(f"   Grammar points studied: {stats.get('grammar_points_studied', 'N/A')}")
    emit(f"   Vocab learned: {stats.get('vocab_learned', 'N/A')}")
    emit(f"   Study streak: {stats.get('study_streak', 'N/A')} days")
    for field in ("username", "total_reviews"):
        if field not in stats:
            raise ValueError(f"Missing required field: {field}")


async def _test_jlpt_progress(emit: Emitter) -> None:
    emit("[2/4] get_jlpt_progress()")
    progress = await get_jlpt_progress()
    keys = list(progress.keys())
    emit(f"   Keys returned: {', '.join(keys[:4]) or 'none'}")
    if keys:
        preview_key = keys[0]
        emit(f"   Sample [{preview_key}]: {_short_repr(progress.get(preview_key))}")
    else:
        emit("   Data is empty (no progress rows)")


async def _test_srs_forecast(
    emit: Emitter, granularity: Literal["daily", "hourly"]
) -> None:
    emit(f"get_srs_forecast('{granularity}')")
    forecast = await get_srs_forecast(granularity)
    keys = list(forecast.keys())
    emit(f"   Forecast keys: {', '.join(keys[:4]) or 'none'}")
    if keys:
        preview_key = keys[0]
        emit(f"   Sample [{preview_key}]: {_short_repr(forecast.get(preview_key))}")


async def _daily_srs_forecast(emit: Emitter) -> None:
    await _test_srs_forecast(emit, "daily")


async def _hourly_srs_forecast(emit: Emitter) -> None:
    await _test_srs_forecast(emit, "hourly")


async def _run_tests(emit: Emitter) -> tuple[int, int]:
    tests: list[tuple[str, Callable[[Emitter], Awaitable[None]]]] = [
        ("User stats", _test_user_stats),
        ("JLPT progress", _test_jlpt_progress),
        ("Daily forecast", _daily_srs_forecast),
        ("Hourly forecast", _hourly_srs_forecast),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        emit(f"\n--- {name} ---")
        try:
            await test(emit)
            emit(f"PASS: {name}")
            passed += 1
        except Exception as exc:
            emit(f"FAIL: {name} - {exc.__class__.__name__}: {exc}", error=True)
            failed += 1

    return passed, failed


def main() -> int:
    _ensure_log_path()
    with EVIDENCE_LOG.open("a", encoding="utf-8") as log_fh:

        def _emit(message: str, *, error: bool = False) -> None:
            stream = sys.stderr if error else sys.stdout
            print(message, file=stream)
            _ = log_fh.write(message + "\n")
            _ = log_fh.flush()
            _ = stream.flush()

        token_source = None
        for source, _ in _iterate_tokens():
            token_source = source
            break

        if not token_source:
            _emit(
                "FAIL: Missing Bunpro token (set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT).",
                error=True,
            )
            return 1

        _emit("=" * 60)
        _emit("Test 04: User Stats Tools")
        _emit(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        _emit("=" * 60)
        _emit(f"Token source: {token_source}")

        passed, failed = asyncio.run(_run_tests(_emit))

        _emit("\n" + "=" * 60)
        _emit(f"Results: {passed} passed, {failed} failed")
        _emit("=" * 60)

        return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
