from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Final

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from src.api_client import BunproClient
from src.types.bunpro import (
    BunproDueResponse,
    BunproQueueResponse,
    BunproQuizIndexResponse,
)

_REVIEW_QUEUE_PATH: Final[str] = "/user/queue"
_DUE_ITEMS_PATH: Final[str] = "/user/due"
_QUIZ_INDEX_PATH: Final[str] = "/reviews/quiz_index"


@asynccontextmanager
async def _bunpro_client() -> AsyncGenerator[BunproClient, None]:
    client = BunproClient()
    try:
        yield client
    finally:
        await client.aclose()


async def get_review_queue() -> dict[str, object]:
    """Return the `/user/queue` payload from Bunpro."""

    async with _bunpro_client() as client:
        payload = await client.request_json("GET", _REVIEW_QUEUE_PATH)

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro review queue payload shape")

    try:
        validated = BunproQueueResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro review queue payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def get_due_items() -> dict[str, object]:
    """Return the `/user/due` payload from Bunpro."""

    async with _bunpro_client() as client:
        payload = await client.request_json("GET", _DUE_ITEMS_PATH)

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro due items payload shape")

    try:
        validated = BunproDueResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro due items payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def get_quiz_index() -> dict[str, object]:
    """Return the `/reviews/quiz_index` payload from Bunpro."""

    async with _bunpro_client() as client:
        payload = await client.request_json("GET", _QUIZ_INDEX_PATH)

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro quiz index payload shape")

    try:
        validated = BunproQuizIndexResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro quiz index payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


def register_review_tools(mcp: FastMCP) -> None:
    """Register Bunpro review queue tools on the MCP instance."""

    _ = mcp.tool()(get_review_queue)
    _ = mcp.tool()(get_due_items)
    _ = mcp.tool()(get_quiz_index)
