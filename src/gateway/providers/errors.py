"""Typed provider errors. Callers decide on retry/fallback from `retryable`, never from strings."""


class ProviderError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProviderConfigError(ProviderError):
    """Missing or invalid local configuration (e.g. no API key)."""


class ProviderAuthError(ProviderError):
    """401/403: invalid or unauthorized key."""


class ProviderPaymentRequiredError(ProviderError):
    """402: not enough credits."""


class ProviderBadRequestError(ProviderError):
    """400/404/422: the request itself is wrong; retrying will not help."""


class ProviderRateLimitError(ProviderError):
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = 429,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after_seconds = retry_after_seconds


class ProviderUnavailableError(ProviderError):
    """5xx or upstream model/provider down."""

    retryable = True


class ProviderTimeoutError(ProviderError):
    retryable = True


class ProviderResponseError(ProviderError):
    """The response did not have the expected shape."""
