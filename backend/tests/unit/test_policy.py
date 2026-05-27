"""Unit tests for the pure policy rule functions.

These tests only exercise app.policy.* — no agents, no LLM, no graph —
so they're the fastest sanity check that the rules engine is correct.
"""

from __future__ import annotations

from datetime import date

from app.domain.claim import ClaimCategory, ExtractedDocument, LineItem
from app.domain.policy.coverage import apply_financial_calculation, line_item_excluded_reason
from app.domain.policy.exclusions import diagnosis_excluded_reason
from app.domain.policy.pre_auth import pre_auth_violation
from app.domain.policy.terms import is_network_hospital, load_policy
from app.domain.policy.waiting_periods import waiting_period_violation


def test_load_policy_smoke():
    p = load_policy()
    assert p.policy_id == "PLUM_GHI_2024"
    assert p.coverage["per_claim_limit"] == 5000


def test_network_hospital_match():
    assert is_network_hospital("Apollo Hospitals")
    assert is_network_hospital("apollo hospital, bengaluru")
    assert not is_network_hospital("City Clinic")
    assert not is_network_hospital(None)


def test_diagnosis_exclusion_obesity():
    p = load_policy()
    excl = diagnosis_excluded_reason(
        p, "Morbid Obesity — BMI 37", "Bariatric Consultation"
    )
    assert excl is not None
    assert "obesity" in excl.lower() or "bariatric" in excl.lower()


def test_diagnosis_exclusion_clean():
    p = load_policy()
    assert diagnosis_excluded_reason(p, "Viral Fever", None) is None


def test_waiting_period_diabetes():
    p = load_policy()
    join = date(2024, 9, 1)
    treatment = date(2024, 10, 15)
    v = waiting_period_violation(p, join, treatment, "Type 2 Diabetes Mellitus")
    assert v is not None
    assert v.kind == "SPECIFIC_CONDITION"
    assert v.matched_condition == "diabetes"
    assert v.eligibility_date == date(2024, 11, 30)


def test_waiting_period_initial_only():
    p = load_policy()
    join = date(2024, 11, 1)
    treatment = date(2024, 11, 10)
    v = waiting_period_violation(p, join, treatment, "Viral Fever")
    assert v is not None
    assert v.kind == "INITIAL"


def test_waiting_period_clear():
    p = load_policy()
    join = date(2024, 4, 1)
    treatment = date(2024, 11, 1)
    assert waiting_period_violation(p, join, treatment, "Viral Fever") is None


def test_pre_auth_mri_above_threshold():
    p = load_policy()
    docs = [
        ExtractedDocument(
            file_id="X",
            document_type="LAB_REPORT",  # type: ignore[arg-type]
            tests_ordered=["MRI Lumbar Spine"],
        )
    ]
    v = pre_auth_violation(p, ClaimCategory.DIAGNOSTIC, 15000, docs, pre_auth_obtained=False)
    assert v is not None
    assert "MRI" in v.test_name


def test_pre_auth_under_threshold_passes():
    p = load_policy()
    docs = [
        ExtractedDocument(
            file_id="X",
            document_type="LAB_REPORT",  # type: ignore[arg-type]
            tests_ordered=["CBC"],
        )
    ]
    assert pre_auth_violation(p, ClaimCategory.DIAGNOSTIC, 800, docs) is None


def test_line_item_exclusion_dental():
    p = load_policy()
    assert line_item_excluded_reason(p, ClaimCategory.DENTAL, "Teeth Whitening") is not None
    assert line_item_excluded_reason(p, ClaimCategory.DENTAL, "Root Canal Treatment") is None


def test_financial_calculation_tc010_network_then_copay():
    """TC010: ₹4500 at Apollo (network) -> 20% off = 3600 -> 10% co-pay = 3240."""
    p = load_policy()
    extracted = [
        ExtractedDocument(
            file_id="F",
            document_type="HOSPITAL_BILL",  # type: ignore[arg-type]
            line_items=[
                LineItem(description="Consultation Fee", amount=1500),
                LineItem(description="Medicines", amount=3000),
            ],
            total_amount=4500,
        )
    ]
    out = apply_financial_calculation(
        policy=p,
        category=ClaimCategory.CONSULTATION,
        claimed_amount=4500,
        extracted=extracted,
        hospital_name="Apollo Hospitals",
        ytd_claims_amount=8000,
    )
    assert out["breakdown"]["network_discount_amount"] == 900.0
    assert out["breakdown"]["after_discount"] == 3600.0
    assert out["breakdown"]["copay_amount"] == 360.0
    assert out["breakdown"]["after_copay"] == 3240.0
    assert out["final_amount"] == 3240.0


def test_financial_calculation_tc004_consultation_copay_only():
    """TC004: ₹1500 consultation, no network, 10% co-pay -> 1350."""
    p = load_policy()
    extracted = [
        ExtractedDocument(
            file_id="F",
            document_type="HOSPITAL_BILL",  # type: ignore[arg-type]
            line_items=[
                LineItem(description="Consultation Fee", amount=1000),
                LineItem(description="CBC Test", amount=300),
                LineItem(description="Dengue NS1 Test", amount=200),
            ],
            total_amount=1500,
        )
    ]
    out = apply_financial_calculation(
        policy=p,
        category=ClaimCategory.CONSULTATION,
        claimed_amount=1500,
        extracted=extracted,
        hospital_name="City Clinic, Bengaluru",
        ytd_claims_amount=5000,
    )
    assert out["final_amount"] == 1350.0


def test_financial_calculation_tc006_dental_partial():
    p = load_policy()
    extracted = [
        ExtractedDocument(
            file_id="F",
            document_type="HOSPITAL_BILL",  # type: ignore[arg-type]
            line_items=[
                LineItem(description="Root Canal Treatment", amount=8000),
                LineItem(description="Teeth Whitening", amount=4000),
            ],
            total_amount=12000,
        )
    ]
    out = apply_financial_calculation(
        policy=p,
        category=ClaimCategory.DENTAL,
        claimed_amount=12000,
        extracted=extracted,
        hospital_name=None,
        ytd_claims_amount=0,
    )
    assert out["had_excluded_line_items"] is True
    assert out["final_amount"] == 8000.0
    rejected = [ld for ld in out["line_decisions"] if ld.approved_amount == 0]
    approved = [ld for ld in out["line_decisions"] if ld.approved_amount > 0]
    assert any("Whitening" in ld.description for ld in rejected)
    assert any("Root Canal" in ld.description for ld in approved)


def test_financial_calculation_tc008_per_claim_cap():
    p = load_policy()
    out = apply_financial_calculation(
        policy=p,
        category=ClaimCategory.CONSULTATION,
        claimed_amount=7500,
        extracted=[],
        hospital_name=None,
        ytd_claims_amount=10000,
    )
    assert "PER_CLAIM" in out["breakdown"]["caps_hit"]
