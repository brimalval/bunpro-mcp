from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token
import logging
import os
from typing import TypeAlias, cast

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.bunpro.jp/api/frontend"
REQUEST_FRONTEND_API_TOKEN: ContextVar[str | None] = ContextVar(
    "request_frontend_api_token", default=None
)

JSONPayload: TypeAlias = (
    dict[str, object] | list[object] | str | int | float | bool | None
)


class BunproClientError(Exception):
    """Generic client error."""


class BunproAuthenticationError(BunproClientError):
    """Raised when Bunpro returns an authentication failure."""


class BunproNotFoundError(BunproClientError):
    """Raised when the requested resource cannot be found."""


class BunproUnexpectedStatusError(BunproClientError):
    """Raised when Bunpro responds with an unexpected status."""


class BunproClient:
    """Async Bunpro HTTP client.

    Designed to cover Bunpro API shards such as /user/due, /user/queue,
    /user_stats/base_stats, /reviewables/vocab/{slugOrId}, and /search/v1_1.
    """

    def __init__(
        self,
        base_url: str | None = None,
        jwt: str | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> None:
        base_url_value = (
            base_url or os.environ.get("BUNPRO_API_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        token_value = _resolve_frontend_api_token(jwt)
        if not token_value:
            raise RuntimeError(
                "Missing Bunpro auth token. Set BUNPRO_FRONTEND_API_TOKEN or BUNPRO_JWT."
            )

        self.base_url: str = base_url_value
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Token token={token_value}"},
            timeout=timeout or httpx.Timeout(10.0, read=30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: JSONPayload | None = None,
    ) -> object:
        """Perform a Bunpro request and return the parsed JSON response."""

        normalized_path = path.lstrip("/")
        logger.debug(
            "Bunpro request %s %s params=%s", method.upper(), normalized_path, params
        )
        try:
            response = await self._client.request(
                method.upper(), normalized_path, params=params, json=json
            )
        except httpx.HTTPError as exc:
            raise BunproClientError("Bunpro request failed") from exc

        logger.debug("Bunpro response %s %s", response.status_code, response.url.path)
        if response.is_error:
            self._raise_for_status(response)

        return cast(object, response.json())

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status in {401, 403}:
            raise BunproAuthenticationError("Authentication failed")
        if status == 404:
            raise BunproNotFoundError("Resource not found")
        raise BunproUnexpectedStatusError(f"Unexpected status {status}")

    async def aclose(self) -> None:
        """Close the internal HTTP client."""

        await self._client.aclose()


def set_request_frontend_api_token(value: str | None) -> Token[str | None]:
    normalized = value.strip() if value and value.strip() else None
    return REQUEST_FRONTEND_API_TOKEN.set(normalized)


def reset_request_frontend_api_token(token: Token[str | None]) -> None:
    REQUEST_FRONTEND_API_TOKEN.reset(token)


def resolve_frontend_api_token(jwt: str | None = None) -> str | None:
    return _resolve_frontend_api_token(jwt)


def _resolve_frontend_api_token(jwt: str | None) -> str | None:
    request_token = REQUEST_FRONTEND_API_TOKEN.get()
    if request_token:
        return request_token

    if jwt and jwt.strip():
        return jwt.strip()

    env_token = os.environ.get("BUNPRO_FRONTEND_API_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    legacy_env_token = os.environ.get("BUNPRO_JWT")
    if legacy_env_token and legacy_env_token.strip():
        return legacy_env_token.strip()

    return None
