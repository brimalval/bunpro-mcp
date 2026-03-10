"""Test 05: Review Queue Tools."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import cast

from src.tools.review import get_due_count, get_study_configuration

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-05-review.log")


def _emit(message: str) -> None:
    print(message)
    _ = EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_LOG.open("a", encoding="utf-8") as handle:
        _ = handle.write(message + "\n")


def _summarize_payload(label: str, payload: dict[str, object]) -> None:
    keys = list(payload.keys())
    _emit(f"   {label} payload keys: {', '.join(keys) if keys else 'none'}")
    for key, value in payload.items():
        if isinstance(value, list):
            value_list = cast(list[object], value)
            _emit(f"   {key}: list with {len(value_list)} entries")
        elif isinstance(value, dict):
            value_dict = cast(dict[str, object], value)
            _emit(f"   {key}: dict with {len(value_dict)} keys")
        elif isinstance(value, (int, float)):
            _emit(f"   {key}: {value}")


async def test_study_configuration() -> tuple[bool, str | None]:
    _emit("\n1. Testing get_study_configuration()")
    queue: dict[str, object] = await get_study_configuration()
    _summarize_payload("study configuration", queue)

    ready = cast(list[dict[str, object]], queue.get("ready") or [])
    future = cast(list[dict[str, object]], queue.get("future") or [])
    # pprint(queue)
    queue_length = queue.get("queue_length")

    if queue_length == 0 and not ready and not future:
        _emit("   WARN: Queue reports zero items")
        return True, "Queue is empty"

    if queue_length is not None:
        _emit(f"   queue_length reported {queue_length}")
    if ready:
        _emit(f"   ready: {len(ready)} items")
        _emit(f"   First ready item type: {ready[0].get('reviewable_type') or 'N/A'}")
    if future:
        _emit(f"   future: {len(future)} items")
    return True, None


async def test_due_count() -> tuple[bool, str | None]:
    _emit("\n2. Testing get_due_count()")
    due: dict[str, object] = await get_due_count()
    _summarize_payload("due count", due)

    upcoming = cast(list[dict[str, object]], due.get("upcoming") or [])
    total_due = due.get("total_due")

    pprint(due)

    if total_due is not None:
        _emit(f"   total_due reported {total_due}")
    if upcoming:
        _emit(f"   upcoming: {len(upcoming)} items")
        _emit(f"   First due item type: {upcoming[0].get('reviewable_type') or 'N/A'}")
        return True, None

    _emit("   WARN: No items are currently due")
    return True, "No items are currently due"


async def main() -> None:
    _emit("=" * 60)
    _emit("Test 05: Review Queue Tools")
    _emit(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _emit("=" * 60)

    token = os.getenv("BUNPRO_FRONTEND_API_TOKEN") or os.getenv("BUNPRO_JWT")
    if not token:
        _emit(
            "\nFAIL: Bunpro token missing. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT."
        )
        sys.exit(1)

    tests = [
        ("Study configuration", test_study_configuration),
        ("Due count", test_due_count),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        try:
            result, warn = await test()
            if result:
                _emit(f"   PASS ({name})")
                if warn:
                    _emit(f"   WARN ({name}): {warn}")
                passed += 1
            else:
                _emit(f"   FAIL ({name})")
                failed += 1
        except Exception as exc:
            _emit(f"   FAIL ({name}) - {type(exc).__name__}: {str(exc)[:120]}")
            failed += 1

    _emit("\n" + "=" * 60)
    _emit(f"Results: {passed} passed, {failed} failed")
    _emit("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
