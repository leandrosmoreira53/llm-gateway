"""Runtime settings, read from the project's `.env` or environment variables."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Sent as X-Title / HTTP-Referer so calls are attributed to this app on OpenRouter.
    app_title: str = "llm-gateway"
    app_url: str = "https://github.com/leandrosmoreira53/llm-gateway"

    http_connect_timeout_seconds: float = Field(default=10.0, gt=0)
    http_timeout_seconds: float = Field(default=120.0, gt=0)

    bench_dataset_path: Path | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # The project's .env wins over machine-wide variables: a global OPENROUTER_API_KEY set for
        # other tools must not silently pay for this project. Without a .env (e.g. in a container),
        # environment variables apply as usual.
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    def key_hint(self) -> str:
        """Last 4 characters of the OpenRouter key, safe to print."""
        if self.openrouter_api_key is None:
            return "(none)"
        return "..." + self.openrouter_api_key.get_secret_value()[-4:]
