from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

# pyright: reportMissingImports=false, reportUnknownParameterType=false, reportUnknownVariableType=false
import httpx
import pytest

from src.tools.grammar import get_grammar_point, search_grammar
from src.tools.reading import get_reading_passages, search_reading_passages
from src.tools.review import get_due_items, get_review_queue
from src.tools.user_stats import get_jlpt_progress, get_srs_forecast, get_user_stats
from src.tools.vocabulary import get_vocab_items, get_vocab_level, search_vocab


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


def _json_body(request: httpx.Request) -> object | None:
    if not request.content:
        return None
    return cast(object, json.loads(request.content.decode("utf-8")))


@pytest.mark.asyncio
async def test_grammar_tools_call_expected_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        calls.append((request.method, request.url.path, _json_body(request)))
        if request.url.path == "/search/v1_1":
            payload = {
                "results": [{"grammar_point_id": 123}]
                + [{"id": i} for i in range(100)],
            }
            return httpx.Response(200, json=payload)
        if request.url.path == "/reviewables/grammar_point/123":
            return httpx.Response(200, json={"id": 123, "name": "test"})
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, _handler)

    search_payload = await search_grammar("〜ない")
    detail_payload = await get_grammar_point("123")
    search_results = search_payload["results"]
    assert isinstance(search_results, list)
    typed_search_results = cast(list[object], search_results)

    assert len(typed_search_results) == 40
    assert detail_payload == {"id": 123, "name": "test"}
    assert calls[0] == ("POST", "/search/v1_1", {"query": "〜ない"})
    assert calls[1] == ("GET", "/reviewables/grammar_point/123", None)


@pytest.mark.asyncio
async def test_vocab_tools_call_expected_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        calls.append((request.method, request.url.path, _json_body(request)))
        if request.url.path == "/user_stats/jlpt_progress_mixed":
            return httpx.Response(200, json={"jlpt": "n3"})
        if request.url.path == "/reviewables/vocab/本":
            return httpx.Response(200, json={"id": "本", "kind": "vocab"})
        if request.url.path == "/search/v1_1":
            return httpx.Response(
                200,
                json={"results": [{"slug": f"item-{i}"} for i in range(100)]},
            )
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, _handler)

    level_payload = await get_vocab_level()
    item_payload = await get_vocab_items("本")
    search_payload = await search_vocab("本")
    search_results = search_payload["results"]
    assert isinstance(search_results, list)
    typed_search_results = cast(list[object], search_results)

    assert level_payload == {"jlpt": "n3"}
    assert item_payload == {"id": "本", "kind": "vocab"}
    assert len(typed_search_results) == 40
    assert calls[0] == ("GET", "/user_stats/jlpt_progress_mixed", None)
    assert calls[1] == ("GET", "/reviewables/vocab/本", None)
    assert calls[2] == ("POST", "/search/v1_1", {"query": "本"})


@pytest.mark.asyncio
async def test_reading_tools_call_expected_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Cookie") == "frontend_api_token=dummy"
        calls.append((request.method, request.url.path, _json_body(request)))
        if request.url.path == "/reading_passages":
            html = """<html><body><script id=\"__NEXT_DATA__\" type=\"application/json\">{"props":{"pageProps":{"readingPassages":[{"id":1,"title":"本を読む"},{"id":2,"title":"海へ行く"}]}}}</script></body></html>"""
            return httpx.Response(200, text=html)
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, _handler)

    passages_payload = await get_reading_passages()
    search_payload = await search_reading_passages("本")
    search_results = search_payload["results"]
    assert isinstance(search_results, list)
    typed_search_results = cast(list[object], search_results)

    assert passages_payload == {
        "results": [
            {"id": 1, "title": "本を読む"},
            {"id": 2, "title": "海へ行く"},
        ]
    }
    assert len(typed_search_results) == 1
    assert search_payload["query"] == "本"
    assert calls[0] == ("GET", "/reading_passages", None)
    assert calls[1] == ("GET", "/reading_passages", None)


@pytest.mark.asyncio
async def test_user_stats_tools_call_expected_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        calls.append((request.method, request.url.path, _json_body(request)))
        payloads = {
            "/user_stats/base_stats": {"total": 42},
            "/user_stats/jlpt_progress_mixed": {"n2": {"done": 10}},
            "/user_stats/forecast_daily": {"daily": [1, 2, 3]},
        }
        return httpx.Response(200, json=payloads[request.url.path])

    _install_mock_transport(monkeypatch, _handler)

    stats_payload = await get_user_stats()
    jlpt_payload = await get_jlpt_progress()
    forecast_payload = await get_srs_forecast()

    assert stats_payload == {"total": 42}
    assert jlpt_payload == {"n2": {"done": 10}}
    assert forecast_payload == {"daily": [1, 2, 3]}
    assert calls[0] == ("GET", "/user_stats/base_stats", None)
    assert calls[1] == ("GET", "/user_stats/jlpt_progress_mixed", None)
    assert calls[2] == ("GET", "/user_stats/forecast_daily", None)


@pytest.mark.asyncio
async def test_review_tools_call_expected_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        calls.append((request.method, request.url.path, _json_body(request)))
        payloads = {
            "/user/queue": {"queue": [{"id": 1}]},
            "/user/due": {"due": [{"id": 2}]},
        }
        return httpx.Response(200, json=payloads[request.url.path])

    _install_mock_transport(monkeypatch, _handler)

    queue_payload = await get_review_queue()
    due_payload = await get_due_items()

    assert queue_payload == {"queue": [{"id": 1}]}
    assert due_payload == {"due": [{"id": 2}]}
    assert calls[0] == ("GET", "/user/queue", None)
    assert calls[1] == ("GET", "/user/due", None)
