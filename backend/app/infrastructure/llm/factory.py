"""Build the configured `LLMProvider` from a `Settings`.

This is the only place that knows about provider selection; the
composition root calls it once and stores the resulting provider on
the container.
"""

from __future__ import annotations

from app.application.ports.llm import LLMProvider
from app.config import Settings
from app.infrastructure.llm.mock import MockProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider.lower() == "gemini" and settings.gemini_api_key:
        from app.infrastructure.llm.gemini import GeminiProvider

        return GeminiProvider(
            api_key=settings.gemini_api_key, model=settings.gemini_model
        )
    return MockProvider()
