from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TextIO, cast

from src.tools.vocabulary import get_vocab_level, search_vocab

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-02-vocabulary.log")


def _ensure_log_path() -> None:
    EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _emit(message: str, *, log_fh: TextIO, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream)
    _ = log_fh.write(message + "\n")
    _ = log_fh.flush()
    _ = stream.flush()


def _is_missing_token(exc: Exception) -> bool:
    return "Missing Bunpro auth token" in str(exc)


def _truncate_repr(value: object, limit: int = 64) -> str:
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _build_hit_snippet(hit: dict[str, object]) -> str:
    parts: list[str] = []
    for field in ("japanese", "reading", "type", "level"):
        value = hit.get(field)
        if isinstance(value, str) and value:
            parts.append(f"{field}={value}")
    meanings = hit.get("meanings")
    if isinstance(meanings, list):
        count = len(cast(list[object], meanings))
        parts.append(f"meanings={count} entries")
    if not parts:
        return "first hit missing metadata"
    return "; ".join(parts)


def _extract_results(
    payload: object, *, label: str, log_fh: TextIO
) -> list[dict[str, object]] | None:
    if not isinstance(payload, dict):
        _emit(
            f"FAIL: {label} - payload missing or malformed", log_fh=log_fh, error=True
        )
        return None

    payload_dict = cast(dict[str, object], payload)
    raw_results = payload_dict.get("results")
    if raw_results is None:
        _emit(f"FAIL: {label} - results key not present", log_fh=log_fh, error=True)
        return None

    if not isinstance(raw_results, list):
        _emit(f"FAIL: {label} - results is not a list", log_fh=log_fh, error=True)
        return None

    return cast(list[dict[str, object]], raw_results)


async def _test_get_vocab_level(log_fh: TextIO) -> tuple[bool, bool]:
    try:
        payload = await get_vocab_level()
    except RuntimeError as exc:
        if _is_missing_token(exc):
            _emit(
                "FAIL: get_vocab_level - Missing Bunpro auth token. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT.",
                log_fh=log_fh,
                error=True,
            )
            return False, True
        _emit(
            f"FAIL: get_vocab_level - {exc.__class__.__name__}: {exc}",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    if not payload:
        _emit("WARN: get_vocab_level - payload empty", log_fh=log_fh)
        return True, False

    keys = sorted(payload.keys())
    preview_parts: list[str] = []
    for key in keys[:4]:
        value = payload.get(key)
        preview_parts.append(f"{key}={_truncate_repr(value)}")

    preview = "; ".join(preview_parts) if preview_parts else "no preview"
    key_list = ",".join(keys)
    _emit(f"PASS: get_vocab_level - keys={key_list} preview={preview}", log_fh=log_fh)
    return True, False


async def _run_search_scenario(
    label: str, query: str, limit: int, log_fh: TextIO
) -> tuple[bool, bool]:
    try:
        payload = await search_vocab(query, result_limit=limit)
    except RuntimeError as exc:
        if _is_missing_token(exc):
            _emit(
                f"FAIL: {label} search ({query}) - Missing Bunpro auth token. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT.",
                log_fh=log_fh,
                error=True,
            )
            return False, True
        _emit(
            f"FAIL: {label} search ({query}) - {exc.__class__.__name__}: {exc}",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    results = _extract_results(
        payload, label=f"{label} search ({query})", log_fh=log_fh
    )
    if results is None:
        return False, False

    if not results:
        _emit(
            f"WARN: {label} search ({query}) limit={limit} - no hits returned",
            log_fh=log_fh,
        )
        return True, False

    snippet = _build_hit_snippet(results[0])
    _emit(
        f"PASS: {label} search ({query}) limit={limit} - first hit: {snippet}",
        log_fh=log_fh,
    )
    return True, False


async def _english_search(log_fh: TextIO) -> tuple[bool, bool]:
    return await _run_search_scenario("English", "hello", 5, log_fh)


async def _japanese_search(log_fh: TextIO) -> tuple[bool, bool]:
    return await _run_search_scenario("Japanese", "ありがとう", 3, log_fh)


async def _test_result_limit(log_fh: TextIO) -> tuple[bool, bool]:
    try:
        payload_5 = await search_vocab("hello", result_limit=5)
        payload_10 = await search_vocab("hello", result_limit=10)
    except RuntimeError as exc:
        if _is_missing_token(exc):
            _emit(
                "FAIL: result_limit test - Missing Bunpro auth token. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT.",
                log_fh=log_fh,
                error=True,
            )
            return False, True
        _emit(
            f"FAIL: result_limit test - {exc.__class__.__name__}: {exc}",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    results_5 = _extract_results(payload_5, label="result_limit (5)", log_fh=log_fh)
    if results_5 is None:
        return False, False
    results_10 = _extract_results(payload_10, label="result_limit (10)", log_fh=log_fh)
    if results_10 is None:
        return False, False

    if not results_5 or not results_10:
        _emit(
            "WARN: result_limit test - empty results prevent verifying limits",
            log_fh=log_fh,
        )
        return True, False

    len_5 = len(results_5)
    len_10 = len(results_10)
    if len_5 > len_10:
        _emit(
            "FAIL: result_limit test - limit=5 returned more hits than limit=10",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    if len_5 > 5 or len_10 > 10:
        _emit(
            "FAIL: result_limit test - server returned more hits than the requested limit",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    _emit(
        f"PASS: result_limit test - limit=5 returned {len_5}, limit=10 returned {len_10}",
        log_fh=log_fh,
    )
    return True, False


async def main() -> int:
    _ensure_log_path()
    with EVIDENCE_LOG.open("a", encoding="utf-8") as log_fh:
        scenarios = [
            ("get_vocab_level", _test_get_vocab_level),
            ("english search", _english_search),
            ("japanese search", _japanese_search),
            ("result limit", _test_result_limit),
        ]

        failed = False
        missing_token = False

        for _, runner in scenarios:
            passed, token_missing = await runner(log_fh)
            if token_missing:
                missing_token = True
                failed = True
                break
            if not passed:
                failed = True

        if missing_token:
            return 1
        return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
