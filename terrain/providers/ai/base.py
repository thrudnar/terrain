"""AI provider interface — the contract for Anthropic and Ollama adapters."""

from datetime import datetime
from enum import StrEnum
from typing import Optional, Protocol

from pydantic import BaseModel, Field


class BatchStatus(StrEnum):
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CompletionRequest(BaseModel):
    model: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 4096
    temperature: float = 0.0
    response_format: Optional[str] = None
    cache_control: bool = False
    skill: Optional[str] = None
    metadata: dict[str, str] = Field(default_factory=dict)


class CompletionResponse(BaseModel):
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    model: str = ""
    cost_usd: float = 0.0


class BatchHandle(BaseModel):
    id: str
    provider: str
    status: BatchStatus = BatchStatus.SUBMITTED
    submitted_at: Optional[datetime] = None
    request_count: int = 0


class BatchResult(BaseModel):
    handle: BatchHandle
    responses: list[CompletionResponse] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    status: BatchStatus = BatchStatus.COMPLETED


class AIProvider(Protocol):
    """Common interface for all AI operations."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    async def complete_batch(self, requests: list[CompletionRequest]) -> BatchHandle: ...

    async def poll_batch(self, handle: BatchHandle) -> BatchResult: ...

    async def check_health(self) -> bool: ...
