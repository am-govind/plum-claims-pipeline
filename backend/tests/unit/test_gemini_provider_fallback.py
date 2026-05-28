"""GeminiProvider content-fallback test.

When the pipeline runs extraction at submit-time, documents arrive without
`bytes_b64` (the form deliberately stripped them) but with a populated
`content` dict. The provider must build the `ExtractedDocument` from
content WITHOUT calling Gemini - otherwise we would either pay for a
second OCR pass on the same document or have Gemini hallucinate from a
filename hint.

This test mocks out `google.generativeai` so we don't need network or
an API key, and asserts the model was never invoked.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from app.domain.claim import DocumentInput, DocumentQuality, DocumentType


class _FakeModel:
    """Stand-in for `genai.GenerativeModel` that fails if called."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:  # noqa: D401, ARG002
        self.calls += 1
        raise AssertionError(
            "GeminiProvider should not call generate_content when content "
            "is already supplied and bytes are missing"
        )


@pytest.fixture
def fake_genai(monkeypatch: pytest.MonkeyPatch) -> _FakeModel:
    """Install a fake `google.generativeai` module in sys.modules so the
    GeminiProvider can be imported and constructed without the real SDK."""
    fake_module = types.ModuleType("google.generativeai")
    fake_model = _FakeModel()

    def _configure(api_key: str) -> None:  # noqa: ARG001
        return None

    def _generative_model(model_name: str) -> _FakeModel:  # noqa: ARG001
        return fake_model

    fake_module.configure = _configure  # type: ignore[attr-defined]
    fake_module.GenerativeModel = _generative_model  # type: ignore[attr-defined]

    google_pkg = types.ModuleType("google")
    google_pkg.generativeai = fake_module  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_module)
    return fake_model


@pytest.mark.asyncio
async def test_content_fallback_skips_llm_call(fake_genai: _FakeModel):
    from app.infrastructure.llm.gemini import GeminiProvider

    provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")

    doc = DocumentInput(
        file_id="F001",
        file_name="prescription.jpg",
        actual_type=DocumentType.PRESCRIPTION,
        quality=DocumentQuality.GOOD,
        patient_name_on_doc="Rajesh Kumar",
        content={
            "patient_name": "Rajesh Kumar",
            "diagnosis": "Acute Bronchitis",
            "doctor_name": "Dr. Mehta",
            "doctor_registration": "KA/45678/2015",
            "total": 1500,
        },
    )

    extracted, usage = await provider.extract_document(doc, hint_category="CONSULTATION")

    assert fake_genai.calls == 0
    assert usage.tokens_in == 0 and usage.tokens_out == 0
    assert usage.usd_estimate == 0.0
    assert extracted.diagnosis == "Acute Bronchitis"
    assert extracted.patient_name == "Rajesh Kumar"
    assert extracted.total_amount == pytest.approx(1500.0)
    assert extracted.document_type == DocumentType.PRESCRIPTION


@pytest.mark.asyncio
async def test_empty_content_still_calls_llm(fake_genai: _FakeModel):
    """An empty/sparse content dict (e.g. just `{}` or just a hint key) must
    not short-circuit; otherwise we'd silently skip OCR. The fake_genai's
    raise is our assertion that the call WAS attempted."""
    from app.infrastructure.llm.gemini import GeminiProvider

    provider = GeminiProvider(api_key="fake-key", model="gemini-2.0-flash")

    doc = DocumentInput(
        file_id="F001",
        file_name="prescription.jpg",
        actual_type=DocumentType.PRESCRIPTION,
        quality=DocumentQuality.GOOD,
        content={},
    )

    with pytest.raises(Exception):  # noqa: PT011, BLE001
        await provider.extract_document(doc, hint_category="CONSULTATION")
    assert fake_genai.calls == 1
