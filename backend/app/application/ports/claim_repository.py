"""Abstract claim persistence port.

The repository speaks the domain language (`ClaimState`, `ClaimSummary`)
and intentionally never returns the SQLAlchemy ORM type. Concrete
adapters live in `app.infrastructure.persistence`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.claim import ClaimState
from app.domain.claim.summary import ClaimSummary


class ClaimRepository(ABC):
    """Persistence port for fully-processed claims."""

    @abstractmethod
    async def save(self, state: ClaimState) -> None:
        """Persist (insert or update) the claim state by ``state.claim_id``."""

    @abstractmethod
    async def get(self, claim_id: str) -> ClaimState | None:
        """Reconstruct a previously saved claim, or return ``None`` if absent."""

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> list[ClaimSummary]:
        """Return the most recent claims as lightweight summaries."""
