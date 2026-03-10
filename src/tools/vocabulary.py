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


def _is_search_fallback_error(error: BunproUnexpectedStatusError) -> bool:
    return str(error) == "Unexpected status 500"


def _first_string(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    for item in cast(list[object], value):
        if isinstance(item, str) and item:
            return item
    return None


def _build_vocab_fallback_hit(
    query: str, payload: dict[str, object]
) -> dict[str, object]:
    vocab = payload.get("vocab")
    vocab_data = cast(dict[str, object], vocab) if isinstance(vocab, dict) else {}
    title = _first_string(vocab_data.get("japanese")) or query
    excerpt = _first_string(vocab_data.get("english"))
    slug = payload.get("slug") or vocab_data.get("slug") or query
    hit_id = payload.get("id") or vocab_data.get("id") or slug

    return {
        "id": hit_id,
        "slug": slug,
        "type": "vocab",
        "title": title,
        "excerpt": excerpt,
        "meta": {"source": "reviewables/vocab"},
        "vocab_detail": payload,
    }


async def _search_vocab_fallback_payload(
    client: BunproClient, query: str
) -> dict[str, object]:
    try:
        vocab_payload = await client.request_json(
            "GET", f"{_VOCAB_DETAIL_PATH}/{query}"
        )
    except BunproNotFoundError:
        return {"query": query, "results": []}

    if not isinstance(vocab_payload, dict):
        raise RuntimeError("Unexpected Bunpro vocabulary payload shape")

    vocab_payload_dict = cast(dict[str, object], vocab_payload)
    return {
        "query": query,
        "results": [_build_vocab_fallback_hit(query, vocab_payload_dict)],
    }


async def get_vocab_level() -> dict[str, object]:
    """Get vocabulary progress by JLPT level.

    Retrieves vocabulary learning progress broken down by JLPT level (N5-N1).
    This shows how many vocabulary items have been learned at each proficiency
    level.

    Use this tool when you need to:
    - Check vocabulary progress by JLPT level
    - See which JLPT level to focus vocabulary study on
    - Track vocabulary acquisition across proficiency levels
    - Get an overview of vocabulary SRS distribution

    Args:
        None

    Returns:
        A dictionary containing:
        - summary: Overall vocabulary statistics
        - srs_overview: Vocabulary items grouped by JLPT level and SRS stage
        - activity: Recent vocabulary-related activity
        - meta: Additional JLPT vocabulary metadata

    Note:
        JLPT levels range from N5 (beginner) to N1 (advanced). This endpoint
        focuses on vocabulary specifically, not grammar.

    Related tools: get_jlpt_progress, search_vocab, get_vocab_items
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
    """Retrieve detailed information about a specific vocabulary word.

    Fetches complete vocabulary data including Japanese forms, English meanings,
    readings, example sentences, and audio URL. Use this to get full details
    about a vocabulary item found via search.

    Use this tool when you need to:
    - Get full details for a vocabulary word
    - See example sentences using the vocabulary
    - Access audio pronunciation URL
    - Review context and usage for a word

    Args:
        vocab_slug_or_id: The vocabulary slug (e.g., "genki-lesson-1") or
            numeric ID from search results.

    Returns:
        A dictionary containing:
        - vocab: Primary vocabulary definition with:
            - slug: URL-friendly identifier
            - japanese: List of Japanese forms (kanji/kana)
            - english: List of English definitions
            - readings: List of reading variants
            - level: JLPT level or deck identifier
            - audio_url: Link to pronunciation audio (if available)
            - contexts: Context sentences showing usage
        - examples: Additional example sentences
        - glossary: Auxiliary lookup metadata

    Related tools: search_vocab (to find vocabulary slugs/IDs)
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
    """Search Bunpro's vocabulary database for Japanese words.

    Queries Bunpro's search endpoint to find vocabulary matching the given
    text. Results include Japanese forms, English meanings, and slugs for
    retrieving full details.

    Use this tool when you need to:
    - Find vocabulary by Japanese or English (e.g., "hello", "こんにちは")
    - Discover vocabulary in a specific deck or lesson
    - Get slugs/IDs for use with get_vocab_items()
    - Browse vocabulary before viewing full details

    Args:
        query: Search term in Japanese or English. Can include kanji, kana,
            romaji, or English definitions.
        result_limit: Maximum number of results to return (default: 40, max: 50).
            Values outside 1-50 are clamped to valid range.

    Returns:
        A dictionary containing:
        - query: The original search query
        - results: List of matching vocabulary items, each with:
            - id: Vocabulary identifier
            - slug: URL-friendly identifier for get_vocab_items()
            - title: Primary Japanese form
            - excerpt: English definition(s)
            - type: Always "vocab" for these results
            - score: Relevance score
        - meta: Additional search metadata

    Related tools: get_vocab_items (for full details on a specific word),
        get_vocab_level (for JLPT progress)
    """

    limit = _normalize_limit(result_limit)
    async with _bunpro_client() as client:
        try:
            payload = await client.request_json(
                "POST", _SEARCH_PATH, json={"query": query}
            )
        except BunproNotFoundError:
            payload = await _search_vocab_fallback_payload(client, query)
        except BunproUnexpectedStatusError as exc:
            if not _is_search_fallback_error(exc):
                raise
            payload = await _search_vocab_fallback_payload(client, query)

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
