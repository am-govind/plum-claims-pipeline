"""LLM provider abstraction.

Two implementations live behind this interface: a Gemini-backed one for the
live UI, and a deterministic mock that reads the pre-extracted `content`
blocks from test_cases.json so the eval suite runs offline.

Each call returns ``(ExtractedDocument, LLMUsage)`` so the orchestrator
can aggregate token + cost per claim. The mock returns realistic-but-fake
usage numbers so the eval report carries cost data even offline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.claim import DocumentInput, ExtractedDocument
from app.models.cost import LLMUsage


class ProviderError(Exception):
    """Generic LLM provider error."""


class LLMTimeoutError(ProviderError):
    """Raised when an LLM call times out — handled by the orchestrator
    so the pipeline degrades gracefully (TC011)."""


class LLMProvider(ABC):
    """Extract a single document into ExtractedDocument; report usage."""

    name: str = "abstract"
    model: str = "abstract"

    @abstractmethod
    async def extract_document(
        self, doc: DocumentInput, *, hint_category: str | None = None
    ) -> tuple[ExtractedDocument, LLMUsage]: ...
