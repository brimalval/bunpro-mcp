from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

# pyright: reportMissingImports=false, reportUnknownParameterType=false, reportUnknownVariableType=false
import httpx
import pytest

from src.api_client import (
    BunproClient,
    BunproAuthenticationError,
    BunproNotFoundError,
    BunproUnexpectedStatusError,
    reset_request_frontend_api_token,
    set_request_frontend_api_token,
)
from src.tools.grammar import get_grammar_point, search_grammar
from src.tools.vocabulary import search_vocab


def _install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    real_async_client = httpx.AsyncClient
    monkeypatch.setenv("BUNPRO_JWT", "dummy")
    monkeypatch.setenv("BUNPRO_API_BASE_URL", "http://test")

    def _mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        return real_async_client(
            base_url=str(kwargs.get("base_url", "http://test")),
            transport=httpx.MockTransport(handler),
            headers=cast(dict[str, str], kwargs.get("headers", {})),
        )

    monkeypatch.setattr(httpx, "AsyncClient", _mock_async_client)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error_cls"),
    [
        (401, BunproAuthenticationError),
        (403, BunproAuthenticationError),
        (404, BunproNotFoundError),
        (502, BunproUnexpectedStatusError),
    ],
)
async def test_search_vocab_raises_for_error_statuses(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    error_cls: type[Exception],
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        return httpx.Response(status, json={"error": "failed"})

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(error_cls):
        _ = await search_vocab("本")


@pytest.mark.asyncio
async def test_get_grammar_point_propagates_detail_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        if request.url.path == "/reviewables/grammar_point/123":
            return httpx.Response(404, json={"error": "missing"})
        return httpx.Response(500, json={"error": "unexpected"})

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(BunproNotFoundError):
        _ = await get_grammar_point("123")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 500])
async def test_search_grammar_falls_back_to_empty_results_for_known_failures(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        if request.url.path == "/search/v1_1":
            return httpx.Response(status, json={"error": "failed"})
        return httpx.Response(500, json={"error": "unexpected"})

    _install_mock_transport(monkeypatch, _handler)

    payload = await search_grammar("〜ない")

    assert payload["query"] == "〜ない"
    assert payload["results"] == []


@pytest.mark.asyncio
async def test_get_grammar_point_non_numeric_raises_clear_id_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        if request.url.path == "/search/v1_1":
            return httpx.Response(500, json={"error": "failed"})
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(RuntimeError, match="provide a numeric grammar ID instead"):
        _ = await get_grammar_point("〜ない")


@pytest.mark.asyncio
async def test_japanese_queries_are_passed_without_corruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_queries: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        if request.url.path == "/search/v1_1":
            body = cast(dict[str, str], json.loads(request.content.decode("utf-8")))
            seen_queries.append(body["query"])
            return httpx.Response(200, json={"results": []})
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, _handler)

    _ = await search_vocab("本")
    _ = await search_grammar("〜ない")

    assert seen_queries == ["本", "〜ない"]


@pytest.mark.asyncio
async def test_request_token_context_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_headers: dict[str, str] = {}
    real_async_client = httpx.AsyncClient

    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "env-token")
    monkeypatch.setenv("BUNPRO_JWT", "legacy-token")

    def _mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        headers = cast(dict[str, str], kwargs.get("headers", {}))
        captured_headers.update(headers)
        return real_async_client(
            base_url=str(kwargs.get("base_url", "http://test")),
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"ok": True})
            ),
            headers=headers,
        )

    monkeypatch.setattr(httpx, "AsyncClient", _mock_async_client)

    token = set_request_frontend_api_token("cookie-token")
    try:
        client = BunproClient(base_url="http://test")
    finally:
        reset_request_frontend_api_token(token)

    assert captured_headers["Authorization"] == "Token token=cookie-token"
    await client.aclose()
