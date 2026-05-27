"""Decision Synthesizer.

Aggregates findings, line-item decisions, and fraud signals into a final
``Decision`` with status, approved amount, reasons, confidence, and a
user-facing message. Order of precedence:

  1. Hard rejections (waiting period, exclusion, pre-auth missing,
     per-claim limit, prescription missing, coverage failure).
  2. Manual review (fraud signals, simulated component failure, or
     extraction total failure).
  3. Partial (line-item exclusions present and final amount > 0).
  4. Approved (everything passed, final amount > 0).
  5. Rejected (final amount = 0 with no other reason).
"""

from __future__ import annotations

from app.application.agents.base import BaseAgent
from app.domain.claim import ClaimState
from app.domain.decision import (
    Decision,
    DecisionStatus,
    PolicyFinding,
    RejectionReason,
)
from app.domain.events import (
    ClaimApproved,
    ClaimPartiallyApproved,
    ClaimRejected,
    DomainEvent,
    ManualReviewRequired,
)
from app.domain.services.confidence import ConfidenceConfig, compute_confidence
from app.domain.services.explanation_builder import build_explanation_tree
from app.domain.trace import TraceStatus

HARD_REJECT_CODES: set[str] = {
    RejectionReason.WAITING_PERIOD.value,
    RejectionReason.EXCLUDED_CONDITION.value,
    RejectionReason.PRE_AUTH_MISSING.value,
    RejectionReason.PER_CLAIM_EXCEEDED.value,
    RejectionReason.PRESCRIPTION_MISSING.value,
    RejectionReason.SUBMISSION_DEADLINE.value,
    RejectionReason.BELOW_MIN_CLAIM.value,
}


