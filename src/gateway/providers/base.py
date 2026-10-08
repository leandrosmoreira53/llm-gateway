"""Provider interface and the normalized request/response models every provider speaks."""

from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant", "tool", "developer"]
    # Plain text or OpenAI content parts (text, image_url, ...).
    content: str | list[dict[str, Any]] | None = None


class ChatRequest(BaseModel):
    """OpenAI-style chat request. Unknown fields (temperature, tools, ...) pass through as-is."""

    model_config = ConfigDict(extra="allow")

    messages: list[Message] = Field(min_length=1)


class ResolvedRoute(BaseModel):
    """Where a request goes: the model chosen by the gateway plus transport-level options."""

    model: str
    # Tried in order by OpenRouter if `model` is down (sent as the `models` parameter).
    fallback_models: list[str] = Field(default_factory=list)
    # OpenRouter provider preferences, e.g. {"sort": "price"}. The gateway picks the model;
    # OpenRouter only picks which provider serves it (ADR 0002).
    provider_preferences: dict[str, Any] | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # None when the provider did not report cost; never estimated here.
    cost_usd: Decimal | None = None


class ChatResult(BaseModel):
    id: str
    model_requested: str
    model_used: str
    provider: str | None
    content: str | None
    finish_reason: str | None
    usage: Usage
    latency_ms: float
    raw: dict[str, Any] = Field(repr=False)


class Provider(Protocol):
    name: str

    async def chat(self, request: ChatRequest, route: ResolvedRoute) -> ChatResult: ...
