"""Tests for the Anthropic AI adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from terrain.providers.ai.anthropic import AnthropicProvider, _calculate_cost
from terrain.providers.ai.base import BatchHandle, BatchStatus, CompletionRequest


def _make_request(**overrides: object) -> CompletionRequest:
    defaults = {
        "model": "claude-sonnet-4-6",
        "system_prompt": "You are a job evaluator.",
        "user_prompt": "Evaluate this job.",
        "metadata": {"task": "scoring", "candidate_id": "candidate_1"},
    }
    return CompletionRequest(**(defaults | overrides))


def _mock_message_response(content: str = "test response") -> MagicMock:
    """Create a mock Anthropic message response."""
    block = MagicMock()
    block.text = content
    block.type = "text"

    usage = MagicMock()
    usage.input_tokens = 1000
    usage.output_tokens = 200
    usage.cache_read_input_tokens = 0

    msg = MagicMock()
    msg.content = [block]
    msg.usage = usage
    msg.model = "claude-sonnet-4-6"
    return msg


class TestCalculateCost:
    def test_sonnet_pricing(self) -> None:
        cost = _calculate_cost("claude-sonnet-4-6", 1000, 200, 0)
        expected = 1000 * 3.0 / 1_000_000 + 200 * 15.0 / 1_000_000
        assert abs(cost - expected) < 0.000001

    def test_cached_tokens_reduce_input_cost(self) -> None:
        cost_no_cache = _calculate_cost("claude-sonnet-4-6", 1000, 100, 0)
        cost_cached = _calculate_cost("claude-sonnet-4-6", 1000, 100, 800)
        assert cost_cached < cost_no_cache

    def test_haiku_cheaper_than_sonnet(self) -> None:
        haiku = _calculate_cost("claude-haiku-4-5-20251001", 1000, 200, 0)
        sonnet = _calculate_cost("claude-sonnet-4-6", 1000, 200, 0)
        assert haiku < sonnet

    def test_unknown_model_uses_default(self) -> None:
        cost = _calculate_cost("unknown-model", 1000, 200, 0)
        assert cost > 0


class TestAnthropicComplete:
    async def test_basic_completion(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")
        mock_msg = _mock_message_response("The result")

        with patch.object(provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_msg):
            result = await provider.complete(_make_request())

        assert result.content == "The result"
        assert result.input_tokens == 1000
        assert result.output_tokens == 200

    async def test_cache_control_wraps_system(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")
        mock_msg = _mock_message_response()

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_msg
        ) as mock_create:
            await provider.complete(_make_request(cache_control=True))

            call_kwargs = mock_create.call_args.kwargs
            system = call_kwargs["system"]
            assert isinstance(system, list)
            assert system[0]["cache_control"] == {"type": "ephemeral"}

    async def test_no_cache_control_sends_string(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")
        mock_msg = _mock_message_response()

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_msg
        ) as mock_create:
            await provider.complete(_make_request(cache_control=False))

            call_kwargs = mock_create.call_args.kwargs
            assert isinstance(call_kwargs["system"], str)

    async def test_skill_adds_beta_header(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")
        mock_msg = _mock_message_response()

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_msg
        ) as mock_create:
            await provider.complete(_make_request(skill="voice-of-tim"))

            call_kwargs = mock_create.call_args.kwargs
            assert "extra_headers" in call_kwargs
            assert call_kwargs["extra_headers"]["anthropic-beta"] == "skills-2025-10-02"

    async def test_usage_logger_called(self) -> None:
        logger = AsyncMock()
        provider = AnthropicProvider(api_key="sk-test", usage_logger=logger)
        mock_msg = _mock_message_response()

        with patch.object(provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_msg):
            await provider.complete(_make_request())

        logger.assert_called_once()
        usage = logger.call_args[0][0]
        assert usage.provider == "anthropic"
        assert usage.task == "scoring"
        assert usage.candidate_id == "candidate_1"


class TestAnthropicHealthCheck:
    async def test_healthy(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")
        mock_msg = _mock_message_response()

        with patch.object(provider._client.messages, "create", new_callable=AsyncMock, return_value=mock_msg):
            assert await provider.check_health() is True

    async def test_unhealthy(self) -> None:
        provider = AnthropicProvider(api_key="sk-test")

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock, side_effect=Exception("API error")
        ):
            assert await provider.check_health() is False
