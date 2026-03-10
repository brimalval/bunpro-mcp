from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Final, cast

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from src.api_client import BunproClient
from src.types.bunpro import (
    BunproSearchResponse,
    BunproUserStatsResponse,
    BunproVocabResponse,
)

_SEARCH_RESULT_LIMIT: Final[int] = 40
_MAX_SEARCH_RESULT_LIMIT: Final[int] = 50
_VOCAB_DETAIL_PATH: Final[str] = "/reviewables/vocab"
_SEARCH_PATH: Final[str] = "/search/v1_1"


@asynccontextmanager
async def _bunpro_client() -> AsyncGenerator[BunproClient, None]:
    client = BunproClient()
    try:
        yield client
    finally:
        await client.aclose()


def _normalize_limit(requested: int | None) -> int:
    normalized = requested if requested is not None else _SEARCH_RESULT_LIMIT
    if normalized < 1:
        normalized = 1
    if normalized > _MAX_SEARCH_RESULT_LIMIT:
        normalized = _MAX_SEARCH_RESULT_LIMIT
    return normalized


def _trim_results(payload: dict[str, object], limit: int) -> dict[str, object]:
    results = payload.get("results")
    if isinstance(results, list):
        return {**payload, "results": results[:limit]}
    return payload


async def get_vocab_level() -> dict[str, object]:
    """Return the mixed JLPT progress payload from Bunpro.

    The pinned Bunpro spec exposes /user_stats/jlpt_progress_mixed, which is
    the closest available representation of the overall JLPT level data.
    """

    async with _bunpro_client() as client:
        payload = await client.request_json("GET", "/user_stats/jlpt_progress_mixed")

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro JLPT progress payload shape")

    try:
        validated = BunproUserStatsResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro JLPT progress payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def get_vocab_items(vocab_slug_or_id: str) -> dict[str, object]:
    """Return the Bunpro vocabulary detail payload for the given slug or id.

    Args:
        vocab_slug_or_id: The Bunpro vocabulary slug or numeric identifier.

    Returns:
        The raw JSON dictionary returned by /reviewables/vocab/{slugOrId}.
    """

    async with _bunpro_client() as client:
        payload = await client.request_json(
            "GET", f"{_VOCAB_DETAIL_PATH}/{vocab_slug_or_id}"
        )

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro vocabulary payload shape")

    try:
        validated = BunproVocabResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro vocabulary payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def search_vocab(
    query: str, result_limit: int | None = None
) -> dict[str, object]:
    """Search Bunpro vocabulary using the pinned /search/v1_1 endpoint.

    Args:
        query: Free-text query to submit to Bunpro (case-sensitive).
        result_limit: Optional cap on the number of entries in the `results` list;
            values above 50 are clamped, values below 1 are raised to 1.

    Returns:
        The Bunpro search JSON dictionary with `results` truncated to the requested limit.
    """

    limit = _normalize_limit(result_limit)
    async with _bunpro_client() as client:
        payload = await client.request_json("POST", _SEARCH_PATH, json={"query": query})

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro search payload shape")

    trimmed_payload = _trim_results(cast(dict[str, object], payload), limit)
    try:
        validated = BunproSearchResponse.model_validate(trimmed_payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro search payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


def register_vocab_tools(mcp: FastMCP) -> None:
    """Register Bunpro vocabulary tools on the MCP instance."""

    _ = mcp.tool()(get_vocab_level)
    _ = mcp.tool()(get_vocab_items)
    _ = mcp.tool()(search_vocab)
