from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

# pyright: reportMissingImports=false, reportUnknownParameterType=false, reportUnknownVariableType=false
import httpx
import pytest

from src.tools.grammar import search_grammar
from src.tools.reading import get_reading_passages
from src.tools.review import get_study_configuration
from src.tools.user_stats import get_srs_forecast, get_user_stats
from src.tools.vocabulary import search_vocab


def _vocab_reviewable(id_value: str, slug: str) -> dict[str, object]:
    return {
        "id": id_value,
        "type": "vocab",
        "attributes": {"slug": slug, "title": slug},
    }


def _install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    real_async_client = httpx.AsyncClient
    monkeypatch.setenv("BUNPRO_JWT", "dummy")
    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "dummy")
    monkeypatch.setenv("BUNPRO_API_BASE_URL", "http://test")

    def _mock_async_client(**kwargs: object) -> httpx.AsyncClient:
        return real_async_client(
            base_url=str(kwargs.get("base_url", "http://test")),
            transport=httpx.MockTransport(handler),
            headers=cast(dict[str, str], kwargs.get("headers", {})),
        )

    monkeypatch.setattr(httpx, "AsyncClient", _mock_async_client)


@pytest.mark.asyncio
async def test_search_grammar_raises_for_invalid_results_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        assert _request.headers.get("Authorization") == "Token token=dummy"
        return httpx.Response(200, json={"results": "not-a-list"})

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(
        RuntimeError, match="Unexpected Bunpro grammar search payload shape"
    ):
        _ = await search_grammar("〜ない")


@pytest.mark.asyncio
async def test_get_reading_passages_raises_for_missing_next_data_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        assert _request.headers.get("Cookie") == "frontend_api_token=dummy"
        return httpx.Response(200, text="<html><body>No next data</body></html>")

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(RuntimeError, match="Missing __NEXT_DATA__ payload"):
        _ = await get_reading_passages()


@pytest.mark.asyncio
async def test_get_study_configuration_raises_for_invalid_ready_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        assert _request.headers.get("Authorization") == "Token token=dummy"
        return httpx.Response(200, json={"ready": "bad-ready"})

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(RuntimeError, match="Invalid Bunpro review queue payload"):
        _ = await get_study_configuration()


@pytest.mark.asyncio
async def test_get_user_stats_raises_for_non_dict_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        assert _request.headers.get("Authorization") == "Token token=dummy"
        return httpx.Response(200, json=["unexpected", "shape"])

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(RuntimeError, match="Unexpected Bunpro payload shape"):
        _ = await get_user_stats()


@pytest.mark.asyncio
async def test_get_srs_forecast_rejects_invalid_granularity() -> None:
    with pytest.raises(ValueError, match="granularity must be 'daily' or 'hourly'"):
        _ = await get_srs_forecast("weekly")  # pyright: ignore[reportArgumentType]


@pytest.mark.asyncio
async def test_search_vocab_clamps_result_limit_to_min_and_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Token token=dummy"
        if request.url.path == "/search/reviewables_v1_1":
            body = cast(dict[str, object], json.loads(request.content.decode("utf-8")))
            assert body["options"] == {}
            assert body["is_searching_vocab"] is True
            assert body["is_searching_grammar"] is False
            return httpx.Response(
                200,
                json={
                    "query": body["query"],
                    "vocabs": {
                        "data": [
                            _vocab_reviewable(str(i), f"item-{i}") for i in range(100)
                        ]
                    },
                    "meta": {},
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, _handler)

    min_payload = await search_vocab("本", result_limit=0)
    max_payload = await search_vocab("本", result_limit=999)
    min_results = cast(list[object], min_payload["results"])
    max_results = cast(list[object], max_payload["results"])

    assert len(min_results) == 1
    assert len(max_results) == 50


@pytest.mark.asyncio
async def test_search_vocab_raises_for_invalid_search_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _handler(_request: httpx.Request) -> httpx.Response:
        assert _request.headers.get("Authorization") == "Token token=dummy"
        if _request.url.path == "/search/reviewables_v1_1":
            return httpx.Response(
                200,
                json={
                    "query": "本",
                    "vocabs": {"data": "bad-results"},
                },
            )
        return httpx.Response(500, json={"error": "unexpected"})

    _install_mock_transport(monkeypatch, _handler)

    with pytest.raises(RuntimeError, match="Unexpected Bunpro search payload shape"):
        _ = await search_vocab("本")
