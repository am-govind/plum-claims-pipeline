"""Document Verification Agent unit tests (TC001, TC002, TC003)."""

from __future__ import annotations

from datetime import date

import pytest

from app.application.agents.document_verification import DocumentVerificationAgent
from app.config import Settings
from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentQuality,
    DocumentType,
)
from app.infrastructure.policy.json_policy_repository import JsonPolicyRepository


@pytest.fixture(scope="module")
def agent() -> DocumentVerificationAgent:
    policy = JsonPolicyRepository(Settings().policy_terms_path).get_terms()
    return DocumentVerificationAgent(policy=policy)


def _state(documents: list[DocumentInput]) -> ClaimState:
    return ClaimState(
        claim_id="T",
        input=ClaimInput(
            member_id="EMP001",
            policy_id="PLUM_GHI_2024",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date=date(2024, 11, 1),
            claimed_amount=1500,
            documents=documents,
        ),
    )


@pytest.mark.asyncio
async def test_tc001_wrong_document_type(agent: DocumentVerificationAgent):
    state = _state(
        [
            DocumentInput(file_id="F001", actual_type=DocumentType.PRESCRIPTION),
            DocumentInput(file_id="F002", actual_type=DocumentType.PRESCRIPTION),
        ]
    )
    state = await agent.run(state)
    assert state.early_stop
    assert state.early_stop_reason == "DOCUMENT_TYPE_MISMATCH"
    msg = state.early_stop_user_message or ""
    assert "PRESCRIPTION" in msg
    assert "HOSPITAL_BILL" in msg
    assert "consultation" in msg.lower()


@pytest.mark.asyncio
async def test_tc002_unreadable_document(agent: DocumentVerificationAgent):
    state = ClaimState(
        claim_id="T",
        input=ClaimInput(
            member_id="EMP004",
            policy_id="PLUM_GHI_2024",
            claim_category=ClaimCategory.PHARMACY,
            treatment_date=date(2024, 10, 25),
            claimed_amount=800,
            documents=[
                DocumentInput(file_id="F003", actual_type=DocumentType.PRESCRIPTION),
                DocumentInput(
                    file_id="F004",
                    actual_type=DocumentType.PHARMACY_BILL,
                    quality=DocumentQuality.UNREADABLE,
                ),
            ],
        ),
    )
    state = await agent.run(state)
    assert state.early_stop
    assert state.early_stop_reason == "DOCUMENT_UNREADABLE"
    assert "F004" in (state.early_stop_user_message or "")
    assert "re-upload" in (state.early_stop_user_message or "").lower()


@pytest.mark.asyncio
async def test_tc003_patient_mismatch(agent: DocumentVerificationAgent):
    state = _state(
        [
            DocumentInput(
                file_id="F005",
                actual_type=DocumentType.PRESCRIPTION,
                patient_name_on_doc="Rajesh Kumar",
            ),
            DocumentInput(
                file_id="F006",
                actual_type=DocumentType.HOSPITAL_BILL,
                patient_name_on_doc="Arjun Mehta",
            ),
        ]
    )
    state = await agent.run(state)
    assert state.early_stop
    assert state.early_stop_reason == "PATIENT_MISMATCH"
    assert "Rajesh Kumar" in (state.early_stop_user_message or "")
    assert "Arjun Mehta" in (state.early_stop_user_message or "")


@pytest.mark.asyncio
async def test_clean_documents_pass(agent: DocumentVerificationAgent):
    state = _state(
        [
            DocumentInput(
                file_id="F007",
                actual_type=DocumentType.PRESCRIPTION,
                patient_name_on_doc="Rajesh Kumar",
            ),
            DocumentInput(
                file_id="F008",
                actual_type=DocumentType.HOSPITAL_BILL,
                patient_name_on_doc="Rajesh Kumar",
            ),
        ]
    )
    state = await agent.run(state)
    assert not state.early_stop
