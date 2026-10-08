"""OpenRouter provider: the transport to the models (ADR 0002)."""

import time
from decimal import Decimal, InvalidOperation
from types import TracebackType
from typing import Any, Self

import httpx

from gateway.config import Settings
from gateway.providers.base import ChatRequest, ChatResult, ResolvedRoute, Usage
from gateway.providers.errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderConfigError,
    ProviderError,
    ProviderPaymentRequiredError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.openrouter_api_key is None:
            raise ProviderConfigError("OPENROUTER_API_KEY is not set")
        self._api_key = settings.openrouter_api_key
        self._base_url = settings.openrouter_base_url.rstrip("/")
        self._headers = {"X-Title": settings.app_title, "HTTP-Referer": settings.app_url}
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                settings.http_timeout_seconds, connect=settings.http_connect_timeout_seconds
            )
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(self, request: ChatRequest, route: ResolvedRoute) -> ChatResult:
        body = self._build_body(request, route)
        headers = {
            **self._headers,
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
        }
        started = time.perf_counter()
        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions", json=body, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"OpenRouter timed out: {type(exc).__name__}") from exc
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(f"OpenRouter unreachable: {type(exc).__name__}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        if response.status_code >= 400:
            raise _error_from_response(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("OpenRouter returned non-JSON body") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("OpenRouter returned a non-object body")
        # OpenRouter may report upstream failures with HTTP 200 and an `error` object.
        if "error" in payload:
            raise _error_from_payload(payload["error"], status_code=response.status_code)
        return _parse_result(payload, route=route, latency_ms=latency_ms)

    @staticmethod
    def _build_body(request: ChatRequest, route: ResolvedRoute) -> dict[str, Any]:
        body = request.model_dump(mode="json", exclude_none=True)
        body.pop("stream", None)  # streaming lands in S4
        body["model"] = route.model
        if route.fallback_models:
            body["models"] = [route.model, *route.fallback_models]
        if route.provider_preferences:
            body["provider"] = route.provider_preferences
        # Ask OpenRouter to include token counts and cost in `usage`.
        body["usage"] = {"include": True}
        return body


def _parse_result(
    payload: dict[str, Any], *, route: ResolvedRoute, latency_ms: float
) -> ChatResult:
    try:
        choice = payload["choices"][0]
        message = choice.get("message") or {}
        usage_raw = payload.get("usage") or {}
        return ChatResult(
            id=str(payload["id"]),
            model_requested=route.model,
            model_used=str(payload.get("model") or route.model),
            provider=payload.get("provider"),
            content=message.get("content"),
            finish_reason=choice.get("finish_reason"),
            usage=Usage(
                prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
                completion_tokens=int(usage_raw.get("completion_tokens") or 0),
                total_tokens=int(usage_raw.get("total_tokens") or 0),
                cost_usd=_to_decimal(usage_raw.get("cost")),
            ),
            latency_ms=latency_ms,
            raw=payload,
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderResponseError(f"Unexpected OpenRouter response shape: {exc!r}") from exc


def _to_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _error_from_response(response: httpx.Response) -> ProviderError:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return _error_from_payload(
            error, status_code=response.status_code, retry_after=response.headers.get("Retry-After")
        )
    return _error_for_status(
        response.status_code,
        f"OpenRouter HTTP {response.status_code}",
        retry_after=response.headers.get("Retry-After"),
    )


def _error_from_payload(
    error: object, *, status_code: int, retry_after: str | None = None
) -> ProviderError:
    message = "OpenRouter error"
    code = status_code
    if isinstance(error, dict):
        message = str(error.get("message") or message)
        if isinstance(error.get("code"), int):
            code = error["code"]
    return _error_for_status(code, message, retry_after=retry_after)


def _error_for_status(status: int, message: str, *, retry_after: str | None) -> ProviderError:
    if status in (401, 403):
        return ProviderAuthError(message, status_code=status)
    if status == 402:
        return ProviderPaymentRequiredError(message, status_code=status)
    if status == 429:
        return ProviderRateLimitError(
            message, status_code=status, retry_after_seconds=_parse_retry_after(retry_after)
        )
    if status == 408:
        return ProviderTimeoutError(message, status_code=status)
    if status >= 500:
        return ProviderUnavailableError(message, status_code=status)
    if status >= 400:
        return ProviderBadRequestError(message, status_code=status)
    # An error object with a non-error status: treat as upstream failure.
    return ProviderUnavailableError(message, status_code=status)


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None  # HTTP-date form is not used by OpenRouter; ignore.
    return seconds if seconds >= 0 else None
