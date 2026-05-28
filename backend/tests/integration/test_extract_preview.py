"""Integration tests for POST /api/claims/extract-preview.

The endpoint must:
  - run the configured LLM provider on a single document
  - return `{ok: true, extracted}` for normal extractions
  - return `{ok: false, reason, message}` (HTTP 200) for provider failures so
    the form can show inline guidance rather than a generic 500
  - reject oversized `bytes_b64` payloads with HTTP 422
"""

from __future__ import annotations

import base64

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.ports.llm import LLMProvider, ProviderError
from app.composition import Container
from app.domain.claim import DocumentInput, ExtractedDocument
from app.domain.cost import LLMUsage
from app.interfaces.http.app import create_app


def _attach_container(app, container: Container) -> None:
    """The preview endpoint only needs `app.state.container`; we skip the
    lifespan dance because no DB init is required for extraction."""
    app.state.container = container


def _build_client(container: Container) -> AsyncClient:
    app = create_app()
    _attach_container(app, container)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_preview_with_content_returns_echo(container: Container):
    async with _build_client(container) as client:
        doc = {
            "file_id": "F001",
            "file_name": "rx.jpg",
            "actual_type": "PRESCRIPTION",
            "quality": "GOOD",
            "patient_name_on_doc": "Rajesh Kumar",
            "content": {
                "patient_name": "Rajesh Kumar",
                "diagnosis": "Acute Pharyngitis",
                "doctor_name": "Dr. Mehta",
                "doctor_registration": "KA/45678/2015",
                "total": 1500,
            },
        }
        resp = await client.post(
            "/api/claims/extract-preview",
            json={"document": doc, "hint_category": "CONSULTATION"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["extracted"]["patient_name"] == "Rajesh Kumar"
    assert body["extracted"]["diagnosis"] == "Acute Pharyngitis"
    assert body["extracted"]["extraction_confidence"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_preview_with_bytes_returns_low_confidence_stub(container: Container):
    """When the mock provider receives raw bytes (no content), it must
    return the explicit low-confidence stub so the demo flow is honest
    about what happened without a real vision model."""
    async with _build_client(container) as client:
        payload = base64.b64encode(b"fake-jpeg-bytes" * 100).decode()
        doc = {
            "file_id": "F001",
            "file_name": "rx.jpg",
            "actual_type": "PRESCRIPTION",
            "quality": "GOOD",
            "patient_name_on_doc": "Rajesh Kumar",
            "bytes_b64": payload,
            "mime_type": "image/jpeg",
        }
        resp = await client.post(
            "/api/claims/extract-preview",
            json={"document": doc, "hint_category": "CONSULTATION"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["extracted"]["extraction_confidence"] == pytest.approx(0.45)
    assert body["extracted"]["raw"]["_mock_source"] == "uploaded_bytes_stub"


@pytest.mark.asyncio
async def test_preview_rejects_oversized_bytes(container: Container):
    """The `DocumentInput.bytes_b64` validator must trip BEFORE the
    provider is invoked, so a 50 MB upload doesn't pin Gemini for 30 s."""
    async with _build_client(container) as client:
        payload = "A" * 15_000_000
        doc = {
            "file_id": "F001",
            "file_name": "huge.jpg",
            "actual_type": "PRESCRIPTION",
            "quality": "GOOD",
            "bytes_b64": payload,
            "mime_type": "image/jpeg",
        }
        resp = await client.post(
            "/api/claims/extract-preview",
            json={"document": doc, "hint_category": "CONSULTATION"},
        )

    assert resp.status_code == 422
    # Pydantic error message references our custom validator copy.
    assert "10 MB" in resp.text


class _FailingProvider(LLMProvider):
    name = "failing"
    model = "failing"

    async def extract_document(
        self, doc: DocumentInput, *, hint_category: str | None = None
    ) -> tuple[ExtractedDocument, LLMUsage]:  # noqa: ARG002
        raise ProviderError("LLM is on fire")


@pytest.mark.asyncio
async def test_preview_provider_failure_returns_structured_ok_false(
    container: Container,
):
    """ProviderError must surface as `{ok: false, reason, message}` so the
    form can show inline guidance instead of treating it as an unrecoverable
    HTTP error."""
    # Swap the provider on a shallow-copied container so the rest of the
    # fixture stays clean.
    from dataclasses import replace

    failing = _FailingProvider()
    failing_container = replace(container, llm_provider=failing)

    async with _build_client(failing_container) as client:
        doc = {
            "file_id": "F001",
            "file_name": "rx.jpg",
            "actual_type": "PRESCRIPTION",
            "quality": "GOOD",
            "content": {"patient_name": "Rajesh Kumar"},
        }
        resp = await client.post(
            "/api/claims/extract-preview",
            json={"document": doc, "hint_category": "CONSULTATION"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["reason"] == "ProviderError"
    assert "LLM is on fire" in body["message"]
    assert body["extracted"] is None
