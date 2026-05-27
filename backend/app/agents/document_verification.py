"""Document Verification Agent.

Runs three checks before any expensive extraction:
  1. Required document types present (TC001).
  2. No unreadable documents (TC002).
  3. All documents belong to the same patient (TC003).

Failures raise typed errors that map to specific, actionable user messages.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from app.agents.base import BaseAgent
from app.models.agent_result import AgentResult
from app.models.claim import ClaimState, DocumentInput, DocumentQuality, DocumentType
from app.models.errors import (
    DocumentTypeMismatchError,
    PatientMismatchError,
    UnreadableDocumentError,
    error_to_user_message,
)
from app.models.trace import TraceStatus
from app.policy.loader import get_policy

NAME_SIMILARITY_THRESHOLD = 80


class DocumentVerificationAgent(BaseAgent):
    name = "document_verification"
    is_critical = True

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            policy = get_policy()
            inp = state.input
            requirements = policy.document_requirements.get(inp.claim_category.value, {})
            required = list(requirements.get("required", []))

            uploaded_types = [d.actual_type.value for d in inp.documents]
            missing = [r for r in required if r not in uploaded_types]

            if missing:
                err = DocumentTypeMismatchError(
                    uploaded_types=uploaded_types,
                    required_types=required,
                    missing_types=missing,
                    category=inp.claim_category.value,
                )
                self._halt(state, rec, err, ctx["latency_ms"], step="type_check")
                return state

            unreadable = next(
                (d for d in inp.documents if d.quality == DocumentQuality.UNREADABLE), None
            )
            if unreadable:
                err = UnreadableDocumentError(
                    file_id=unreadable.file_id,
                    file_name=unreadable.file_name,
                    document_type=unreadable.actual_type.value,
                )
                self._halt(state, rec, err, ctx["latency_ms"], step="quality_check")
                return state

            mismatch = self._patient_mismatch(inp.documents)
            if mismatch:
                err = PatientMismatchError(names_by_file=mismatch)
                self._halt(state, rec, err, ctx["latency_ms"], step="patient_match")
                return state

            rec.record(
                self.name,
                status=TraceStatus.OK,
                summary=(
                    f"All {len(inp.documents)} document(s) verified for "
                    f"{inp.claim_category.value} (required: {required})"
                ),
                evidence={
                    "uploaded_types": uploaded_types,
                    "required_types": required,
                    "qualities": [d.quality.value for d in inp.documents],
                    "patient_names": [
                        d.patient_name_on_doc for d in inp.documents if d.patient_name_on_doc
                    ],
                },
                latency_ms=ctx["latency_ms"],
            )
            state.agent_results[self.name] = AgentResult(
                confidence=1.0,
                evidence_strength=1.0,
                contradiction_score=0.0,
                notes=["all_documents_verified"],
            )
        return state

    def _halt(self, state: ClaimState, rec, err, latency_ms: int, *, step: str) -> None:
        rec.record(
            self.name,
            status=TraceStatus.EARLY_STOP,
            summary=f"{err.code} ({step}): {err.message}",
            evidence={**err.evidence, "check": step},
            confidence_delta=-0.5,
            latency_ms=latency_ms,
            error=err.code,
        )
        state.early_stop = True
        state.early_stop_reason = err.code
        state.early_stop_user_message = error_to_user_message(err)

    @staticmethod
    def _patient_mismatch(documents: list[DocumentInput]) -> dict[str, str] | None:
        names = {d.file_id: d.patient_name_on_doc for d in documents if d.patient_name_on_doc}
        if len(names) < 2:
            return None
        name_list = list(names.values())
        canonical = name_list[0]
        for n in name_list[1:]:
            if fuzz.token_set_ratio(canonical, n) < NAME_SIMILARITY_THRESHOLD:
                return names
        return None
