import json
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from gateway.config import Settings
from gateway.providers import ChatRequest, OpenRouterProvider, ResolvedRoute
from gateway.providers.errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderConfigError,
    ProviderPaymentRequiredError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

BASE_URL = "https://openrouter.test/api/v1"
CHAT_URL = f"{BASE_URL}/chat/completions"
API_KEY = "sk-or-test-not-real"
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "openrouter_chat_ok.json").read_text(encoding="utf-8")
)
REQUEST = ChatRequest.model_validate(
    {"messages": [{"role": "user", "content": "Como deixar o carro mais preso?"}], "temperature": 0}
)
ROUTE = ResolvedRoute(model="anthropic/claude-haiku-5.5")


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        openrouter_api_key=SecretStr(API_KEY),
        openrouter_base_url=BASE_URL,
    )


@pytest.fixture
async def provider() -> AsyncIterator[OpenRouterProvider]:
    async with OpenRouterProvider(make_settings()) as p:
        yield p


def sent_body(route: respx.Route) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(route.calls.last.request.content)
    return body


@respx.mock
async def test_chat_parses_result(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).respond(200, json=FIXTURE)

    result = await provider.chat(REQUEST, ROUTE)

    assert result.id == "gen-1760000000-abc123"
    assert result.model_requested == "anthropic/claude-haiku-5.5"
    assert result.model_used == "anthropic/claude-haiku-5.5"
    assert result.provider == "Anthropic"
    assert result.content == "Aumente o wedge para deixar o carro mais preso."
    assert result.finish_reason == "stop"
    assert result.usage.prompt_tokens == 120
    assert result.usage.completion_tokens == 30
    assert result.usage.total_tokens == 150
    assert result.usage.cost_usd == Decimal("0.000315")
    assert result.latency_ms >= 0


@respx.mock
async def test_request_body_and_headers(provider: OpenRouterProvider) -> None:
    route = respx.post(CHAT_URL).respond(200, json=FIXTURE)

    await provider.chat(REQUEST, ROUTE)

    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert request.headers["X-Title"] == "llm-gateway"
    body = sent_body(route)
    assert body["model"] == "anthropic/claude-haiku-5.5"
    assert body["temperature"] == 0  # extra fields pass through
    assert body["messages"] == [{"role": "user", "content": "Como deixar o carro mais preso?"}]
    assert body["usage"] == {"include": True}
    assert "models" not in body
    assert "provider" not in body


@respx.mock
async def test_fallback_models_and_provider_preferences(provider: OpenRouterProvider) -> None:
    route = respx.post(CHAT_URL).respond(200, json={**FIXTURE, "model": "google/gemini-3.8-flash"})
    resolved = ResolvedRoute(
        model="anthropic/claude-haiku-5.5",
        fallback_models=["google/gemini-3.8-flash"],
        provider_preferences={"sort": "price"},
    )

    result = await provider.chat(REQUEST, resolved)

    body = sent_body(route)
    assert body["models"] == ["anthropic/claude-haiku-5.5", "google/gemini-3.8-flash"]
    assert body["provider"] == {"sort": "price"}
    # The model that actually answered is what gets recorded.
    assert result.model_requested == "anthropic/claude-haiku-5.5"
    assert result.model_used == "google/gemini-3.8-flash"


@respx.mock
async def test_stream_flag_is_not_forwarded(provider: OpenRouterProvider) -> None:
    route = respx.post(CHAT_URL).respond(200, json=FIXTURE)
    request = ChatRequest.model_validate(
        {"messages": [{"role": "user", "content": "oi"}], "stream": True}
    )

    await provider.chat(request, ROUTE)

    assert "stream" not in sent_body(route)


@respx.mock
async def test_missing_cost_is_none_not_estimated(provider: OpenRouterProvider) -> None:
    payload = {**FIXTURE, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    respx.post(CHAT_URL).respond(200, json=payload)

    result = await provider.chat(REQUEST, ROUTE)

    assert result.usage.cost_usd is None


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (400, ProviderBadRequestError),
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (402, ProviderPaymentRequiredError),
        (404, ProviderBadRequestError),
        (408, ProviderTimeoutError),
        (500, ProviderUnavailableError),
        (502, ProviderUnavailableError),
        (503, ProviderUnavailableError),
    ],
)
@respx.mock
async def test_http_errors_are_typed(
    provider: OpenRouterProvider, status: int, error_type: type[Exception]
) -> None:
    respx.post(CHAT_URL).respond(status, json={"error": {"code": status, "message": "boom"}})

    with pytest.raises(error_type, match="boom"):
        await provider.chat(REQUEST, ROUTE)


@respx.mock
async def test_rate_limit_reads_retry_after(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).respond(
        429, headers={"Retry-After": "12"}, json={"error": {"code": 429, "message": "slow down"}}
    )

    with pytest.raises(ProviderRateLimitError) as info:
        await provider.chat(REQUEST, ROUTE)

    assert info.value.retry_after_seconds == 12
    assert info.value.retryable is True


@respx.mock
async def test_rate_limit_without_retry_after(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).respond(429, text="Too Many Requests")

    with pytest.raises(ProviderRateLimitError) as info:
        await provider.chat(REQUEST, ROUTE)

    assert info.value.retry_after_seconds is None


@respx.mock
async def test_error_object_inside_200(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).respond(
        200, json={"error": {"code": 502, "message": "upstream provider failed"}}
    )

    with pytest.raises(ProviderUnavailableError, match="upstream provider failed"):
        await provider.chat(REQUEST, ROUTE)


@respx.mock
async def test_timeout(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderTimeoutError) as info:
        await provider.chat(REQUEST, ROUTE)

    assert info.value.retryable is True


@respx.mock
async def test_connection_error(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(ProviderUnavailableError):
        await provider.chat(REQUEST, ROUTE)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, json={"id": "x", "choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": "no id"}}]}),
    ],
)
@respx.mock
async def test_malformed_responses(provider: OpenRouterProvider, response: httpx.Response) -> None:
    respx.post(CHAT_URL).mock(return_value=response)

    with pytest.raises(ProviderResponseError):
        await provider.chat(REQUEST, ROUTE)


@respx.mock
async def test_api_key_never_leaks_into_errors(provider: OpenRouterProvider) -> None:
    respx.post(CHAT_URL).respond(401, json={"error": {"code": 401, "message": "invalid key"}})

    with pytest.raises(ProviderAuthError) as info:
        await provider.chat(REQUEST, ROUTE)

    assert API_KEY not in str(info.value)
    assert API_KEY not in repr(info.value)


def test_missing_api_key_fails_fast() -> None:
    settings = Settings(_env_file=None, openrouter_api_key=None)
    with pytest.raises(ProviderConfigError):
        OpenRouterProvider(settings)


def test_raw_payload_hidden_from_repr() -> None:
    from gateway.providers.openrouter import _parse_result

    result = _parse_result(FIXTURE, route=ROUTE, latency_ms=1.0)
    assert "raw=" not in repr(result)
