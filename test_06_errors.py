from __future__ import annotations

from collections.abc import Awaitable
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from src.api_client import BunproAuthenticationError, BunproNotFoundError
from src.tools.grammar import get_grammar_point
from src.tools.user_stats import get_user_stats

ORIGINAL_FRONTEND_TOKEN = os.environ.get("BUNPRO_FRONTEND_API_TOKEN")
ORIGINAL_JWT_TOKEN = os.environ.get("BUNPRO_JWT")

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-06-errors.log")
EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        _ = os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _preview(value: object | None) -> str:
    if value is None:
        return "<none>"
    text = str(value).strip().replace("\n", " ")
    if len(text) <= 120:
        return text
    return f"{text[:120].rstrip()}..."


def _exception_context(exc: Exception) -> str:
    if isinstance(exc, BunproAuthenticationError):
        return "authentication failure"
    if isinstance(exc, BunproNotFoundError):
        return "resource missing"
    if isinstance(exc, RuntimeError):
        message = str(exc).lower()
        if "missing" in message and "token" in message:
            return "missing token"
        return "runtime failure"
    return "unexpected"


def _emit(message: str = "") -> None:
    print(message)
    with EVIDENCE_LOG.open("a", encoding="utf-8") as log_file:
        _ = log_file.write(f"{message}\n")


async def _invalid_token_action() -> None:
    token_before = os.environ.get("BUNPRO_FRONTEND_API_TOKEN")
    os.environ["BUNPRO_FRONTEND_API_TOKEN"] = "invalid_token_12345"
    try:
        _ = await get_user_stats()
    finally:
        _restore_env("BUNPRO_FRONTEND_API_TOKEN", token_before)


async def _empty_token_action() -> None:
    token_before = os.environ.pop("BUNPRO_FRONTEND_API_TOKEN", None)
    jwt_before = os.environ.pop("BUNPRO_JWT", None)
    try:
        _ = await get_user_stats()
    finally:
        _restore_env("BUNPRO_FRONTEND_API_TOKEN", token_before)
        _restore_env("BUNPRO_JWT", jwt_before)


async def _malformed_token_action() -> None:
    token_before = os.environ.get("BUNPRO_FRONTEND_API_TOKEN")
    os.environ["BUNPRO_FRONTEND_API_TOKEN"] = "!!!@@@###$$$"
    try:
        _ = await get_user_stats()
    finally:
        _restore_env("BUNPRO_FRONTEND_API_TOKEN", token_before)


async def _nonexistent_resource_action() -> object | None:
    _result = await get_grammar_point("non-existent-slug-xyz-12345")
    return _result


async def _exercise(name: str, action: Awaitable[object | None]) -> bool:
    _emit("")
    _emit(name)
    try:
        result = await action
    except Exception as exc:
        context = _exception_context(exc)
        preview = _preview(exc)
        _emit(f"   PASS - {type(exc).__name__} ({context}): {preview}")
        return True
    else:
        preview = _preview(result)
        _emit(f"   FAIL - Expected error but got success: {preview}")
        return False


async def main() -> None:
    _emit("=" * 60)
    _emit("Test 06: Error Scenarios")
    _emit(f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}")
    _emit("=" * 60)

    scenarios: list[tuple[str, Awaitable[object | None]]] = [
        ("1. Invalid token → BunproAuthenticationError", _invalid_token_action()),
        ("2. Empty/missing token → RuntimeError", _empty_token_action()),
        ("3. Malformed token → BunproAuthenticationError", _malformed_token_action()),
        (
            "4. Non-existent grammar slug → BunproNotFoundError/RuntimeError",
            _nonexistent_resource_action(),
        ),
    ]

    passed = 0
    failed = 0

    try:
        for title, action in scenarios:
            ok = await _exercise(title, action)
            if ok:
                passed += 1
            else:
                failed += 1
    finally:
        _restore_env("BUNPRO_FRONTEND_API_TOKEN", ORIGINAL_FRONTEND_TOKEN)
        _restore_env("BUNPRO_JWT", ORIGINAL_JWT_TOKEN)

    _emit("")
    _emit("=" * 60)
    _emit(f"Results: {passed} passed, {failed} failed")
    _emit("=" * 60)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
