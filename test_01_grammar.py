from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TextIO, cast

from src.tools.grammar import search_grammar

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-01-grammar.log")
QUERIES: tuple[tuple[str, str], ...] = (
    ("English", "particles"),
    ("Japanese", "は"),
    ("Romaji", "desu"),
)


def _ensure_log_path() -> None:
    EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _build_snippet(hit: dict[str, object]) -> str:
    parts: list[str] = []
    for key in ("title", "slug", "type", "level"):
        value = hit.get(key)
        if isinstance(value, str) and value:
            parts.append(f"{key}={value}")
    meta = hit.get("meta")
    if isinstance(meta, dict):
        meta_dict = cast(dict[str, object], meta)
        level = meta_dict.get("level")
        if isinstance(level, str) and level:
            tag = f"meta.level={level}"
            if tag not in parts:
                parts.append(tag)
    if not parts:
        return "first hit missing metadata"
    return "; ".join(parts)


def _emit(message: str, *, log_fh: TextIO, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream)
    _ = log_fh.write(message + "\n")
    _ = log_fh.flush()
    _ = stream.flush()


async def _run_single(label: str, query: str, log_fh: TextIO) -> tuple[bool, bool]:
    try:
        payload = await search_grammar(query)
    except RuntimeError as exc:
        message = str(exc)
        if "Missing Bunpro auth token" in message:
            _emit(
                f"FAIL {label} grammar search ({query}) - Missing Bunpro auth token. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT.",
                log_fh=log_fh,
                error=True,
            )
            return False, True
        _emit(
            f"FAIL {label} grammar search ({query}) - {exc.__class__.__name__}: {message}",
            log_fh=log_fh,
            error=True,
        )
        return False, False
    except Exception as exc:
        _emit(
            f"FAIL {label} grammar search ({query}) - {exc.__class__.__name__}: {exc}",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        _emit(
            f"FAIL {label} grammar search ({query}) - results missing or malformed",
            log_fh=log_fh,
            error=True,
        )
        return False, False

    results = cast(list[dict[str, object]], raw_results)

    if not results:
        _emit(
            f"WARN {label} grammar search ({query}) - no hits returned",
            log_fh=log_fh,
        )
        return True, False

    first_hit = results[0]
    snippet = _build_snippet(first_hit)
    _emit(
        f"PASS {label} grammar search ({query}) - first hit: {snippet}", log_fh=log_fh
    )
    return True, False


async def _run_all(log_fh: TextIO) -> tuple[bool, bool]:
    all_passed = True
    missing_token = False
    for label, query in QUERIES:
        passed, token_missing = await _run_single(label, query, log_fh)
        if token_missing:
            missing_token = True
            all_passed = False
            break
        if not passed:
            all_passed = False
    return all_passed, missing_token


def main() -> int:
    _ensure_log_path()
    with EVIDENCE_LOG.open("a", encoding="utf-8") as log_fh:
        all_passed, missing_token = asyncio.run(_run_all(log_fh))
        if missing_token:
            return 1
        return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
