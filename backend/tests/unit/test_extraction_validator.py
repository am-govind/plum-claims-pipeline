"""Unit tests for the post-extraction validator."""

from __future__ import annotations

from datetime import date, timedelta

from app.domain.claim import DocumentType, ExtractedDocument, LineItem
from app.domain.services.extraction_validator import validate_extraction


def _doc(**kwargs):
    base = dict(
        file_id="F1",
        document_type=DocumentType.HOSPITAL_BILL,
        patient_name="Vikram Joshi",
        document_date="2024-11-01",
        line_items=[LineItem(description="A", amount=1000.0)],
        total_amount=1000.0,
    )
    base.update(kwargs)
    return ExtractedDocument(**base)


def test_clean_doc_has_no_issues():
    doc = _doc()
    issues = validate_extraction(doc)
    assert issues == []
    assert doc.extraction_confidence == 1.0


def test_line_item_total_mismatch_flagged():
    doc = _doc(
        line_items=[LineItem(description="A", amount=500.0)],
        total_amount=2000.0,
    )
    issues = validate_extraction(doc)
    assert any("line item sum" in i for i in issues)
    assert doc.extraction_confidence < 1.0


def test_future_date_flagged():
    future = (date.today() + timedelta(days=30)).isoformat()
    doc = _doc(document_date=future)
    issues = validate_extraction(doc)
    assert any("future" in i for i in issues)


def test_doctor_registration_pattern_unrecognized():
    doc = _doc(
        document_type=DocumentType.PRESCRIPTION, doctor_registration="weird-format"
    )
    issues = validate_extraction(doc)
    assert any("doctor_registration" in i for i in issues)


def test_doctor_registration_valid_pattern_accepted():
    doc = _doc(
        document_type=DocumentType.PRESCRIPTION, doctor_registration="KA/12345/2015"
    )
    issues = validate_extraction(doc)
    assert not any("doctor_registration" in i for i in issues)


def test_negative_amount_flagged():
    doc = _doc(total_amount=-100.0, line_items=[])
    issues = validate_extraction(doc)
    assert any("negative" in i for i in issues)


def test_missing_patient_name_flagged_on_prescription():
    doc = _doc(document_type=DocumentType.PRESCRIPTION, patient_name=None)
    issues = validate_extraction(doc)
    assert any("patient_name" in i for i in issues)
