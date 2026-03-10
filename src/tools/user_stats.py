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
    """Return Bunpro base stats from /user_stats/base_stats."""
    return await _fetch_stats(_BASE_STATS_PATH, BunproUserStatsResponse)


async def get_jlpt_progress() -> dict[str, object]:
    """Return Bunpro mixed JLPT progress from /user_stats/jlpt_progress_mixed."""
    return await _fetch_stats(_JLPT_PROGRESS_PATH, BunproUserStatsResponse)


async def get_srs_forecast(
    granularity: Literal["daily", "hourly"] = "daily",
) -> dict[str, object]:
    """Return Bunpro SRS forecast for the requested granularity."""
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
