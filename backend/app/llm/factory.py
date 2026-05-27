"""Pick the configured provider; default to mock so tests never hit the network."""

from __future__ import annotations

from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider


def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider.lower() == "gemini" and s.gemini_api_key:
        from app.llm.gemini import GeminiProvider

        return GeminiProvider()
    return MockProvider()
