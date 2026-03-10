from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

from src.api_client import resolve_frontend_api_token
from src.tools.grammar import get_grammar_point, search_grammar
from src.tools.reading import get_reading_passages, search_reading_passages
from src.tools.review import get_due_count, get_study_configuration
from src.tools.user_stats import get_jlpt_progress, get_srs_forecast, get_user_stats
from src.tools.vocabulary import get_vocab_items, get_vocab_level, search_vocab

LOG_DIR = Path(".sisyphus/evidence/real-api-testing")
LOG_FILE = LOG_DIR / "test-all-comprehensive.log"
EXPECTED_TESTS = 14
GRAMMAR_IDENTIFIERS = ("slug", "id", "grammar_point_id", "reviewable_id")
VOCAB_IDENTIFIERS = ("slug", "id")


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _append_to_log(entries: Iterable[str]) -> None:
    _ensure_log_dir()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        for entry in entries:
            _ = handle.write(f"{entry}\n")


def _list_from_payload(
    payload: dict[str, object], keys: Iterable[str] = ("results", "passages")
) -> list[dict[str, object]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [
                cast(dict[str, object], item)
                for item in cast(list[object], value)
                if isinstance(item, dict)
            ]
    return []


def _first_identifier_from_results(
    payload: dict[str, object], candidates: Iterable[str]
) -> str | None:
    hits = _list_from_payload(payload, ("results",))
    for entry in hits:
        for key in candidates:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, int):
                return str(value)
    return None


def _search_result_summary(
    payload: dict[str, object], keys: Iterable[str] = ("results",)
) -> str:
    hits = _list_from_payload(payload, keys)
    if hits:
        return f"{len(hits)} hit(s)"
    return "0 hits (warning: no results)"


def _reading_passage_summary(payload: dict[str, object]) -> str:
    hits = _list_from_payload(payload, ("passages", "results"))
    if hits:
        return f"{len(hits)} passage(s)"
    return "0 passages (warning: none returned)"


def _queue_summary(payload: dict[str, object]) -> str:
    ready_value = payload.get("ready")
    future_value = payload.get("future")
    ready: list[object] = (
        cast(list[object], ready_value) if isinstance(ready_value, list) else []
    )
    future: list[object] = (
        cast(list[object], future_value) if isinstance(future_value, list) else []
    )
    ready_count = len(ready)
    future_count = len(future)
    message = f"ready={ready_count} future={future_count}"
    if ready_count + future_count == 0:
        return f"{message} (warning: queue empty)"
    return message


def _due_summary(payload: dict[str, object]) -> str:
    upcoming_value = payload.get("upcoming")
    upcoming: list[object] = (
        cast(list[object], upcoming_value) if isinstance(upcoming_value, list) else []
    )
    count = len(upcoming)
    if count == 0:
        return "upcoming=0 (warning: no due items)"
    return f"upcoming={count}"


def _dict_keys_summary(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, dict):
        typed = cast(dict[str, object], value)
        return f"{key} keys={len(typed)}"
    return f"{key}=missing"


def _list_length_summary(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, list):
        typed = cast(list[object], value)
        return f"{key} entries={len(typed)}"
    return f"{key}=missing"


