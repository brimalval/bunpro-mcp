from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Final, cast

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from src.api_client import (
    BunproClient,
    BunproNotFoundError,
    BunproUnexpectedStatusError,
)
from src.types.bunpro import BunproGrammarPointResponse, BunproSearchResponse

_SEARCH_RESULT_LIMIT: Final[int] = 40
_SEARCH_PATH: Final[str] = "/search/v1_1"
_GRAMMAR_DETAIL_PATH: Final[str] = "/reviewables/grammar_point"
_SEARCH_UNAVAILABLE_ERROR: Final[str] = (
    "Bunpro grammar search is unavailable; provide a numeric grammar ID instead"
)


@asynccontextmanager
async def _bunpro_client() -> AsyncGenerator[BunproClient, None]:
    client = BunproClient()
    try:
        yield client
    finally:
        await client.aclose()


def _trim_results(payload: dict[str, object], limit: int) -> dict[str, object]:
    results = payload.get("results")
    if isinstance(results, list):
        return {**payload, "results": results[:limit]}
    return payload


def _extract_grammar_id_from_entry(entry: object) -> str | None:
    if not isinstance(entry, dict):
        return None
    entry_dict = cast(dict[str, object], entry)
    for key in ("grammar_point_id", "reviewable_id", "id"):
        value = entry_dict.get(key)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str) and value.isdigit():
            return value
    return None


def _resolve_grammar_id(payload: dict[str, object], query: str) -> str:
    results = payload.get("results")
    if isinstance(results, list):
        for entry in cast(list[object], results):
            grammar_id = _extract_grammar_id_from_entry(entry)
            if grammar_id:
                return grammar_id
    raise RuntimeError(
        f"Could not resolve a grammar point ID for query {query!r} from Bunpro search results"
    )


async def search_grammar(query: str) -> dict[str, object]:
    """Search Bunpro grammar via /search/v1_1 and return results truncated to 40 entries."""

    payload: object
    async with _bunpro_client() as client:
        try:
            payload = await client.request_json(
                "POST", _SEARCH_PATH, json={"query": query}
            )
        except BunproNotFoundError:
            payload = {"query": query, "results": []}
        except BunproUnexpectedStatusError as exc:
            if str(exc) != "Unexpected status 500":
                raise
            payload = {"query": query, "results": []}

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro grammar search payload shape")

    trimmed_payload = _trim_results(
        cast(dict[str, object], payload), _SEARCH_RESULT_LIMIT
    )
    try:
        validated = BunproSearchResponse.model_validate(trimmed_payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro grammar search payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def get_grammar_point(slug: str) -> dict[str, object]:
    """Resolve a grammar ID via search and fetch detail from GET /reviewables/grammar_point/{grammarId}."""
    grammar_id: str
    if slug.isdigit():
        grammar_id = slug
    else:
        search_payload = await search_grammar(slug)
        try:
            grammar_id = _resolve_grammar_id(search_payload, slug)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Could not resolve grammar point for {slug!r}. {_SEARCH_UNAVAILABLE_ERROR}."
            ) from exc

    async with _bunpro_client() as client:
        payload = await client.request_json(
            "GET", f"{_GRAMMAR_DETAIL_PATH}/{grammar_id}"
        )

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro grammar detail payload shape")

    try:
        validated = BunproGrammarPointResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro grammar detail payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


def register_grammar_tools(mcp: FastMCP) -> None:
    """Register Bunpro grammar tools on the MCP instance."""
    _ = mcp.tool()(search_grammar)
    _ = mcp.tool()(get_grammar_point)
