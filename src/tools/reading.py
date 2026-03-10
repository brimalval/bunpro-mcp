from __future__ import annotations

import json
import re
from typing import Final, cast

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from src.api_client import resolve_frontend_api_token
from src.types.bunpro import BunproReadingPassagesResponse, BunproSearchResponse

_READING_PASSAGES_PAGE_URL: Final[str] = "https://bunpro.jp/reading_passages"
_NEXT_DATA_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(?P<data>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_SEARCH_RESULT_LIMIT: Final[int] = 40


def _truncate_results(payload: dict[str, object], limit: int) -> dict[str, object]:
    results = payload.get("results")
    if isinstance(results, list):
        return {**payload, "results": results[:limit]}
    return payload


def _extract_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        list_result: list[str] = []
        for item in cast(list[object], value):
            list_result.extend(_extract_strings(item))
        return list_result
    if isinstance(value, dict):
        dict_result: list[str] = []
        for nested in cast(dict[str, object], value).values():
            dict_result.extend(_extract_strings(nested))
        return dict_result
    return []


def _as_object_dict(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    raw_dict = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_dict):
        return None
    return cast(dict[str, object], value)


def _pick_best_title(passage: dict[str, object]) -> str | None:
    for key in ("title", "name", "slug", "excerpt", "japanese", "english"):
        value = passage.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            for item in cast(list[object], value):
                if isinstance(item, str) and item.strip():
                    return item
    return None


def _search_hit_from_passage(passage: dict[str, object]) -> dict[str, object]:
    hit: dict[str, object] = {
        **passage,
        "id": passage.get("id"),
        "slug": cast(object, passage.get("slug")),
        "title": _pick_best_title(passage),
        "type": cast(object, passage.get("type") or "reading"),
    }
    excerpt = passage.get("excerpt")
    if isinstance(excerpt, str):
        hit["excerpt"] = excerpt
    return hit


async def _fetch_reading_passages() -> list[dict[str, object]]:
    token = resolve_frontend_api_token()
    if not token:
        raise RuntimeError(
            "Missing Bunpro auth token. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT."
        )

    headers = {"Cookie": f"frontend_api_token={token}"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:
            response = await client.get(_READING_PASSAGES_PAGE_URL, headers=headers)
    except httpx.HTTPError as exc:
        raise RuntimeError("Failed to fetch Bunpro reading passages page") from exc

    if response.is_error:
        raise RuntimeError(
            f"Failed to fetch Bunpro reading passages page (status {response.status_code})"
        )

    match = _NEXT_DATA_PATTERN.search(response.text)
    if match is None:
        raise RuntimeError(
            "Missing __NEXT_DATA__ payload on Bunpro reading passages page"
        )

    raw_data = match.group("data")
    try:
        loaded_data = cast(object, json.loads(raw_data))
        next_data = _as_object_dict(loaded_data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid __NEXT_DATA__ JSON payload for reading passages"
        ) from exc
    if next_data is None:
        raise RuntimeError("Invalid __NEXT_DATA__ JSON payload for reading passages")

    props = _as_object_dict(next_data.get("props"))
    if props is None:
        raise RuntimeError("Invalid __NEXT_DATA__ payload: missing props")

    page_props = _as_object_dict(props.get("pageProps"))
    if page_props is None:
        raise RuntimeError("Invalid __NEXT_DATA__ payload: missing pageProps")

    passages = page_props.get("readingPassages")
    if not isinstance(passages, list):
        raise RuntimeError("Invalid __NEXT_DATA__ payload: missing readingPassages")

    normalized: list[dict[str, object]] = []
    for item in cast(list[object], passages):
        if isinstance(item, dict):
            normalized.append(cast(dict[str, object], item))
    return normalized


async def get_reading_passages() -> dict[str, object]:
    passages = await _fetch_reading_passages()
    payload: dict[str, object] = {"results": passages}

    try:
        validated = BunproReadingPassagesResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro reading passages payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def search_reading_passages(query: str) -> dict[str, object]:
    passages = await _fetch_reading_passages()
    normalized_query = query.casefold()
    filtered_results = [
        _search_hit_from_passage(passage)
        for passage in passages
        if normalized_query in "\n".join(_extract_strings(passage)).casefold()
    ]
    payload: dict[str, object] = {
        "query": query,
        "results": filtered_results,
    }
    truncated_payload = _truncate_results(payload, _SEARCH_RESULT_LIMIT)
    try:
        validated = BunproSearchResponse.model_validate(truncated_payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro reading search payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


def register_reading_tools(mcp: FastMCP) -> None:
    """Register Bunpro reading tools on the MCP instance."""

    _ = mcp.tool()(get_reading_passages)
    _ = mcp.tool()(search_reading_passages)
