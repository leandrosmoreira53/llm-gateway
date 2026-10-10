"""Runtime settings, read from environment variables or `.env`."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Sent as X-Title / HTTP-Referer so calls are attributed to this app on OpenRouter.
    app_title: str = "llm-gateway"
    app_url: str = "https://github.com/Leandrosmoreira/llm-gateway"

    http_connect_timeout_seconds: float = Field(default=10.0, gt=0)
    http_timeout_seconds: float = Field(default=120.0, gt=0)

    bench_dataset_path: Path | None = None
