from __future__ import annotations

from collections.abc import Callable
from typing import override

import httpx
import pytest
from httpx._client import UseClientDefault
from httpx._types import (
    AuthTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestExtensions,
    RequestFiles,
    TimeoutTypes,
)

from src.tools.grammar import search_grammar
from src.tools.vocabulary import search_vocab


def _patch_client_for_inspection(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    recorded_urls: list[str],
) -> None:
    monkeypatch.setenv("BUNPRO_JWT", "dummy-token")
    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "dummy-token")

    class _RecordingAsyncClient(httpx.AsyncClient):
        @override
        async def request(
            self,
            method: str,
            url: httpx.URL | str,
            *,
            content: RequestContent | None = None,
            data: RequestData | None = None,
            files: RequestFiles | None = None,
            json: object | None = None,
            params: QueryParamTypes | None = None,
            headers: HeaderTypes | None = None,
            cookies: CookieTypes | None = None,
            auth: AuthTypes | UseClientDefault | None = None,
            follow_redirects: bool | UseClientDefault = False,
            timeout: TimeoutTypes | UseClientDefault | None = None,
            extensions: RequestExtensions | None = None,
        ) -> httpx.Response:
            recorded_urls.append(str(url))
            return await super().request(
                method,
                url,
                content=content,
                data=data,
                files=files,
                json=json,
                params=params,
                headers=headers,
                cookies=cookies,
                auth=auth,
                follow_redirects=follow_redirects,
                timeout=timeout,
                extensions=extensions,
            )

    def _mock_async_client(*_args: object, **_kwargs: object) -> httpx.AsyncClient:
        return _RecordingAsyncClient(
            base_url="https://api.bunpro.jp/api/frontend",
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Token token=dummy-token"},
            timeout=httpx.Timeout(10.0, read=30.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    monkeypatch.setattr(httpx, "AsyncClient", _mock_async_client)


@pytest.mark.asyncio
async def test_search_grammar_passes_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_urls: list[str] = []
    handler_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        handler_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "query": "particles",
                "grammar_points": {"data": []},
                "meta": {},
            },
        )

    _patch_client_for_inspection(monkeypatch, handler, recorded_urls)

    _ = await search_grammar("particles")

    assert recorded_urls, "Expected Bunpro search to issue a request"
    assert handler_urls, "Expected Bunpro search to hit the mock handler"
    assert not recorded_urls[0].startswith("/"), "Expected relative path, got absolute"
    assert (
        handler_urls[0] == "https://api.bunpro.jp/api/frontend/search/reviewables_v1_1"
    ), "Expected fully joined Bunpro search URL"


@pytest.mark.asyncio
async def test_search_vocab_passes_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_urls: list[str] = []
    handler_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        handler_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "query": "book",
                "vocabs": {"data": []},
                "meta": {},
            },
        )

    _patch_client_for_inspection(monkeypatch, handler, recorded_urls)

    _ = await search_vocab("book")

    assert recorded_urls, "Expected Bunpro search to issue a request"
    assert handler_urls, "Expected Bunpro search to hit the mock handler"
    assert not recorded_urls[0].startswith("/"), "Expected relative path, got absolute"
    assert (
        handler_urls[0] == "https://api.bunpro.jp/api/frontend/search/reviewables_v1_1"
    ), "Expected fully joined Bunpro search URL"
