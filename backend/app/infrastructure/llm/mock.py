"""Deterministic provider that converts a document's pre-extracted ``content``
block (as supplied in test_cases.json) into an ExtractedDocument.

This is what makes the eval suite reproducible and CI-friendly: no network,
no token cost, no provider variance. Reviewers can rerun `make eval` and
get bit-for-bit identical traces.

The mock returns plausible token counts (length-derived) so the cost
breakdown on the decision card and eval metrics has realistic data.
"""

from __future__ import annotations

import json
import random
import time

from app.application.ports.llm import LLMProvider, ProviderError
from app.domain.claim import DocumentInput, DocumentType, ExtractedDocument, LineItem
from app.domain.cost import LLMUsage, estimate_usd


class MockProvider(LLMProvider):
    name = "mock"
    model = "mock"

    async def extract_document(
        self, doc: DocumentInput, *, hint_category: str | None = None
    ) -> tuple[ExtractedDocument, LLMUsage]:
        start = time.perf_counter()
        if doc.content is None:
            ed = ExtractedDocument(
                file_id=doc.file_id,
                document_type=doc.actual_type,
                quality=doc.quality,
                patient_name=doc.patient_name_on_doc,
                extraction_confidence=0.5
                if doc.actual_type == DocumentType.UNKNOWN
                else 0.7,
                raw={},
            )
            return ed, _make_usage(self.model, doc, start, baseline_in=200, baseline_out=80)

        c = doc.content
        line_items_raw = c.get("line_items", []) or []
        line_items = [
            LineItem(description=str(li["description"]), amount=float(li["amount"]))
            for li in line_items_raw
            if "description" in li and "amount" in li
        ]

        try:
            doc_type = doc.actual_type
            ed = ExtractedDocument(
                file_id=doc.file_id,
                document_type=doc_type,
                quality=doc.quality,
                patient_name=c.get("patient_name") or doc.patient_name_on_doc,
                doctor_name=c.get("doctor_name"),
                doctor_registration=c.get("doctor_registration"),
                diagnosis=c.get("diagnosis"),
                treatment=c.get("treatment"),
                medicines=list(c.get("medicines", []) or []),
                tests_ordered=list(c.get("tests_ordered", []) or [])
                + ([c["test_name"]] if c.get("test_name") else []),
                hospital_name=c.get("hospital_name"),
                bill_number=c.get("bill_number"),
                document_date=c.get("date"),
                line_items=line_items,
                total_amount=float(c["total"]) if c.get("total") is not None else None,
                extraction_confidence=0.95,
                raw=dict(c),
            )
            return ed, _make_usage(self.model, doc, start, baseline_in=400, payload=c)
        except (TypeError, ValueError) as e:
            raise ProviderError(f"Failed to parse mock content for {doc.file_id}: {e}") from e


def _make_usage(
    model: str,
    doc: DocumentInput,
    start: float,
    *,
    baseline_in: int = 300,
    baseline_out: int = 120,
    payload: dict | None = None,
) -> LLMUsage:
    """Synthesize realistic token + latency numbers from the doc payload.

    For the mock provider we don't actually call an LLM, but we still want
    the cost card on the decision page and the eval report to show
    plausible numbers. Tokens scale roughly with payload size.
    """
    rng = random.Random(hash(doc.file_id) & 0xFFFFFFFF)
    payload_size = len(json.dumps(payload or {}, default=str))
    tokens_in = baseline_in + payload_size // 3 + rng.randint(0, 50)
    tokens_out = baseline_out + payload_size // 6 + rng.randint(0, 40)
    latency_ms = int((time.perf_counter() - start) * 1000) + rng.randint(80, 320)
    return LLMUsage(
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        usd_estimate=estimate_usd(model, tokens_in, tokens_out),
        file_id=doc.file_id,
    )
