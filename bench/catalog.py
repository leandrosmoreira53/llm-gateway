"""OpenRouter model prices for cost estimates before a paid run; real cost comes from usage.cost."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

CATALOG_URL = "https://openrouter.ai/api/v1/models"


@dataclass(frozen=True)
class Price:
    prompt_per_token: float
    completion_per_token: float
    reasoning: bool

    @property
    def known(self) -> bool:
        # Routers (openrouter/auto, typesafe/jev-router) publish -1: the price depends on the pick.
        return self.prompt_per_token >= 0 and self.completion_per_token >= 0


def fetch_catalog(cache: Path) -> dict[str, Any]:
    """Public endpoint, no key needed. Cached so estimates are reproducible within a run."""
    if cache.exists():
        data: dict[str, Any] = json.loads(cache.read_text(encoding="utf-8"))
        return data
    response = httpx.get(CATALOG_URL, timeout=30)
    response.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(response.text, encoding="utf-8")
    data = response.json()
    return data


def prices(catalog: dict[str, Any]) -> dict[str, Price]:
    out: dict[str, Price] = {}
    for model in catalog.get("data", []):
        pricing = model.get("pricing") or {}
        try:
            out[model["id"]] = Price(
                prompt_per_token=float(pricing.get("prompt", -1)),
                completion_per_token=float(pricing.get("completion", -1)),
                reasoning="reasoning" in (model.get("supported_parameters") or []),
            )
        except (TypeError, ValueError):
            continue
    return out
