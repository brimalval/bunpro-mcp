from __future__ import annotations

# pyright: reportPrivateUsage=false
import asyncio
from collections.abc import Generator
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from src.cache import _clear_cache, _recreate_cache
from src.tools.review import get_pending_reviews


def _quiz_payload(session_id: str = "session") -> dict[str, object]:
    return {
        "review_session_id": session_id,
        "pending_attempt": [
            {
                "study_question": "Question",
                "answer": "Answer",
                "kanji_answer": "漢字",
                "nuance": "Nuance",
                "translation": "English",
                "audio_url": None,
                "reviewable": {"id": 1, "slug": "reviewable", "type": "vocab"},
            }
        ],
        "pending_wrapup": [],
        "total_pending_attempt_count": 1,
        "total_pending_wrapup_count": 0,
    }


@pytest.fixture(autouse=True)
def clear_pending_reviews_cache() -> Generator[None, None, None]:
    _clear_cache()
    yield
    _clear_cache()


@pytest.mark.asyncio
async def test_cache_hit_avoids_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "token-cache-hit")
    payload = _quiz_payload("hit-session")

    with patch(
        "src.api_client.BunproClient.request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = payload
        first = await get_pending_reviews()
        second = await get_pending_reviews()

    assert first == payload
    assert second == payload
    assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_cache_expiry_triggers_refetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "token-expiry")
    _ = _recreate_cache(ttl_seconds=1)
    payload_one = _quiz_payload("expiry-one")
    payload_two = _quiz_payload("expiry-two")

    with patch(
        "src.api_client.BunproClient.request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [payload_one, payload_two]
        first = await get_pending_reviews()
        assert first == payload_one
        await asyncio.sleep(1.1)
        second = await get_pending_reviews()

    assert second == payload_two
    assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_per_user_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    payload_a = _quiz_payload("user-a")
    payload_b = _quiz_payload("user-b")

    with patch(
        "src.api_client.BunproClient.request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [payload_a, payload_b]

        monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "token-user-a")
        first = await get_pending_reviews()

        monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "token-user-b")
        second = await get_pending_reviews()

    assert first == payload_a
    assert second == payload_b
    assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_invalid_payload_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "token-invalid")
    payload = _quiz_payload("valid-after-error")

    invalid_payload = _quiz_payload("invalid-session")
    invalid_payload["pending_attempt"] = [123]

    with patch(
        "src.api_client.BunproClient.request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [invalid_payload, payload]
        with pytest.raises(RuntimeError, match="Invalid Bunpro quiz index payload"):
            _ = await get_pending_reviews()
        result = await get_pending_reviews()

    assert result == payload
    assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_mutation_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUNPRO_FRONTEND_API_TOKEN", "token-mutation")
    payload = _quiz_payload("mutation-session")

    with patch(
        "src.api_client.BunproClient.request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = payload
        first = await get_pending_reviews()
        pending_attempt = cast(list[dict[str, object]], first["pending_attempt"])
        pending_attempt.append({"study_question": "Extra"})
        second = await get_pending_reviews()

    assert second["pending_attempt"] == payload["pending_attempt"]
    assert mock_request.call_count == 1
