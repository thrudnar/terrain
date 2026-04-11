"""Ollama adapter — local LLM inference via HTTP API."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from terrain.providers.ai.base import (
    BatchHandle,
    BatchResult,
    BatchStatus,
    CompletionRequest,
    CompletionResponse,
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """AI provider backed by a local Ollama instance."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120.0)
        self._batch_results: dict[str, list[CompletionResponse]] = {}

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a chat completion request to Ollama."""
        body = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "options": {"temperature": request.temperature},
        }

        resp = await self._client.post("/api/chat", json=body)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        return CompletionResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=0,
            model=request.model,
            cost_usd=0.0,
        )

    async def complete_batch(self, requests: list[CompletionRequest]) -> BatchHandle:
        """Execute requests sequentially — Ollama has no batch API."""
        batch_id = f"ollama-batch-{uuid.uuid4().hex[:8]}"
        responses: list[CompletionResponse] = []

        for req in requests:
            resp = await self.complete(req)
            responses.append(resp)

        self._batch_results[batch_id] = responses

        return BatchHandle(
            id=batch_id,
            provider="ollama",
            status=BatchStatus.COMPLETED,
            submitted_at=datetime.now(timezone.utc),
            request_count=len(requests),
        )

    async def poll_batch(self, handle: BatchHandle) -> BatchResult:
        """Return stored batch results."""
        responses = self._batch_results.pop(handle.id, [])
        return BatchResult(
            handle=handle,
            responses=responses,
            completed_at=datetime.now(timezone.utc),
            status=BatchStatus.COMPLETED,
        )

    async def check_health(self) -> bool:
        """Verify Ollama is reachable and responding."""
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
