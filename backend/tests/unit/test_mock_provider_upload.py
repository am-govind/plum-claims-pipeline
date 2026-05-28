"""MockProvider behaviour for the upload + preview path.

The mock has three branches:
  - typed-only fallback        (no content, no bytes)  -> medium confidence
  - upload stub                 (no content, bytes set) -> low  confidence + marker
  - structured-content echo     (content provided)      -> high confidence
"""

from __future__ import annotations

import base64

import pytest

from app.domain.claim import DocumentInput, DocumentQuality, DocumentType
from app.infrastructure.llm.mock import MockProvider


def _doc(**overrides) -> DocumentInput:
    base = dict(
        file_id="F001",
        file_name="document_1.jpg",
        actual_type=DocumentType.PRESCRIPTION,
        quality=DocumentQuality.GOOD,
        patient_name_on_doc="Rajesh Kumar",
    )
    base.update(overrides)
    return DocumentInput(**base)


@pytest.mark.asyncio
async def test_upload_without_content_returns_low_confidence_stub():
    provider = MockProvider()
    payload = base64.b64encode(b"fake-jpeg-bytes" * 10).decode()
    doc = _doc(bytes_b64=payload, mime_type="image/jpeg")

    extracted, usage = await provider.extract_document(doc)

    assert extracted.extraction_confidence == pytest.approx(0.45, abs=1e-6)
    assert extracted.raw.get("_mock_source") == "uploaded_bytes_stub"
    assert extracted.patient_name == "Rajesh Kumar"
    assert extracted.document_type == DocumentType.PRESCRIPTION
    assert usage.tokens_in > 0
    assert usage.file_id == "F001"


@pytest.mark.asyncio
async def test_content_wins_over_bytes_when_both_supplied():
    """If `content` is present, the echo branch should always win - the
    pipeline's submit-time extraction sends content but no bytes, so this
    branch is the hot path in production. It must not fall into the
    upload-stub branch by accident."""
    provider = MockProvider()
    payload = base64.b64encode(b"ignored").decode()
    doc = _doc(
        bytes_b64=payload,
        mime_type="image/jpeg",
        content={
            "patient_name": "Rajesh Kumar",
            "diagnosis": "Acute Pharyngitis",
            "doctor_name": "Dr. Mehta",
            "doctor_registration": "KA/45678/2015",
        },
    )

    extracted, _ = await provider.extract_document(doc)

    assert extracted.extraction_confidence == pytest.approx(0.95, abs=1e-6)
    assert extracted.diagnosis == "Acute Pharyngitis"
    assert extracted.raw.get("_mock_source") is None


@pytest.mark.asyncio
async def test_typed_only_fallback_unchanged():
    """No content, no bytes - the original "manual fields only" stub.
    Guarantees the eval suite path still works for cases where the test
    fixture omits `content` entirely."""
    provider = MockProvider()
    doc = _doc()

    extracted, _ = await provider.extract_document(doc)

    assert extracted.extraction_confidence == pytest.approx(0.7, abs=1e-6)
    assert extracted.raw == {}
