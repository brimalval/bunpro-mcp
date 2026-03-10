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
    """Search Bunpro's grammar database for Japanese grammar points.

    Queries Bunpro's search endpoint to find grammar points matching the given
    text. Results include grammar point titles, slugs, and excerpts for discovery.

    Use this tool when you need to:
    - Find grammar points by Japanese or English keywords (e.g., "particles", "て-form")
    - Discover available grammar structures for a topic
    - Get slugs/IDs for use with get_grammar_point()
    - Browse grammar before diving into detailed explanations

    Args:
        query: Search term in Japanese or English. Examples: "particles",
            "conditional", "potential form", "ために", "〜たい"

    Returns:
        A dictionary containing:
        - query: The original search query
        - results: List of up to 40 matching grammar points, each with:
            - id: Grammar point identifier
            - slug: URL-friendly identifier for get_grammar_point()
            - title: Grammar point name (Japanese/English)
            - excerpt: Brief description or usage example
            - type: Always "grammar" for these results
        - meta: Additional search metadata

    Related tools: get_grammar_point (for full details on a specific grammar point)
    """

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
    """Retrieve detailed information about a specific Japanese grammar point.

    Fetches the complete grammar point data including explanations, structure,
    example sentences, and usage notes. Accepts either a numeric ID or a
    text slug (which will be resolved via search first).

    Use this tool when you need to:
    - Get the full explanation of a grammar point
    - See example sentences using the grammar structure
    - Understand meaning nuances and usage contexts
    - Review detailed Japanese grammar patterns

    Args:
        slug: Either a numeric grammar point ID (e.g., "123") or a text slug
            (e.g., "particles-1", "te-form"). If a non-numeric slug is provided,
            it will be searched first to resolve the ID.

    Returns:
        A dictionary containing:
        - id: Grammar point identifier
        - slug: URL-friendly identifier
        - title: Grammar point name
        - grammar_point: Core grammar data with explanations
        - examples: List of example sentences demonstrating usage
        - meanings: List of meaning/nuance explanations
        - meta: Additional metadata from Bunpro

    Raises:
        RuntimeError: If the grammar point cannot be found or Bunpro search
            is unavailable when resolving a text slug.

    Related tools: search_grammar (to find grammar point slugs/IDs)
    """
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
