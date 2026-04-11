"""Anthropic adapter — Messages API, Batch API, skills beta, prompt caching."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Optional

import anthropic

from terrain.models.pipeline import ApiUsage
from terrain.providers.ai.base import (
    BatchHandle,
    BatchResult,
    BatchStatus,
    CompletionRequest,
    CompletionResponse,
)

logger = logging.getLogger(__name__)

# Per-token pricing in USD (as of 2025)
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
        "cache_read": 0.08 / 1_000_000,
    },
    "claude-sonnet-4-6": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
        "cache_read": 0.30 / 1_000_000,
    },
    "claude-opus-4-6": {
        "input": 15.00 / 1_000_000,
        "output": 75.00 / 1_000_000,
        "cache_read": 1.50 / 1_000_000,
    },
}

_DEFAULT_PRICING = {
    "input": 3.00 / 1_000_000,
    "output": 15.00 / 1_000_000,
    "cache_read": 0.30 / 1_000_000,
}


def _calculate_cost(
    model: str, input_tokens: int, output_tokens: int, cached_tokens: int
) -> float:
    """Calculate API cost in USD."""
    pricing = _PRICING.get(model, _DEFAULT_PRICING)
    billable_input = max(0, input_tokens - cached_tokens)
    cost = (
        billable_input * pricing["input"]
        + output_tokens * pricing["output"]
        + cached_tokens * pricing["cache_read"]
    )
    return round(cost, 6)


class AnthropicProvider:
    """AI provider backed by the Anthropic Messages API and Batch API."""

    def __init__(
        self,
        api_key: str,
        usage_logger: Optional[Callable[[ApiUsage], Awaitable[None]]] = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._usage_logger = usage_logger

    async def _log_usage(
        self,
        request: CompletionRequest,
        response: CompletionResponse,
    ) -> None:
        """Log API usage via the callback if one was provided."""
        if self._usage_logger is None:
            return
        usage = ApiUsage(
            provider="anthropic",
            model=response.model,
            task=request.metadata.get("task", "unknown"),
            candidate_id=request.metadata.get("candidate_id", ""),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cached_tokens=response.cached_tokens,
            cost_usd=response.cost_usd,
        )
        try:
            await self._usage_logger(usage)
        except Exception as e:
            logger.warning("Failed to log API usage: %s", e)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a single completion request via the Messages API."""
        # Build system prompt
        if request.cache_control:
            system: str | list[dict] = [
                {
                    "type": "text",
                    "text": request.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = request.system_prompt

        messages = [{"role": "user", "content": request.user_prompt}]

        kwargs: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": system,
            "messages": messages,
        }

        # Skills beta
        extra_headers: dict[str, str] = {}
        if request.skill:
            extra_headers["anthropic-beta"] = "skills-2025-10-02"

        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        result = await self._client.messages.create(**kwargs)

        # Extract content
        content = ""
        for block in result.content:
            if hasattr(block, "text"):
                content += block.text

        # Extract usage
        usage = result.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

        cost = _calculate_cost(request.model, input_tokens, output_tokens, cached_tokens)

        response = CompletionResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            model=request.model,
            cost_usd=cost,
        )

        await self._log_usage(request, response)
        return response

    async def complete_batch(self, requests: list[CompletionRequest]) -> BatchHandle:
        """Submit a batch of requests via the Batch API."""
        batch_requests = []
        for i, req in enumerate(requests):
            if req.cache_control:
                system: str | list[dict] = [
                    {
                        "type": "text",
                        "text": req.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                system = req.system_prompt

            batch_requests.append({
                "custom_id": f"req-{i}",
                "params": {
                    "model": req.model,
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": req.user_prompt}],
                },
            })

        result = await self._client.messages.batches.create(requests=batch_requests)

        return BatchHandle(
            id=result.id,
            provider="anthropic",
            status=BatchStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
            request_count=len(requests),
        )

    async def poll_batch(self, handle: BatchHandle) -> BatchResult:
        """Check batch status and retrieve results if complete."""
        batch = await self._client.messages.batches.retrieve(handle.id)

        status_map = {
            "in_progress": BatchStatus.IN_PROGRESS,
            "ended": BatchStatus.COMPLETED,
            "canceling": BatchStatus.IN_PROGRESS,
            "canceled": BatchStatus.FAILED,
            "expired": BatchStatus.FAILED,
        }
        current_status = status_map.get(batch.processing_status, BatchStatus.IN_PROGRESS)

        if current_status != BatchStatus.COMPLETED:
            return BatchResult(
                handle=handle,
                status=current_status,
            )

        # Retrieve results
        responses: list[CompletionResponse] = []
        async for result_entry in await self._client.messages.batches.results(handle.id):
            if result_entry.result.type == "succeeded":
                msg = result_entry.result.message
                content = ""
                for block in msg.content:
                    if hasattr(block, "text"):
                        content += block.text

                usage = msg.usage
                input_tokens = usage.input_tokens
                output_tokens = usage.output_tokens
                cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

                responses.append(
                    CompletionResponse(
                        content=content,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_tokens=cached_tokens,
                        model=msg.model,
                        cost_usd=_calculate_cost(
                            msg.model, input_tokens, output_tokens, cached_tokens
                        ),
                    )
                )

        return BatchResult(
            handle=handle,
            responses=responses,
            completed_at=datetime.now(timezone.utc),
            status=BatchStatus.COMPLETED,
        )

    async def check_health(self) -> bool:
        """Verify Anthropic API is reachable with a minimal request."""
        try:
            await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False
