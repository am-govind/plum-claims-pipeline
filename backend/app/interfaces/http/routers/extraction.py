"""Extraction preview endpoint.

The `/submit` form posts a single uploaded document (image or PDF, as
base64 in `bytes_b64` + `mime_type`) and receives the structured
`ExtractedDocument` so it can auto-populate the typed fields. The
endpoint runs *only* the configured LLM provider — no pipeline, no
persistence, no events. Re-using the same provider the pipeline uses
means the preview the customer sees is the same extraction the
pipeline would have produced at submit-time.

Provider failures (timeouts, parsing errors, missing API key) return a
structured `{ok: false, ...}` payload with HTTP 200 so the form can
surface a precise, actionable message without aborting the whole
session.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.ports.llm import LLMTimeoutError, ProviderError
from app.composition import Container
from app.domain.claim import DocumentInput, ExtractedDocument
from app.domain.cost import LLMUsage
from app.domain.services.extraction_validator import validate_extraction
from app.interfaces.http.deps import get_container

router = APIRouter(prefix="/api/claims", tags=["claims"])


class ExtractPreviewRequest(BaseModel):
    document: DocumentInput
    hint_category: str | None = None


class ExtractPreviewResponse(BaseModel):
    """Either an extraction succeeded (`ok=True`) or it failed cleanly with
    a typed reason. We never raise out of this endpoint for provider-level
    failures — the form handles them inline."""

    ok: bool
    extracted: ExtractedDocument | None = None
    usage: LLMUsage | None = None
    validation_issues: list[str] = []
    reason: str | None = None
    message: str | None = None


@router.post("/extract-preview", response_model=ExtractPreviewResponse)
async def extract_preview(
    payload: ExtractPreviewRequest,
    container: Container = Depends(get_container),
) -> ExtractPreviewResponse:
    try:
        extracted, usage = await container.llm_provider.extract_document(
            payload.document, hint_category=payload.hint_category
        )
    except (ProviderError, LLMTimeoutError) as e:
        return ExtractPreviewResponse(
            ok=False,
            reason=e.__class__.__name__,
            message=str(e),
        )
    except Exception as e:  # noqa: BLE001
        # Last-resort safety net: surface the type so the UI can show
        # "unexpected extraction failure" without 500-ing.
        return ExtractPreviewResponse(
            ok=False,
            reason=e.__class__.__name__,
            message=str(e),
        )

    issues = validate_extraction(extracted)
    return ExtractPreviewResponse(
        ok=True,
        extracted=extracted,
        usage=usage,
        validation_issues=issues,
    )
