"""Tests for the Ollama AI adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from terrain.providers.ai.base import CompletionRequest
from terrain.providers.ai.ollama import OllamaProvider


def _make_request(**overrides: object) -> CompletionRequest:
    defaults = {
        "model": "llama3.1:8b-q4",
        "system_prompt": "You are a classifier.",
        "user_prompt": "Classify this text.",
    }
    return CompletionRequest(**(defaults | overrides))


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    return client


class TestOllamaComplete:
    async def test_sends_correct_request(self) -> None:
        provider = OllamaProvider("http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "duplicate"},
            "prompt_eval_count": 100,
            "eval_count": 10,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await provider.complete(_make_request())

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert body["model"] == "llama3.1:8b-q4"
            assert body["stream"] is False
            assert len(body["messages"]) == 2

        assert result.content == "duplicate"
        assert result.input_tokens == 100
        assert result.output_tokens == 10
        assert result.cost_usd == 0.0

    async def test_batch_executes_sequentially(self) -> None:
        provider = OllamaProvider("http://localhost:11434")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "result"},
            "prompt_eval_count": 50,
            "eval_count": 5,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider._client, "post", new_callable=AsyncMock, return_value=mock_response):
            requests = [_make_request(), _make_request()]
            handle = await provider.complete_batch(requests)

            assert handle.request_count == 2
            assert handle.status.value == "completed"

            batch_result = await provider.poll_batch(handle)
            assert len(batch_result.responses) == 2


class TestOllamaHealthCheck:
    async def test_healthy(self) -> None:
        provider = OllamaProvider("http://localhost:11434")
        mock_resp = AsyncMock()
        mock_resp.status_code = 200

        with patch.object(provider._client, "get", return_value=mock_resp):
            assert await provider.check_health() is True

    async def test_unhealthy(self) -> None:
        provider = OllamaProvider("http://localhost:11434")

        with patch.object(provider._client, "get", side_effect=Exception("Connection refused")):
            assert await provider.check_health() is False

    async def test_non_200(self) -> None:
        provider = OllamaProvider("http://localhost:11434")
        mock_resp = AsyncMock()
        mock_resp.status_code = 500

        with patch.object(provider._client, "get", return_value=mock_resp):
            assert await provider.check_health() is False
