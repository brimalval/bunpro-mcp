from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from collections.abc import Iterable

from src.tools.user_stats import get_user_stats

EVIDENCE_LOG = Path(".sisyphus/evidence/real-api-testing/test-00-token-validation.log")
TOKEN_SOURCES: tuple[str, ...] = ("BUNPRO_FRONTEND_API_TOKEN", "BUNPRO_JWT")


def _ensure_log_path() -> None:
    EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _iterate_tokens() -> Iterable[tuple[str, str]]:
    for key in TOKEN_SOURCES:
        value = os.environ.get(key)
        if value and value.strip():
            yield value.strip(), key


def main() -> int:
    _ensure_log_path()
    with EVIDENCE_LOG.open("a", encoding="utf-8") as log_fh:

        def _emit(message: str, *, error: bool = False) -> None:
            stream = sys.stderr if error else sys.stdout
            print(message, file=stream)
            _ = log_fh.write(message + "\n")
            _ = log_fh.flush()
            _ = stream.flush()

        token_source: str | None = None
        token_value: str | None = None
        for value, source in _iterate_tokens():
            token_value = value
            token_source = source
            break

        if not token_value or not token_source:
            _emit(
                "FAIL: Missing Bunpro token (set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT).",
                error=True,
            )
            return 1

        _emit(f"Token source: {token_source}")

        try:
            _ = asyncio.run(get_user_stats())
        except Exception as exc:
            message = f"FAIL: {exc.__class__.__name__}: {exc}"
            _emit(message, error=True)
            return 1

        _emit("PASS: get_user_stats() succeeded.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
