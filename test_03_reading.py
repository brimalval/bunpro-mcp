from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from src.tools.reading import get_reading_passages, search_reading_passages

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-03-reading.log")


def _ensure_log_path() -> None:
    EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)


async def main() -> int:
    _ensure_log_path()
    start_time = datetime.now()
    with EVIDENCE_LOG.open("a", encoding="utf-8") as log_fh:

        def emit(message: str, *, error: bool = False) -> None:
            stream = sys.stderr if error else sys.stdout
            print(message, file=stream)
            _ = log_fh.write(message + "\n")
            _ = log_fh.flush()
            _ = stream.flush()

        emit("=" * 60)
        emit("Test 03: Reading Tools")
        emit(f"Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        emit("=" * 60)

        async def test_get_all_passages() -> None:
            emit("1. Testing get_reading_passages()")
            response = await get_reading_passages()
            raw_results = response.get("results")
            results: list[dict[str, object]] = []
            if isinstance(raw_results, list):
                entries = cast(list[object], raw_results)
                for entry in entries:
                    if isinstance(entry, dict):
                        results.append(cast(dict[str, object], entry))
            total = len(results)
            emit(f"   PASS: get_reading_passages() returned {total} passage(s)")
            if total > 0:
                first = results[0]
                emit(f"     First title: {first.get('title', 'N/A')}")
                emit(f"     Difficulty: {first.get('difficulty', 'N/A')}")
            else:
                emit("   WARN: No passages available yet (may not have been unlocked).")

        async def _test_search(query: str, label: str, index: int) -> None:
            emit(f"{index}. Testing search_reading_passages('{query}') ({label})")
            response = await search_reading_passages(query)
            raw_results = response.get("results")
            results: list[dict[str, object]] = []
            if isinstance(raw_results, list):
                entries = cast(list[object], raw_results)
                for entry in entries:
                    if isinstance(entry, dict):
                        results.append(cast(dict[str, object], entry))
            total = len(results)
            emit(
                f"   PASS: search_reading_passages('{query}') returned {total} passage(s)"
            )
            if total > 0:
                first = results[0]
                emit(
                    f"     First match title: {first.get('title', first.get('slug', 'N/A'))}"
                )
            else:
                emit(
                    f"   WARN: No passages matched '{query}' (reading content may be locked)."
                )

        async def test_search_travel() -> None:
            await _test_search("travel", "English query", 2)

        async def test_search_japanese() -> None:
            await _test_search("日本", "Japanese query", 3)

        async def run_test(name: str, func: Callable[[], Awaitable[None]]) -> bool:
            try:
                await func()
                return True
            except Exception as exc:
                emit(
                    f"FAIL: {name} - {exc.__class__.__name__}: {exc}",
                    error=True,
                )
                return False

        tests: list[tuple[str, Callable[[], Awaitable[None]]]] = [
            ("get_reading_passages", test_get_all_passages),
            ("search_reading_passages_travel", test_search_travel),
            ("search_reading_passages_japanese", test_search_japanese),
        ]

        passed = 0
        failed = 0
        for name, func in tests:
            if await run_test(name, func):
                passed += 1
            else:
                failed += 1

        emit("=" * 60)
        emit(f"Results: {passed} passed, {failed} failed")
        emit("=" * 60)
        emit(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
