"""Real paid calls. Never run in CI; run manually with `uv run pytest -m live`, after a cost check.

Requires OPENROUTER_API_KEY and LIVE_TEST_MODEL (an OpenRouter model slug) in the environment.
"""

import os

import pytest

from gateway.config import Settings
from gateway.providers import ChatRequest, OpenRouterProvider, ResolvedRoute

pytestmark = pytest.mark.live


async def test_openrouter_round_trip() -> None:
    model = os.environ.get("LIVE_TEST_MODEL")
    settings = Settings()
    if settings.openrouter_api_key is None or not model:
        pytest.skip("OPENROUTER_API_KEY and LIVE_TEST_MODEL are required")

    request = ChatRequest.model_validate(
        {"messages": [{"role": "user", "content": "Reply with the word: ok"}], "max_tokens": 5}
    )
    async with OpenRouterProvider(settings) as provider:
        result = await provider.chat(request, ResolvedRoute(model=model))

    assert result.content
    assert result.usage.total_tokens > 0
    assert result.usage.cost_usd is not None, "OpenRouter did not report usage.cost"
