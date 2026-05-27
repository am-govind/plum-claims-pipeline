"""Extraction agent: runs the configured LLM provider per document.

Per-document failures are absorbed: a single bad document drops its own
extraction confidence and is recorded in the trace, but does not abort the
pipeline. If the entire batch fails, the orchestrator routes the claim to
manual review (TC011).
"""

from __future__ import annotations

import asyncio

from app.application.agents.base import BaseAgent
from app.application.ports.llm import LLMProvider, LLMTimeoutError, ProviderError
from app.domain.claim import ClaimState, ExtractedDocument
from app.domain.decision import AgentResult
from app.domain.services.extraction_validator import validate_extraction
from app.domain.trace import TraceStatus


class ExtractionAgent(BaseAgent):
    name = "extraction"
    is_critical = False

    def __init__(self, *, llm_provider: LLMProvider) -> None:
        self._provider = llm_provider

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            inp = state.input
            extracted: list[ExtractedDocument] = []
            failures: list[dict] = []

            results = await asyncio.gather(
                *[
                    self._safe_extract(d, hint_category=inp.claim_category.value)
                    for d in inp.documents
                ]
            )
            for r in results:
                if isinstance(r, tuple):
                    ed, usage = r
                    extracted.append(ed)
                    state.cost.add_llm(usage)
                else:
                    failures.append(r)

            validation_issues_total = 0
            for doc in extracted:
                issues = validate_extraction(doc)
                validation_issues_total += len(issues)

            state.extracted = extracted

            if validation_issues_total:
                rec.record(
                    "extraction_validation",
                    status=TraceStatus.WARNING,
                    summary=(
                        f"{validation_issues_total} extraction validation issue(s) "
                        f"flagged across {sum(1 for d in extracted if d.validation_issues)} document(s)"
                    ),
                    evidence={
                        "issues_by_file": {
                            d.file_id: d.validation_issues
                            for d in extracted
                            if d.validation_issues
                        },
                    },
                    confidence_delta=-0.05 * min(validation_issues_total, 4),
                    latency_ms=0,
                )

            avg_conf = (
                sum(d.extraction_confidence for d in extracted) / len(extracted)
                if extracted
                else 0.0
            )
            state.agent_results[self.name] = AgentResult(
                confidence=avg_conf,
                evidence_strength=1.0 if extracted else 0.0,
                contradiction_score=0.0,
                notes=[
                    f"{d.file_id}: conf={d.extraction_confidence:.2f}"
                    + (f" issues={len(d.validation_issues)}" if d.validation_issues else "")
                    for d in extracted
                ],
            )

            if failures and not extracted:
                rec.record(
                    self.name,
                    status=TraceStatus.ERROR,
                    summary=f"All {len(failures)} extractions failed",
                    evidence={"failures": failures, "provider": self.provider.name},
                    confidence_delta=-0.4,
                    latency_ms=ctx["latency_ms"],
                    error="EXTRACTION_TOTAL_FAILURE",
                )
                state.degraded = True
                state.failed_components.append(self.name)
            elif failures:
                rec.record(
                    self.name,
                    status=TraceStatus.WARNING,
                    summary=f"Extracted {len(extracted)} of {len(inp.documents)} documents",
                    evidence={
                        "extracted_files": [e.file_id for e in extracted],
                        "failures": failures,
                        "provider": self.provider.name,
                    },
                    confidence_delta=-0.1,
                    latency_ms=ctx["latency_ms"],
                )
            else:
                rec.record(
                    self.name,
                    status=TraceStatus.OK,
                    summary=f"Extracted {len(extracted)} document(s) with provider={self.provider.name}",
                    evidence={
                        "documents": [
                            {
                                "file_id": e.file_id,
                                "type": e.document_type.value,
                                "patient": e.patient_name,
                                "diagnosis": e.diagnosis,
                                "total": e.total_amount,
                                "line_items": len(e.line_items),
                                "confidence": e.extraction_confidence,
                            }
                            for e in extracted
                        ],
                        "provider": self.provider.name,
                    },
                    latency_ms=ctx["latency_ms"],
                )
        return state

    async def _safe_extract(self, doc, *, hint_category: str | None):
        try:
            return await self.provider.extract_document(doc, hint_category=hint_category)
        except (ProviderError, LLMTimeoutError) as e:
            return {"file_id": doc.file_id, "error": str(e), "type": e.__class__.__name__}
        except Exception as e:  # noqa: BLE001
            return {"file_id": doc.file_id, "error": str(e), "type": e.__class__.__name__}
