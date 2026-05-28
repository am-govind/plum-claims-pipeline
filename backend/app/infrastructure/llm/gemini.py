"""Gemini-backed extraction provider.

Uses google-generativeai with vision input where available. Returns the
ExtractedDocument shape so the rest of the pipeline doesn't care which
provider produced the data.

If the API key is missing or the call fails/times out, raise the typed
errors so the orchestrator can mark the component as failed and continue
in degraded mode.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

from app.application.ports.llm import LLMProvider, LLMTimeoutError, ProviderError
from app.domain.claim import DocumentInput, DocumentType, ExtractedDocument, LineItem
from app.domain.cost import LLMUsage, estimate_usd

EXTRACTION_PROMPT = """You are a medical document extraction agent for an Indian
health insurance claims pipeline. Extract a strict JSON object with these keys
(use null where not present, do not invent values):

{
  "document_type": one of [PRESCRIPTION, HOSPITAL_BILL, PHARMACY_BILL, LAB_REPORT,
                           DIAGNOSTIC_REPORT, DISCHARGE_SUMMARY, DENTAL_REPORT, UNKNOWN],
  "quality": one of [GOOD, ACCEPTABLE, POOR, UNREADABLE],
  "patient_name": string|null,
  "doctor_name": string|null,
  "doctor_registration": string|null,
  "diagnosis": string|null,
  "treatment": string|null,
  "medicines": [string],
  "tests_ordered": [string],
  "hospital_name": string|null,
  "bill_number": string|null,
  "document_date": "YYYY-MM-DD"|null,
  "line_items": [{"description": string, "amount": number}],
  "total_amount": number|null,
  "extraction_confidence": number between 0 and 1,
  "flags": [string]   // optional audit flags, see "Real-world dirt" below
}

Indian Rx/bill conventions you will encounter:
  - Shorthand: HTN=Hypertension, T2DM=Type 2 Diabetes, COPD, IHD, MI, CKD.
  - Doctor registration formats: KA/45678/2015, MH/12345/2018, AYUR/KL/2345/2019.
  - GSTIN on bills (15-char), drug license numbers on pharmacy bills,
    NABL/CAP accreditation on lab reports. Capture if visible; do not
    invent.

Real-world dirt — handle these instead of failing the whole document:
  - Rubber stamps over text ("PAID", "VERIFIED", "ORIGINAL", "DUPLICATE"):
    extract surrounding readable text; mark the covered field's
    extraction_confidence LOW but keep the document. Add "STAMP_OVERLAY"
    to "flags".
  - Multi-page PDFs: aggregate line items across pages; pick one
    document_type (the most clinically relevant); sum total_amount once.
  - Handwritten prescriptions: extract what you can read; medicines you
    can't decipher should be omitted, not guessed. Lower confidence to
    reflect uncertainty.
  - Regional language sections (Hindi, Tamil, etc.) mixed with English:
    extract the English portions; do not transliterate guesses for
    Indian-language fields.
  - Cancellations / corrections / strike-throughs / overwritten
    amounts: capture the corrected value if obvious; otherwise omit and
    add "DOCUMENT_ALTERATION" to "flags" so the fraud agent can pick it
    up downstream.
  - Partial pages (cropped/scrolled scans): extract visible content and
    add "PARTIAL_PAGE" to "flags".

Mark quality UNREADABLE only when no clinically significant field can be
extracted with reasonable confidence. A single stamp over a doctor name
is NOT UNREADABLE.

Respond with the JSON object only, no commentary, no markdown fences.
"""

_FEEDBACK_PREAMBLE = """A previous extraction attempt produced validation
issues. Re-extract this document with the issues below in mind; favour
correcting them only when the document genuinely supports it (do not
invent values to make the validator happy).

