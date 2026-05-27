"""Unit tests for the cross-document contradiction agent."""

from __future__ import annotations

from datetime import date

import pytest

from app.agents.contradiction_detection import ContradictionDetectionAgent
from app.models.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentType,
    ExtractedDocument,
    LineItem,
)


def _claim_state(extracted: list[ExtractedDocument]) -> ClaimState:
    inp = ClaimInput(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=2000,
        documents=[
            DocumentInput(file_id=d.file_id, actual_type=d.document_type)
            for d in extracted
        ],
    )
    state = ClaimState(claim_id="TEST", input=inp)
    state.extracted = extracted
    return state


@pytest.mark.asyncio
async def test_no_contradictions_when_documents_agree():
    extracted = [
        ExtractedDocument(
            file_id="F1",
            document_type=DocumentType.PRESCRIPTION,
            patient_name="Vikram Joshi",
            hospital_name="Apollo Hospitals",
            document_date="2024-11-01",
            diagnosis="Fever",
            medicines=["Paracetamol"],
        ),
        ExtractedDocument(
            file_id="F2",
            document_type=DocumentType.HOSPITAL_BILL,
            patient_name="Vikram Joshi",
            hospital_name="Apollo Hospitals",
            document_date="2024-11-01",
            total_amount=2000.0,
            line_items=[LineItem(description="Consultation", amount=2000.0)],
        ),
    ]
    state = _claim_state(extracted)
    state = await ContradictionDetectionAgent().run(state)
    assert state.contradictions == []


@pytest.mark.asyncio
async def test_amount_reconciliation_flags_mismatch():
    extracted = [
        ExtractedDocument(
            file_id="F1",
            document_type=DocumentType.HOSPITAL_BILL,
            patient_name="Vikram Joshi",
            line_items=[LineItem(description="A", amount=500.0)],
            total_amount=2000.0,
        )
    ]
    state = _claim_state(extracted)
    state = await ContradictionDetectionAgent().run(state)
    kinds = [c.kind for c in state.contradictions]
    assert "AMOUNT_RECONCILIATION_FAILED" in kinds


@pytest.mark.asyncio
async def test_hospital_name_inconsistency():
    extracted = [
        ExtractedDocument(
            file_id="F1",
            document_type=DocumentType.PRESCRIPTION,
            patient_name="Vikram Joshi",
            hospital_name="Apollo Hospitals",
        ),
        ExtractedDocument(
            file_id="F2",
            document_type=DocumentType.HOSPITAL_BILL,
            patient_name="Vikram Joshi",
            hospital_name="Manipal Hospital",
        ),
    ]
    state = _claim_state(extracted)
    state = await ContradictionDetectionAgent().run(state)
    assert any(c.kind == "HOSPITAL_NAME_INCONSISTENT" for c in state.contradictions)
