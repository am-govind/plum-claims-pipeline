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
from app.config import get_settings
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
  "extraction_confidence": number between 0 and 1
}

Indian Rx/bill notes: HTN=Hypertension, T2DM=Type 2 Diabetes. Doctor
registration formats look like KA/45678/2015, MH/12345/2018, AYUR/KL/2345/2019.
Mark quality UNREADABLE only if you cannot confidently extract any field.

Respond with the JSON object only, no commentary, no markdown fences.
"""


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        s = get_settings()
        self.api_key = api_key or s.gemini_api_key
        self.model_name = model or s.gemini_model
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
        self, doc: DocumentInput, *, hint_category: str | None = None
    ) -> tuple[ExtractedDocument, LLMUsage]:
        start = time.perf_counter()
        try:
            parts: list[Any] = [EXTRACTION_PROMPT]
            if hint_category:
                parts.append(f"Hint: this is a {hint_category} claim.")

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

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    parts,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.1},
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
