from __future__ import annotations

from typing import Callable

import httpx


ResponseHandler = Callable[[httpx.Request], httpx.Response]


def make_mock_async_client(
    handler: ResponseHandler,
    base_url: str = "http://test",
) -> httpx.AsyncClient:
    """Return an AsyncClient backed by an httpx.MockTransport."""

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url=base_url, transport=transport)