Validation issues:
"""


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model_name = model
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY not set")
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
        except ImportError as e:
            raise ProviderError("google-generativeai not installed") from e

    @property
    def model(self) -> str:  # noqa: D401
        return self.model_name

    async def extract_document(
        self,
        doc: DocumentInput,
        *,
        hint_category: str | None = None,
        feedback: str | None = None,
    ) -> tuple[ExtractedDocument, LLMUsage]:
        start = time.perf_counter()
        if not (doc.bytes_b64 and doc.mime_type) and _is_rich_content(doc.content):
            # Pre-extracted via /api/claims/extract-preview earlier in the same
            # session, or supplied directly as structured content. We must NOT
            # call Gemini again here: it would either waste a token round-trip
            # (best case) or hallucinate from a filename hint (worst case) and
            # overwrite values the customer already confirmed. Build the
            # ExtractedDocument from content with a zero-cost usage record so
            # the pipeline's cost tracker stays accurate.
            extracted = _to_extracted(
                doc.file_id, _content_to_gemini_shape(doc.content or {}, doc)
            )
            usage = LLMUsage(
                model=self.model_name,
                tokens_in=0,
                tokens_out=0,
                latency_ms=int((time.perf_counter() - start) * 1000),
                usd_estimate=0.0,
                file_id=doc.file_id,
            )
            return extracted, usage

        try:
            parts: list[Any] = [EXTRACTION_PROMPT]
            if hint_category:
                parts.append(f"Hint: this is a {hint_category} claim.")
            if feedback:
                parts.append(_FEEDBACK_PREAMBLE + feedback)

            if doc.bytes_b64 and doc.mime_type:
                parts.append(
                    {
                        "mime_type": doc.mime_type,
                        "data": base64.b64decode(doc.bytes_b64),
                    }
                )
            elif doc.file_name:
                parts.append(f"Document filename: {doc.file_name}")
            else:
                parts.append(f"File id: {doc.file_id}")

            # First pass uses very low temperature for stable extraction.
            # Retry pass (feedback present) bumps to 0.4 so the model is
            # actually allowed to *change* its mind given the new
            # validator-driven hints; cap is 0.4 — beyond that we'd start
            # inviting hallucination, defeating the point of retrying.
            temperature = 0.4 if feedback else 0.1
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    parts,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": temperature,
                    },
                ),
                timeout=30.0,
            )
            text = (response.text or "").strip()
            data = _parse_json(text)
            extracted = _to_extracted(doc.file_id, data)

            usage_meta = getattr(response, "usage_metadata", None)
            tokens_in = int(getattr(usage_meta, "prompt_token_count", 0) or 0)
            tokens_out = int(getattr(usage_meta, "candidates_token_count", 0) or 0)
            latency_ms = int((time.perf_counter() - start) * 1000)
            usage = LLMUsage(
                model=self.model_name,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                usd_estimate=estimate_usd(self.model_name, tokens_in, tokens_out),
                file_id=doc.file_id,
            )
            return extracted, usage
        except asyncio.TimeoutError as e:
            raise LLMTimeoutError(f"Gemini timeout for {doc.file_id}") from e
        except (ProviderError, LLMTimeoutError):
            raise
        except Exception as e:
            raise ProviderError(f"Gemini call failed for {doc.file_id}: {e}") from e


_RICH_CONTENT_KEYS = (
    "patient_name",
    "diagnosis",
    "doctor_name",
    "hospital_name",
    "total",
    "total_amount",
    "medicines",
    "line_items",
)


def _is_rich_content(content: dict[str, Any] | None) -> bool:
    """A content dict counts as pre-extracted if it has at least one of the
    fields the extraction agent actually consumes downstream."""
    if not content:
        return False
    return any(content.get(k) not in (None, "", [], {}) for k in _RICH_CONTENT_KEYS)


def _content_to_gemini_shape(content: dict[str, Any], doc: DocumentInput) -> dict[str, Any]:
    """Normalise a frontend/test_cases.json content dict to the schema
    `_to_extracted` expects (which mirrors the Gemini response schema).

    Falls back to document-level metadata (`actual_type`, `quality`) when the
    content dict doesn't carry those keys explicitly. Sets a high default
    confidence because content reaching this branch was either user-confirmed
    in the preview UI or pre-extracted in a test fixture.
    """
    d = dict(content)
    if "total_amount" not in d and "total" in d:
        d["total_amount"] = d["total"]
    if "document_date" not in d and "date" in d:
        d["document_date"] = d["date"]
    if "tests_ordered" not in d and "test_name" in d:
        d["tests_ordered"] = [d["test_name"]]
    d.setdefault("document_type", doc.actual_type.value)
    d.setdefault("quality", doc.quality.value)
    if "patient_name" not in d and doc.patient_name_on_doc:
        d["patient_name"] = doc.patient_name_on_doc
    d.setdefault("extraction_confidence", 0.92)
    return d


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ProviderError("Gemini did not return parseable JSON")


def _to_extracted(file_id: str, data: dict[str, Any]) -> ExtractedDocument:
    line_items = [
        LineItem(description=str(li["description"]), amount=float(li["amount"]))
        for li in data.get("line_items") or []
        if "description" in li and "amount" in li
    ]
    try:
        doc_type = DocumentType(data.get("document_type", "UNKNOWN"))
    except ValueError:
        doc_type = DocumentType.UNKNOWN
    return ExtractedDocument(
        file_id=file_id,
        document_type=doc_type,
        quality=data.get("quality", "GOOD"),
        patient_name=data.get("patient_name"),
        doctor_name=data.get("doctor_name"),
        doctor_registration=data.get("doctor_registration"),
        diagnosis=data.get("diagnosis"),
        treatment=data.get("treatment"),
        medicines=list(data.get("medicines") or []),
        tests_ordered=list(data.get("tests_ordered") or []),
        hospital_name=data.get("hospital_name"),
        bill_number=data.get("bill_number"),
        document_date=data.get("document_date"),
        line_items=line_items,
        total_amount=data.get("total_amount"),
        extraction_confidence=float(data.get("extraction_confidence", 0.7)),
        raw=data,
    )