async def main() -> int:
    start_time = time.monotonic()
    lines: list[str] = []
    counts: dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}

    def record_line(status: str, label: str, detail: str | None = None) -> None:
        text = f"{status} - {label}"
        if detail:
            text = f"{text} - {detail}"
        print(text)
        lines.append(text)
        if status in counts:
            counts[status] += 1

    def record_summary(duration: float) -> None:
        passed = counts["PASS"]
        failed = counts["FAIL"]
        total = passed + failed
        summary = f"SUMMARY - Passed: {passed} Failed: {failed} Total: {total} Duration: {duration:.2f}s"
        print(summary)
        lines.append(summary)

    async def _run_test(
        label: str,
        action: Callable[[], Awaitable[dict[str, object]]],
        detail_fn: Callable[[dict[str, object]], str] | None = None,
    ) -> dict[str, object] | None:
        try:
            payload = await action()
        except Exception as exc:  # noqa: BLE490
            record_line("FAIL", label, str(exc))
            return None
        detail = detail_fn(payload) if detail_fn else None
        record_line("PASS", label, detail)
        return payload

    header = f"RUN START - {datetime.now(timezone.utc).isoformat()}"
    print(header)
    lines.append(header)

    token = resolve_frontend_api_token()
    if not token:
        record_line(
            "FAIL",
            "startup",
            "missing Bunpro auth token (set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT)",
        )
    else:
        grammar_particles_payload = await _run_test(
            "search_grammar('particles')",
            lambda: search_grammar("particles"),
            lambda payload: _search_result_summary(payload),
        )
        grammar_japanese_payload = await _run_test(
            "search_grammar('は')",
            lambda: search_grammar("は"),
            lambda payload: _search_result_summary(payload),
        )
        grammar_slug: str | None = None
        if grammar_particles_payload is not None:
            grammar_slug = _first_identifier_from_results(
                grammar_particles_payload, GRAMMAR_IDENTIFIERS
            )
        if grammar_slug is None and grammar_japanese_payload is not None:
            grammar_slug = _first_identifier_from_results(
                grammar_japanese_payload, GRAMMAR_IDENTIFIERS
            )
        grammar_fallback = False
        if grammar_slug is None:
            grammar_slug = "1"
            grammar_fallback = True
        _ = await _run_test(
            "get_grammar_point",
            lambda: get_grammar_point(grammar_slug),
            lambda _: f"slug={grammar_slug}{' (fallback)' if grammar_fallback else ''}",
        )

        _ = await _run_test(
            "get_vocab_level",
            get_vocab_level,
            lambda payload: _dict_keys_summary(payload, "summary"),
        )

        vocab_search_english_payload = await _run_test(
            "search_vocab('hello')",
            lambda: search_vocab("hello", 5),
            lambda payload: _search_result_summary(payload),
        )
        vocab_search_japanese_payload = await _run_test(
            "search_vocab('ありがとう')",
            lambda: search_vocab("ありがとう", 3),
            lambda payload: _search_result_summary(payload),
        )
        vocab_slug: str | None = None
        if vocab_search_english_payload is not None:
            vocab_slug = _first_identifier_from_results(
                vocab_search_english_payload, VOCAB_IDENTIFIERS
            )
        if vocab_slug is None and vocab_search_japanese_payload is not None:
            vocab_slug = _first_identifier_from_results(
                vocab_search_japanese_payload, VOCAB_IDENTIFIERS
            )
        vocab_fallback = False
        if vocab_slug is None:
            vocab_slug = "genki-lesson-1"
            vocab_fallback = True
        _ = await _run_test(
            "get_vocab_items",
            lambda: get_vocab_items(vocab_slug),
            lambda _: f"slug={vocab_slug}{' (fallback)' if vocab_fallback else ''}",
        )

        _ = await _run_test(
            "get_reading_passages",
            get_reading_passages,
            _reading_passage_summary,
        )
        _ = await _run_test(
            "search_reading_passages('vacation')",
            lambda: search_reading_passages("vacation"),
            lambda payload: _search_result_summary(payload),
        )

        _ = await _run_test(
            "get_user_stats",
            get_user_stats,
            lambda payload: _list_length_summary(payload, "activity"),
        )
        _ = await _run_test(
            "get_jlpt_progress",
            get_jlpt_progress,
            lambda payload: _list_length_summary(payload, "srs_overview"),
        )
        _ = await _run_test(
            "get_srs_forecast('daily')",
            lambda: get_srs_forecast("daily"),
            lambda payload: _list_length_summary(payload, "forecasts"),
        )

        _ = await _run_test(
            "get_study_configuration",
            get_study_configuration,
            _queue_summary,
        )
        _ = await _run_test(
            "get_due_count",
            get_due_count,
            _due_summary,
        )

    duration = time.monotonic() - start_time
    record_summary(duration)
    _append_to_log(lines)
    executed = counts["PASS"] + counts["FAIL"]
    success = counts["FAIL"] == 0 and executed == EXPECTED_TESTS
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
