from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Final, Literal, TypeVar, cast

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError

from src.api_client import BunproClient
from src.types.bunpro import BunproUserStatsResponse

_FORECAST_PATHS: Final[dict[Literal["daily", "hourly"], str]] = {
    "daily": "/user_stats/forecast_daily",
    "hourly": "/user_stats/forecast_hourly",
}

_BASE_STATS_PATH: Final[str] = "/user_stats/base_stats"
_JLPT_PROGRESS_PATH: Final[str] = "/user_stats/jlpt_progress_mixed"
ModelT = TypeVar("ModelT", bound=BaseModel)


@asynccontextmanager
async def _bunpro_client() -> AsyncGenerator[BunproClient, None]:
    client = BunproClient()
    try:
        yield client
    finally:
        await client.aclose()


async def _fetch_stats(endpoint: str, model: type[ModelT]) -> dict[str, object]:
    async with _bunpro_client() as client:
        payload = await client.request_json("GET", endpoint)

    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Bunpro payload shape")

    try:
        validated = model.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError("Invalid Bunpro payload shape") from exc

    return cast(
        dict[str, object], validated.model_dump(mode="json", exclude_unset=True)
    )


async def get_user_stats() -> dict[str, object]:
    """Get comprehensive user statistics from Bunpro.

    Retrieves base statistics including review counts, streaks, SRS distribution,
    and recent activity. This is the primary overview of user progress.

    Use this tool when you need to:
    - Get an overview of user's learning progress
    - Check current streak and review statistics
    - See SRS level distribution across all content
    - Review recent study activity

    Args:
        None

    Returns:
        A dictionary containing:
        - summary: Top-level statistics including:
            - Total reviews completed
            - Current streak
            - Items at each SRS level
        - srs_overview: List of SRS level buckets, each with:
            - level: SRS stage name
            - count: Number of items in this stage
            - percent: Percentage share
        - activity: Recent activity timeline with reviews/lessons per period
        - meta: Additional statistics metadata

    Related tools: get_jlpt_progress, get_srs_forecast, get_study_configuration
    """
    return await _fetch_stats(_BASE_STATS_PATH, BunproUserStatsResponse)


async def get_jlpt_progress() -> dict[str, object]:
    """Get JLPT (Japanese Language Proficiency Test) level progress.

    Retrieves progress breakdown by JLPT level (N5 through N1), showing how
    much vocabulary and grammar the user has learned at each level.

    Use this tool when you need to:
    - Check progress toward a specific JLPT level
    - See vocabulary/grammar distribution across JLPT levels
    - Identify which level to focus on next
    - Track overall Japanese proficiency progression

    Args:
        None

    Returns:
        A dictionary containing JLPT progress data including:
        - summary: Overall progress statistics
        - srs_overview: Items grouped by JLPT level and SRS stage
        - activity: Recent activity broken down by level
        - meta: Additional JLPT-specific metadata

    Note:
        JLPT levels range from N5 (beginner) to N1 (advanced).

    Related tools: get_user_stats, get_vocab_level
    """
    return await _fetch_stats(_JLPT_PROGRESS_PATH, BunproUserStatsResponse)


async def get_srs_forecast(
    granularity: Literal["daily", "hourly"] = "daily",
) -> dict[str, object]:
    """Get Spaced Repetition System (SRS) review forecast.

    Predicts how many reviews will be due at future time points. Use this to
    plan study sessions and understand upcoming workload.

    Use this tool when you need to:
    - Plan when to study based on upcoming review load
    - See review distribution over the next hours/days
    - Identify peak review times
    - Understand SRS scheduling patterns

    Args:
        granularity: Time resolution for the forecast.
            - "daily": Forecast by day (default, covers more time)
            - "hourly": Forecast by hour (more granular, shorter range)

    Returns:
        A dictionary containing:
        - forecasts: List of forecast points, each with:
            - timestamp: When this forecast applies
            - reviews: Projected number of reviews due
            - lessons: Projected number of lessons (if available)
        - meta: Additional forecast metadata

    Raises:
        ValueError: If granularity is not "daily" or "hourly".

    Related tools: get_study_configuration, get_due_count, get_user_stats
    """
    try:
        endpoint = _FORECAST_PATHS[granularity]
    except KeyError as exc:
        raise ValueError("granularity must be 'daily' or 'hourly'") from exc

    return await _fetch_stats(endpoint, BunproUserStatsResponse)


def register_user_stats_tools(mcp: FastMCP) -> None:
    """Register Bunpro user stats tools on the MCP instance."""
    _ = mcp.tool()(get_user_stats)
    _ = mcp.tool()(get_jlpt_progress)
    _ = mcp.tool()(get_srs_forecast)