class DecisionSynthesizerAgent(BaseAgent):
    name = "decision_synthesizer"
    is_critical = True

    def __init__(self, *, confidence_config: ConfidenceConfig) -> None:
        self._confidence_config = confidence_config

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            financial = next(
                (f for f in state.findings if f.code == "FINANCIAL_CALCULATION"), None
            )
            breakdown = financial.evidence if financial else {}
            final_amount = float(breakdown.get("final_approved_amount", 0.0))

            hard_rejections = [
                f for f in state.findings if f.code in HARD_REJECT_CODES and not f.passed
            ]
            had_excluded_lines = any(
                f.code == RejectionReason.LINE_ITEM_EXCLUDED.value and not f.passed
                for f in state.findings
            )
            has_coverage_failure = any(
                f.code == "COVERAGE_CHECK" and not f.passed for f in state.findings
            )

            conf_calc = compute_confidence(state, self._confidence_config)
            confidence = conf_calc.final
            confidence_breakdown = conf_calc.to_breakdown()
            state.confidence = round(confidence, 4)

            if has_coverage_failure or hard_rejections:
                rejections = [
                    self._to_rejection_code(f.code) for f in hard_rejections
                ]
                if has_coverage_failure:
                    rejections = list(
                        dict.fromkeys(rejections + [RejectionReason.CATEGORY_NOT_COVERED])
                    )

                primary_reason = hard_rejections[0] if hard_rejections else _coverage_finding(state)
                user_msg = self._user_message_for_rejection(state, primary_reason, breakdown)
                summary = primary_reason.message
                state.decision = Decision(
                    status=DecisionStatus.REJECTED,
                    approved_amount=0.0,
                    submitted_amount=state.input.claimed_amount,
                    rejection_reasons=rejections,
                    confidence=round(confidence, 3),
                    summary=summary,
                    user_message=user_msg,
                    notes=[f.message for f in hard_rejections],
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    degraded=state.degraded,
                    failed_components=state.failed_components,
                )
            elif state.fraud_signals and any(
                c.kind in {"PATIENT_NAME_INCONSISTENT", "AMOUNT_RECONCILIATION_FAILED"}
                for c in state.contradictions
            ):
                user_msg = (
                    "Your claim has been routed to a fraud investigation queue "
                    "because we detected both unusual claim patterns AND "
                    "cross-document inconsistencies. A reviewer will contact you "
                    "if more information is needed."
                )
                state.decision = Decision(
                    status=DecisionStatus.FRAUD_INVESTIGATION,
                    approved_amount=0.0,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary="Fraud signals + contradictions require investigation",
                    user_message=user_msg,
                    notes=state.fraud_signals + [c.description for c in state.contradictions],
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    requires_manual_review=True,
                    degraded=state.degraded,
                    failed_components=state.failed_components,
                )
            elif any(
                c.kind == "DIAGNOSIS_TREATMENT_MISMATCH" for c in state.contradictions
            ):
                user_msg = (
                    "Your claim has been escalated for medical review because "
                    "the diagnosis and the prescribed treatment/tests do not "
                    "appear consistent. A medical reviewer will assess the "
                    "documentation; you'll hear back within 3 business days."
                )
                state.decision = Decision(
                    status=DecisionStatus.ESCALATED_MEDICAL_REVIEW,
                    approved_amount=0.0,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary="Diagnosis-treatment compatibility check failed",
                    user_message=user_msg,
                    notes=[c.description for c in state.contradictions],
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    requires_manual_review=True,
                    degraded=state.degraded,
                    failed_components=state.failed_components,
                )
            elif state.fraud_signals:
                user_msg = self._manual_review_message(state)
                state.decision = Decision(
                    status=DecisionStatus.MANUAL_REVIEW,
                    approved_amount=final_amount,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary="Fraud signals require manual review",
                    user_message=user_msg,
                    notes=state.fraud_signals,
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    requires_manual_review=True,
                    degraded=state.degraded,
                    failed_components=state.failed_components,
                )
            elif _needs_clarification(state, final_amount):
                file_id = state.extracted[0].file_id if state.extracted else "unknown"
                issues = [
                    issue
                    for d in state.extracted
                    for issue in d.validation_issues
                ]
                user_msg = (
                    "We've processed your claim but a few extracted fields need "
                    f"clarification: {'; '.join(issues[:2])}. Please confirm or "
                    "re-upload a clearer document so we can finalise the claim."
                )
                state.decision = Decision(
                    status=DecisionStatus.NEEDS_CLARIFICATION,
                    approved_amount=0.0,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary=f"Field-level clarification needed on {file_id}",
                    user_message=user_msg,
                    notes=issues,
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    requires_manual_review=True,
                    degraded=state.degraded,
                    failed_components=state.failed_components,
                )
            elif state.degraded and final_amount <= 0:
                user_msg = self._manual_review_message(state)
                state.decision = Decision(
                    status=DecisionStatus.MANUAL_REVIEW,
                    approved_amount=0.0,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary="Component failure prevented full processing",
                    user_message=user_msg,
                    notes=[f"Failed components: {state.failed_components}"],
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    requires_manual_review=True,
                    degraded=True,
                    failed_components=state.failed_components,
                )
            elif had_excluded_lines and final_amount > 0:
                user_msg = self._partial_message(state, breakdown)
                state.decision = Decision(
                    status=DecisionStatus.PARTIAL,
                    approved_amount=final_amount,
                    submitted_amount=state.input.claimed_amount,
                    rejection_reasons=[RejectionReason.LINE_ITEM_EXCLUDED],
                    confidence=round(confidence, 3),
                    summary=f"Partial approval: ₹{final_amount:,.2f} of ₹{state.input.claimed_amount:,.2f}",
                    user_message=user_msg,
                    notes=[
                        f"{ld.description}: {ld.status.value if hasattr(ld.status, 'value') else ld.status}"
                        for ld in state.line_decisions
                    ],
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    degraded=state.degraded,
                )
            elif final_amount > 0:
                user_msg = self._approved_message(state, breakdown)
                notes = []
                if state.degraded:
                    notes.append(
                        "Manual review recommended due to incomplete processing "
                        f"(failed components: {state.failed_components})"
                    )
                state.decision = Decision(
                    status=DecisionStatus.APPROVED,
                    approved_amount=final_amount,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary=f"Approved ₹{final_amount:,.2f}",
                    user_message=user_msg,
                    notes=notes,
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    requires_manual_review=state.degraded,
                    degraded=state.degraded,
                    failed_components=state.failed_components,
                )
            else:
                state.decision = Decision(
                    status=DecisionStatus.REJECTED,
                    approved_amount=0.0,
                    submitted_amount=state.input.claimed_amount,
                    confidence=round(confidence, 3),
                    summary="Final approved amount is zero",
                    user_message=(
                        "Your claim has been rejected because no covered amount remained "
                        "after applying policy rules. Please contact support if you believe "
                        "this is in error."
                    ),
                    breakdown=breakdown,
                    line_items=state.line_decisions,
                    degraded=state.degraded,
                )

            state.decision.confidence_breakdown = confidence_breakdown
            state.decision.explanation_tree = build_explanation_tree(state, state.decision)
            state.decision.cost = state.cost

            event = _event_for_decision(state)
            if event is not None:
                state.record_event(event)

            rec.record(
                self.name,
                status=TraceStatus.OK,
                summary=f"{state.decision.status.value}: {state.decision.summary}",
                evidence={
                    "status": state.decision.status.value,
                    "approved_amount": state.decision.approved_amount,
                    "rejection_reasons": [r.value for r in state.decision.rejection_reasons],
                    "confidence": state.decision.confidence,
                },
                latency_ms=ctx["latency_ms"],
            )
        return state

    @staticmethod
    def _to_rejection_code(code: str) -> RejectionReason:
        try:
            return RejectionReason(code)
        except ValueError:
            return RejectionReason.CATEGORY_NOT_COVERED

    def _user_message_for_rejection(
        self, state: ClaimState, finding: PolicyFinding, breakdown: dict
    ) -> str:
        code = finding.code
        if code == RejectionReason.WAITING_PERIOD.value:
            ev = finding.evidence
            return (
                f"Your claim has been rejected because the treatment date "
                f"({state.input.treatment_date}) is within the "
                f"{ev.get('days_required')}-day waiting period"
                + (
                    f" for {ev.get('matched_condition')}"
                    if ev.get("matched_condition")
                    else ""
                )
                + f". You will be eligible for this type of claim from "
                f"{ev.get('eligibility_date')}. "
                f"Please resubmit on or after that date."
            )
        if code == RejectionReason.EXCLUDED_CONDITION.value:
            ev = finding.evidence
            return (
                f"Your claim has been rejected because the diagnosis/treatment "
                f"('{ev.get('diagnosis') or ev.get('treatment')}') is excluded under "
                f"this policy ('{ev.get('matched_exclusion')}'). "
                f"Excluded conditions are not covered regardless of amount."
            )
        if code == RejectionReason.PRE_AUTH_MISSING.value:
            ev = finding.evidence
            return (
                f"Your claim has been rejected because pre-authorization was required "
                f"for {ev.get('test_name')} above ₹{ev.get('threshold'):,.0f} but was "
                f"not obtained. {ev.get('next_steps', '')}"
            )
        if code == RejectionReason.PER_CLAIM_EXCEEDED.value:
            return (
                f"Your claim has been rejected because the claimed amount "
                f"₹{breakdown.get('claimed_amount', 0):,.0f} exceeds the per-claim limit "
                f"of ₹{breakdown.get('per_claim_limit', 0):,.0f} under this policy. "
                f"Please split the claim or contact your HR team."
            )
        if code == RejectionReason.PRESCRIPTION_MISSING.value:
            return (
                "Your claim has been rejected because a prescription is required for "
                f"{state.input.claim_category.value} claims under this policy. Please "
                "resubmit with the prescribing doctor's prescription attached."
            )
        return f"Your claim has been rejected: {finding.message}"

    def _manual_review_message(self, state: ClaimState) -> str:
        if state.fraud_signals:
            return (
                "Your claim has been routed to a human reviewer because we detected "
                f"unusual patterns: {'; '.join(state.fraud_signals)}. "
                f"You'll hear back within 2 business days."
            )
        return (
            "Your claim has been routed to manual review because one of our automated "
            f"checks could not complete (failed: {', '.join(state.failed_components)}). "
            f"A human reviewer will process this within 2 business days. "
            f"No action needed from your side."
        )

    def _partial_message(self, state: ClaimState, breakdown: dict) -> str:
        rejected = [
            ld for ld in state.line_decisions if ld.status == DecisionStatus.REJECTED
        ]
        approved = [
            ld for ld in state.line_decisions if ld.status == DecisionStatus.APPROVED
        ]
        rej_lines = "; ".join(
            f"{ld.description} (₹{ld.submitted_amount:,.0f} — {ld.reason})" for ld in rejected
        )
        apr_lines = "; ".join(
            f"{ld.description} (₹{ld.submitted_amount:,.0f})" for ld in approved
        )
        return (
            f"Partial approval: ₹{breakdown.get('final_approved_amount', 0):,.2f} approved "
            f"of ₹{state.input.claimed_amount:,.2f} claimed. "
            f"Approved items: {apr_lines}. Rejected items: {rej_lines}."
        )

    def _approved_message(self, state: ClaimState, breakdown: dict) -> str:
        parts = [
            f"Approved: ₹{breakdown.get('final_approved_amount', 0):,.2f}",
            f"of ₹{breakdown.get('claimed_amount', 0):,.0f} claimed.",
        ]
        if breakdown.get("network_discount_amount", 0) > 0:
            parts.append(
                f"Network discount applied: ₹{breakdown['network_discount_amount']:,.0f} "
                f"({breakdown['network_discount_percent']}%)."
            )
        if breakdown.get("copay_amount", 0) > 0:
            parts.append(
                f"Co-pay deducted: ₹{breakdown['copay_amount']:,.0f} "
                f"({breakdown['copay_percent']}%)."
            )
        if state.degraded:
            parts.append(
                "Note: a non-critical component did not complete; manual review "
                "recommended for full audit."
            )
        return " ".join(parts)


