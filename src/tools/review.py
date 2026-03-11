from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Final

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from src.api_client import BunproClient, resolve_frontend_api_token
from src.types.bunpro import (
    BunproDueResponse,
    BunproQueueResponse,
    BunproQuizIndexResponse,
)
from src.cache import get_pending_reviews_cache

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


async def get_study_configuration() -> dict[str, object]:
    """Get user's deck and study configuration settings.

    QUICK REFERENCE:
    - Want deck settings? → Use get_study_configuration()  ← YOU ARE HERE
    - Want due counts only? → Use get_due_count()
    - Want actual items to review? → Use get_pending_reviews()

    IMPORTANT: This does NOT return a list of review items. It returns deck
    configuration including batch sizes, sorting order, and study preferences.

    Use this tool when you need to:
    - Check deck batch sizes for review sessions
    - View sorting preferences (default, oldest first, etc.)
    - See daily goals and completion progress
    - Access default SRS levels for new items
    - Check study settings across different decks

    Args:
        None

    Returns:
        A dictionary containing deck settings for each deck:
        - batch_size: Number of items per review session
        - default_srs_level: SRS level for new items
        - sorting_order: Review sorting preference
        - default_input_type_*: Input type (Cloze/Multiple Choice)
        - complete_*_count: Completed items per deck
        - daily_goal: Daily review goal
        - daily_goal_count_*: Progress toward daily goal

    Related tools:
    - get_due_count(): For summary statistics of due items (NOT actual items)
    - get_pending_reviews(): For actual items pending review with full details
    """

    async with _bunpro_client() as client:
        payload = await client.request_json("GET", _REVIEW_QUEUE_PATH)

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro review queue payload shape")

    try:
        validated = BunproQueueResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro review queue payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def get_due_count() -> dict[str, object]:
    """Get count of items currently due for review.

    QUICK REFERENCE:
    - Want deck settings? → Use get_study_configuration()
    - Want due counts only? → Use get_due_count()  ← YOU ARE HERE
    - Want actual items to review? → Use get_pending_reviews()

    IMPORTANT: This returns COUNTS ONLY, not actual items. For detailed
    review items with content, use get_pending_reviews().

    Use this tool when you need to:
    - Get quick summary of review workload
    - Check how many items are due without fetching details
    - See breakdown by type (grammar vs vocab)
    - Plan study session length based on item count

    Args:
        None

    Returns:
        A dictionary containing summary statistics:
        - total_due_grammar: Number of grammar items due
        - total_due_vocab: Number of vocabulary items due

    Related tools:
    - get_study_configuration(): For deck configuration settings
    - get_pending_reviews(): For actual items pending review with full details
    - get_srs_forecast(): For upcoming review schedule
    """

    async with _bunpro_client() as client:
        payload = await client.request_json("GET", _DUE_ITEMS_PATH)

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro due items payload shape")

    try:
        validated = BunproDueResponse.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro due items payload") from exc

    return validated.model_dump(mode="json", exclude_unset=True)


async def get_pending_reviews() -> dict[str, object]:
    """Get pending review items with full details.

    QUICK REFERENCE:
    - Want deck settings? → Use get_study_configuration()
    - Want due counts only? → Use get_due_count()
    - Want actual items to review? → Use get_pending_reviews()  ← YOU ARE HERE

    Returns actual items ready for review, including study questions,
    answers, and context. This is the primary tool for accessing content
    that needs to be reviewed.

    Use this tool when you need to:
    - Get actual items to review with full content
    - See study questions and correct answers
    - Access example sentences and audio
    - Review detailed vocab/grammar information
    - Resume an interrupted review session

    Args:
        None

    Returns:
        A dictionary containing:
        - review_session_id: Identifier for the active session (if any)
        - pending_attempt: List of pending review items, each with:
            - study_question: The question/prompt with cloze input
            - answer: Correct answer
            - kanji_answer: Answer with kanji
            - nuance: Grammar/vocab nuance explanation
            - translation: English translation
            - audio_url: Pronunciation audio link
            - reviewable: Full vocab/grammar details
        - pending_wrapup: List of pending wrap-up payloads
        - total_pending_attempt_count: Count of pending attempts
        - total_pending_wrapup_count: Count of pending wrap-ups

    Related tools:
    - get_study_configuration(): For deck configuration settings
    - get_due_count(): For summary statistics only (NOT actual items)
    """

    async def _fetch_reviews() -> dict[str, object]:
        async with _bunpro_client() as client:
            payload = await client.request_json("GET", _QUIZ_INDEX_PATH)

        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected Bunpro quiz index payload shape")

        try:
            validated = BunproQuizIndexResponse.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError("Invalid Bunpro quiz index payload") from exc

        return validated.model_dump(mode="json", exclude_unset=True)

    token = resolve_frontend_api_token()
    if not token:
        return await _fetch_reviews()

    cache = get_pending_reviews_cache()
    cached = cache.get(token)
    if isinstance(cached, dict):
        return cached

    async with cache.lock_for(token):
        cached = cache.get(token)
        if isinstance(cached, dict):
            return cached

        result = await _fetch_reviews()
        cache.set(token, result)
        return result


def register_review_tools(mcp: FastMCP) -> None:
    """Register Bunpro review tools on the MCP instance."""

    _ = mcp.tool()(get_study_configuration)
    _ = mcp.tool()(get_due_count)
    _ = mcp.tool()(get_pending_reviews)
