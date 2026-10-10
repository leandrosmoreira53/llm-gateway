from pathlib import Path

import pytest

from gateway.config import Settings


def test_defaults_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.openrouter_api_key is None
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"


def test_api_key_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-123")
    settings = Settings(_env_file=None)
    assert settings.openrouter_api_key is not None
    assert settings.openrouter_api_key.get_secret_value() == "sk-or-test-123"
    assert "sk-or-test-123" not in repr(settings)


def test_project_env_file_wins_over_machine_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=sk-or-project-abcd\n", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-global-wxyz")
    settings = Settings(_env_file=env_file)
    assert settings.key_hint() == "...abcd"


def test_machine_variable_applies_without_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-global-wxyz")
    assert Settings(_env_file=None).key_hint() == "...wxyz"