def _coverage_finding(state: ClaimState) -> PolicyFinding:
    return next(f for f in state.findings if f.code == "COVERAGE_CHECK" and not f.passed)


def _needs_clarification(state: ClaimState, final_amount: float) -> bool:
    """Return True when extraction succeeded but a field needs follow-up.

    Triggers:
    - any extracted document has 2+ validation_issues OR very-low confidence,
      AND no other rejection/contradiction decided the case already.

    Default behaviour for the 12 fixture cases: false (mock confidences are
    high and validation issues stay below the threshold).
    """
    if not state.extracted:
        return False
    severe = any(
        len(d.validation_issues) >= 2 or d.extraction_confidence < 0.5
        for d in state.extracted
    )
    return severe and final_amount <= 0


_MANUAL_REVIEW_STATUSES: set[DecisionStatus] = {
    DecisionStatus.MANUAL_REVIEW,
    DecisionStatus.FRAUD_INVESTIGATION,
    DecisionStatus.ESCALATED_MEDICAL_REVIEW,
    DecisionStatus.NEEDS_CLARIFICATION,
}


def _event_for_decision(state: ClaimState) -> DomainEvent | None:
    """Map a finalised `Decision` onto the appropriate domain event.

    Returns ``None`` only if the synthesizer somehow ran without setting
    a decision; in practice that branch is unreachable here.
    """
    decision = state.decision
    if decision is None:
        return None
    claim_id = state.claim_id
    status = decision.status

    if status == DecisionStatus.APPROVED:
        return ClaimApproved(
            claim_id=claim_id,
            member_id=state.input.member_id,
            approved_amount=decision.approved_amount,
            confidence=decision.confidence,
        )
    if status == DecisionStatus.PARTIAL:
        rejected = tuple(
            ld.description
            for ld in state.line_decisions
            if ld.approved_amount == 0
        )
        return ClaimPartiallyApproved(
            claim_id=claim_id,
            member_id=state.input.member_id,
            approved_amount=decision.approved_amount,
            rejected_line_items=rejected,
        )
    if status == DecisionStatus.REJECTED:
        return ClaimRejected(
            claim_id=claim_id,
            rejection_reasons=tuple(r.value for r in decision.rejection_reasons),
            summary=decision.summary or "",
        )
    if status in _MANUAL_REVIEW_STATUSES:
        return ManualReviewRequired(
            claim_id=claim_id,
            reason=status.value,
            notes=tuple(decision.notes or ()),
        )
    return None
