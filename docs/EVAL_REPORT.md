# Eval Report

_Generated: 2026-05-28T05:03:31.829586+00:00_

**Summary**: 12/12 cases passed.

| Case | Name | Expected | Got | Approved | Confidence | Latency | Tokens | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC001 | Wrong Document Uploaded | EARLY_STOP | EARLY_STOP | — | 0.5 | 0 ms | 0 | PASS |
| TC002 | Unreadable Document | EARLY_STOP | EARLY_STOP | — | 0.5 | 0 ms | 0 | PASS |
| TC003 | Documents Belong to Different Patients | EARLY_STOP | EARLY_STOP | — | 0.5 | 0 ms | 0 | PASS |
| TC004 | Clean Consultation — Full Approval | APPROVED | APPROVED | 1350.0 | 0.985 | 20 ms | 1386 | PASS |
| TC005 | Waiting Period — Diabetes | REJECTED | REJECTED | 0.0 | 0.977 | 0 ms | 1225 | PASS |
| TC006 | Dental Partial Approval — Cosmetic Exclusion | PARTIAL | PARTIAL | 8000.0 | 0.985 | 0 ms | 645 | PASS |
| TC007 | MRI Without Pre-Authorization | REJECTED | REJECTED | 0.0 | 0.908 | 0 ms | 3095 | PASS |
| TC008 | Per-Claim Limit Exceeded | REJECTED | REJECTED | 0.0 | 0.962 | 0 ms | 1900 | PASS |
| TC009 | Fraud Signal — Multiple Same-Day Claims | MANUAL_REVIEW | MANUAL_REVIEW | 4320.0 | 0.932 | 0 ms | 1705 | PASS |
| TC010 | Network Hospital — Discount Applied | APPROVED | APPROVED | 3240.0 | 0.985 | 0 ms | 1362 | PASS |
| TC011 | Component Failure — Graceful Degradation | APPROVED | APPROVED | 4000.0 | 0.612 | 0 ms | 2003 | PASS |
| TC012 | Excluded Treatment | REJECTED | REJECTED | 0.0 | 0.955 | 0 ms | 1917 | PASS |

## Aggregate metrics

- **Latency**: P50 = 0 ms · P95 = 0 ms · avg = 1 ms · median = 0 ms
- **Tokens**: 11,203 in + 4,035 out = 15,238 total · est. cost ≈ $0.000000
- **Extraction validation issues** (hallucination proxy): 6 across 5 cases
- **Cross-document contradictions detected**: 1
- **Deliberation cycles triggered**: 5

### Extraction confidence histogram

| Bucket | Count |
| --- | --- |
| [0.0, 0.1) |  0 |
| [0.1, 0.2) |  0 |
| [0.2, 0.3) |  0 |
| [0.3, 0.4) |  0 |
| [0.4, 0.5) |  0 |
| [0.5, 0.6) |  0 |
| [0.6, 0.7) |  0 |
| [0.7, 0.8) |  0 |
| [0.8, 0.9) | ██████ 6 |
| [0.9, 1.0) | ████████████ 12 |

### Rule coverage matrix (rules that fired in each case)

| Rule | Fired in | Count |
| --- | --- | --- |
| `EXCLUDED_CONDITION` | TC012 | 1 |
| `PRE_AUTH_DIAGNOSTIC_HIGH_VALUE` | TC007 | 1 |
| `WAITING_PERIOD_DIABETES` | TC005 | 1 |
| `WAITING_PERIOD_OBESITY` | TC012 | 1 |

### Decision status distribution

- APPROVED: 3
- EARLY_STOP: 3
- MANUAL_REVIEW: 1
- PARTIAL: 1
- REJECTED: 4

## TC001 — Wrong Document Uploaded

**Result**: PASS

**Expected**:
```json
{
  "decision": null,
  "system_must": [
    "Stop before making any claim decision",
    "Tell the member specifically what document type was uploaded and what is needed instead",
    "Not return a generic error \u2014 the message must name the uploaded document type and the required document type"
  ]
}
```

**Decision (actual)**:
_(no decision; pipeline halted early)_
**Early stop**: `DOCUMENT_TYPE_MISMATCH` — _Your consultation claim cannot be processed yet. You uploaded: PRESCRIPTION, PRESCRIPTION. For a consultation claim we need: PRESCRIPTION, HOSPITAL_BILL. Please upload the missing document(s): HOSPITAL_BILL._

**system_must checks**:
- [x] Stop before making any claim decision
- [x] Tell the member specifically what document type was uploaded and what is needed instead
- [x] Not return a generic error — the message must name the uploaded document type and the required document type

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Rajesh Kumar
  ```json
{
  "member_id": "EMP001",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 1500.0,
  "treatment_date": "2024-11-01",
  "found_member": true,
  "document_count": 2,
  "member_name": "Rajesh Kumar"
}
  ```
- **document_verification** — `EARLY_STOP` (0ms): DOCUMENT_TYPE_MISMATCH (type_check): Wrong documents for CONSULTATION: uploaded ['PRESCRIPTION', 'PRESCRIPTION'], required ['PRESCRIPTION', 'HOSPITAL_BILL'], missing ['HOSPITAL_BILL']
  - error: `DOCUMENT_TYPE_MISMATCH`
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "PRESCRIPTION"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "missing_types": [
    "HOSPITAL_BILL"
  ],
  "category": "CONSULTATION",
  "check": "type_check"
}
  ```

---

## TC002 — Unreadable Document

**Result**: PASS

**Expected**:
```json
{
  "decision": null,
  "system_must": [
    "Identify that the pharmacy bill cannot be read",
    "Ask the member to re-upload that specific document",
    "Not reject the claim outright"
  ]
}
```

**Decision (actual)**:
_(no decision; pipeline halted early)_
**Early stop**: `DOCUMENT_UNREADABLE` — _We couldn't read your pharmacy bill ('blurry_bill.jpg'). The image is too blurry or low-contrast for our system to process. Please re-upload a clearer photo or scan of this specific document. All your other documents are fine — only re-upload file F004._

**system_must checks**:
- [x] Identify that the pharmacy bill cannot be read
- [x] Ask the member to re-upload that specific document
- [x] Not reject the claim outright

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Sneha Reddy
  ```json
{
  "member_id": "EMP004",
  "policy_id": "PLUM_GHI_2024",
  "category": "PHARMACY",
  "claimed_amount": 800.0,
  "treatment_date": "2024-10-25",
  "found_member": true,
  "document_count": 2,
  "member_name": "Sneha Reddy"
}
  ```
- **document_verification** — `EARLY_STOP` (0ms): DOCUMENT_UNREADABLE (quality_check): Document F004 (PHARMACY_BILL) is unreadable
  - error: `DOCUMENT_UNREADABLE`
  ```json
{
  "file_id": "F004",
  "file_name": "blurry_bill.jpg",
  "document_type": "PHARMACY_BILL",
  "check": "quality_check"
}
  ```

---

## TC003 — Documents Belong to Different Patients

**Result**: PASS

**Expected**:
```json
{
  "decision": null,
  "system_must": [
    "Detect that the documents belong to different people",
    "Surface this to the member with the specific names found on each document",
    "Not proceed to a claim decision"
  ]
}
```

**Decision (actual)**:
_(no decision; pipeline halted early)_
**Early stop**: `PATIENT_MISMATCH` — _The documents you uploaded belong to different patients (Arjun Mehta, Rajesh Kumar). We found: F005: Rajesh Kumar, F006: Arjun Mehta. All documents in a single claim must be for the same patient. Please re-check and resubmit with documents that all belong to the same person._

**system_must checks**:
- [x] Detect that the documents belong to different people
- [x] Surface this to the member with the specific names found on each document
- [x] Not proceed to a claim decision

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Rajesh Kumar
  ```json
{
  "member_id": "EMP001",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 1500.0,
  "treatment_date": "2024-11-01",
  "found_member": true,
  "document_count": 2,
  "member_name": "Rajesh Kumar"
}
  ```
- **document_verification** — `EARLY_STOP` (0ms): PATIENT_MISMATCH (patient_match): Documents belong to different patients: ['Arjun Mehta', 'Rajesh Kumar']
  - error: `PATIENT_MISMATCH`
  ```json
{
  "names_by_file": {
    "F005": "Rajesh Kumar",
    "F006": "Arjun Mehta"
  },
  "unique_names": [
    "Arjun Mehta",
    "Rajesh Kumar"
  ],
  "check": "patient_match"
}
  ```

---

## TC004 — Clean Consultation — Full Approval

**Result**: PASS

**Expected**:
```json
{
  "decision": "APPROVED",
  "approved_amount": 1350,
  "notes": "10% co-pay applied on consultation category (\u20b9150 deducted)",
  "confidence_score": "above 0.85"
}
```

**Decision (actual)**:
- Status: **APPROVED**
- Approved: ₹1350.00 of ₹1500.00
- Confidence: 0.985
- Rejection reasons: —
- Summary: Approved ₹1,350.00
- User message: Approved: ₹1,350.00 of ₹1,500 claimed. Co-pay deducted: ₹150 (10%).
- Degraded: False, failed components: —

**system_must checks**:

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Rajesh Kumar
  ```json
{
  "member_id": "EMP001",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 1500.0,
  "treatment_date": "2024-11-01",
  "found_member": true,
  "document_count": 2,
  "member_name": "Rajesh Kumar"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for CONSULTATION (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": [
    "Rajesh Kumar",
    "Rajesh Kumar"
  ]
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F007",
      "type": "PRESCRIPTION",
      "patient": "Rajesh Kumar",
      "diagnosis": "Viral Fever",
      "total": null,
      "line_items": 0,
      "confidence": 0.95
    },
    {
      "file_id": "F008",
      "type": "HOSPITAL_BILL",
      "patient": "Rajesh Kumar",
      "diagnosis": null,
      "total": 1500.0,
      "line_items": 3,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [
    "Rajesh Kumar"
  ],
  "hospital_names": [
    "City Clinic, Bengaluru"
  ]
}
  ```
- **policy_adjudication** — `OK` (0ms): 13 policy rule(s) evaluated; 0 failed
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹1,500 -> discount 0 -> co-pay 150 -> final ₹1,350
  ```json
{
  "claimed_amount": 1500.0,
  "line_items_total_submitted": 1500.0,
  "line_items_accepted_total": 1500.0,
  "line_items_rejected_total": 0.0,
  "gross_after_line_items": 1500.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 1500.0,
  "copay_percent": 10,
  "copay_amount": 150.0,
  "after_copay": 1350.0,
  "sub_limit": 2000,
  "sub_limit_warning": false,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 5000.0,
  "per_claim_exceeded": false,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 5000.0,
  "ytd_remaining": 45000.0,
  "after_ytd_cap": 1350.0,
  "final_approved_amount": 1350.0,
  "caps_hit": []
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): APPROVED: Approved ₹1,350.00
  ```json
{
  "status": "APPROVED",
  "approved_amount": 1350.0,
  "rejection_reasons": [],
  "confidence": 0.985
}
  ```

---

## TC005 — Waiting Period — Diabetes

**Result**: PASS

**Expected**:
```json
{
  "decision": "REJECTED",
  "rejection_reasons": [
    "WAITING_PERIOD"
  ],
  "system_must": [
    "State the date from which the member will be eligible for diabetes-related claims"
  ]
}
```

**Decision (actual)**:
- Status: **REJECTED**
- Approved: ₹0.00 of ₹3000.00
- Confidence: 0.977
- Rejection reasons: ['WAITING_PERIOD']
- Summary: Treatment date 2024-10-15 is within the 90-day waiting period for diabetes. Member becomes eligible from 2024-11-30.
- User message: Your claim has been rejected because the treatment date (2024-10-15) is within the 90-day waiting period for diabetes. You will be eligible for this type of claim from 2024-11-30. Please resubmit on or after that date.
- Degraded: False, failed components: —

**system_must checks**:
- [x] State the date from which the member will be eligible for diabetes-related claims

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Vikram Joshi
  ```json
{
  "member_id": "EMP005",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 3000.0,
  "treatment_date": "2024-10-15",
  "found_member": true,
  "document_count": 2,
  "member_name": "Vikram Joshi"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for CONSULTATION (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": [
    "Vikram Joshi",
    "Vikram Joshi"
  ]
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F009",
      "type": "PRESCRIPTION",
      "patient": "Vikram Joshi",
      "diagnosis": "Type 2 Diabetes Mellitus",
      "total": null,
      "line_items": 0,
      "confidence": 0.95
    },
    {
      "file_id": "F010",
      "type": "HOSPITAL_BILL",
      "patient": "Vikram Joshi",
      "diagnosis": null,
      "total": 3000.0,
      "line_items": 0,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [
    "Vikram Joshi"
  ],
  "hospital_names": []
}
  ```
- **policy_adjudication** — `WARNING` (0ms): 13 policy rule(s) evaluated; 1 failed: WAITING_PERIOD_DIABETES
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": false,
      "severity": "REJECT"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹3,000 -> discount 0 -> co-pay 300 -> final ₹2,700 (caps hit: ['SUB_LIMIT'])
  ```json
{
  "claimed_amount": 3000.0,
  "line_items_total_submitted": null,
  "line_items_accepted_total": null,
  "line_items_rejected_total": null,
  "gross_after_line_items": 3000.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 3000.0,
  "copay_percent": 10,
  "copay_amount": 300.0,
  "after_copay": 2700.0,
  "sub_limit": 2000,
  "sub_limit_warning": true,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 5000.0,
  "per_claim_exceeded": false,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 0.0,
  "ytd_remaining": 50000.0,
  "after_ytd_cap": 2700.0,
  "final_approved_amount": 2700.0,
  "caps_hit": [
    "SUB_LIMIT"
  ]
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): REJECTED: Treatment date 2024-10-15 is within the 90-day waiting period for diabetes. Member becomes eligible from 2024-11-30.
  ```json
{
  "status": "REJECTED",
  "approved_amount": 0.0,
  "rejection_reasons": [
    "WAITING_PERIOD"
  ],
  "confidence": 0.977
}
  ```

---

## TC006 — Dental Partial Approval — Cosmetic Exclusion

**Result**: PASS

**Expected**:
```json
{
  "decision": "PARTIAL",
  "approved_amount": 8000,
  "system_must": [
    "Itemize which line items were approved and which were rejected",
    "State the reason for each rejection at the line-item level"
  ]
}
```

**Decision (actual)**:
- Status: **PARTIAL**
- Approved: ₹8000.00 of ₹12000.00
- Confidence: 0.985
- Rejection reasons: ['LINE_ITEM_EXCLUDED']
- Summary: Partial approval: ₹8,000.00 of ₹12,000.00
- User message: Partial approval: ₹8,000.00 approved of ₹12,000.00 claimed. Approved items: Root Canal Treatment (₹8,000). Rejected items: Teeth Whitening (₹4,000 — Line item matches category exclusion 'teeth whitening').
- Degraded: False, failed components: —

**system_must checks**:
- [x] Itemize which line items were approved and which were rejected
- [x] State the reason for each rejection at the line-item level

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Priya Singh
  ```json
{
  "member_id": "EMP002",
  "policy_id": "PLUM_GHI_2024",
  "category": "DENTAL",
  "claimed_amount": 12000.0,
  "treatment_date": "2024-10-15",
  "found_member": true,
  "document_count": 1,
  "member_name": "Priya Singh"
}
  ```
- **document_verification** — `OK` (0ms): All 1 document(s) verified for DENTAL (required: ['HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD"
  ],
  "patient_names": [
    "Priya Singh"
  ]
}
  ```
- **extraction** — `OK` (0ms): Extracted 1 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F011",
      "type": "HOSPITAL_BILL",
      "patient": "Priya Singh",
      "diagnosis": null,
      "total": 12000.0,
      "line_items": 2,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [
    "Priya Singh"
  ],
  "hospital_names": [
    "Smile Dental Clinic"
  ]
}
  ```
- **policy_adjudication** — `OK` (0ms): 13 policy rule(s) evaluated; 0 failed
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹12,000 -> discount 0 -> co-pay 0 -> final ₹8,000
  ```json
{
  "claimed_amount": 12000.0,
  "line_items_total_submitted": 12000.0,
  "line_items_accepted_total": 8000.0,
  "line_items_rejected_total": 4000.0,
  "gross_after_line_items": 8000.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 8000.0,
  "copay_percent": 0,
  "copay_amount": 0.0,
  "after_copay": 8000.0,
  "sub_limit": 10000,
  "sub_limit_warning": false,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 10000.0,
  "per_claim_exceeded": false,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 0.0,
  "ytd_remaining": 50000.0,
  "after_ytd_cap": 8000.0,
  "final_approved_amount": 8000.0,
  "caps_hit": []
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): PARTIAL: Partial approval: ₹8,000.00 of ₹12,000.00
  ```json
{
  "status": "PARTIAL",
  "approved_amount": 8000.0,
  "rejection_reasons": [
    "LINE_ITEM_EXCLUDED"
  ],
  "confidence": 0.985
}
  ```

---

## TC007 — MRI Without Pre-Authorization

**Result**: PASS

**Expected**:
```json
{
  "decision": "REJECTED",
  "rejection_reasons": [
    "PRE_AUTH_MISSING"
  ],
  "system_must": [
    "Explain that pre-authorization was required and not obtained",
    "Tell the member what they should do to resubmit with pre-auth"
  ]
}
```

**Decision (actual)**:
- Status: **REJECTED**
- Approved: ₹0.00 of ₹15000.00
- Confidence: 0.908
- Rejection reasons: ['PRE_AUTH_MISSING', 'PER_CLAIM_EXCEEDED']
- Summary: Pre-authorization required for MRI above the threshold. Claim amount ₹15,000 requires prior approval, which was not obtained. Please obtain pre-authorization from the insurer for this test, then resubmit the claim with the pre-auth reference number.
- User message: Your claim has been rejected because pre-authorization was required for MRI above ₹10,000 but was not obtained. Please contact the insurer to obtain a pre-authorization reference number for this test, then resubmit the claim with that reference attached.
- Degraded: False, failed components: —

**system_must checks**:
- [x] Explain that pre-authorization was required and not obtained
- [x] Tell the member what they should do to resubmit with pre-auth

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Suresh Patil
  ```json
{
  "member_id": "EMP007",
  "policy_id": "PLUM_GHI_2024",
  "category": "DIAGNOSTIC",
  "claimed_amount": 15000.0,
  "treatment_date": "2024-11-02",
  "found_member": true,
  "document_count": 3,
  "member_name": "Suresh Patil"
}
  ```
- **document_verification** — `OK` (0ms): All 3 document(s) verified for DIAGNOSTIC (required: ['PRESCRIPTION', 'LAB_REPORT', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "LAB_REPORT",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "LAB_REPORT",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD",
    "GOOD"
  ],
  "patient_names": []
}
  ```
- **extraction_validation** — `WARNING` (0ms): 2 extraction validation issue(s) flagged across 2 document(s)
  ```json
{
  "issues_by_file": {
    "F012": [
      "patient_name missing on PRESCRIPTION (expected on this doc type)"
    ],
    "F013": [
      "patient_name missing on LAB_REPORT (expected on this doc type)"
    ]
  }
}
  ```
- **extraction** — `OK` (0ms): Extracted 3 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F012",
      "type": "PRESCRIPTION",
      "patient": null,
      "diagnosis": "Suspected Lumbar Disc Herniation",
      "total": null,
      "line_items": 0,
      "confidence": 0.8
    },
    {
      "file_id": "F013",
      "type": "LAB_REPORT",
      "patient": null,
      "diagnosis": null,
      "total": null,
      "line_items": 0,
      "confidence": 0.8
    },
    {
      "file_id": "F014",
      "type": "HOSPITAL_BILL",
      "patient": null,
      "diagnosis": null,
      "total": 15000.0,
      "line_items": 1,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **re_verification** — `WARNING` (0ms): Re-extracted 2 document(s) with provider=mock; no measurable improvement (provider=mock may not act on feedback, or the underlying document didn't support a better extraction)
  ```json
{
  "iteration": 1,
  "cap": 1,
  "provider": "mock",
  "targets": [
    "F012",
    "F013"
  ],
  "retried": [
    "F012",
    "F013"
  ],
  "improved": [],
  "failed": []
}
  ```
- **contradiction_detection** — `WARNING` (0ms): 1 cross-document contradiction(s) detected
  ```json
{
  "contradictions": [
    {
      "kind": "DIAGNOSIS_TREATMENT_MISMATCH",
      "description": "Diagnosis does not appear consistent with prescribed medicines/tests/line items based on standard clinical patterns"
    }
  ]
}
  ```
- **policy_adjudication** — `WARNING` (0ms): 14 policy rule(s) evaluated; 1 failed: PRE_AUTH_DIAGNOSTIC_HIGH_VALUE
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRE_AUTH_DIAGNOSTIC_HIGH_VALUE",
      "code": "PRE_AUTH_MISSING",
      "passed": false,
      "severity": "REJECT"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹15,000 -> discount 0 -> co-pay 0 -> final ₹0 (caps hit: ['PER_CLAIM'])
  ```json
{
  "claimed_amount": 15000.0,
  "line_items_total_submitted": 15000.0,
  "line_items_accepted_total": 15000.0,
  "line_items_rejected_total": 0.0,
  "gross_after_line_items": 15000.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 15000.0,
  "copay_percent": 0,
  "copay_amount": 0.0,
  "after_copay": 15000.0,
  "sub_limit": 10000,
  "sub_limit_warning": false,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 10000.0,
  "per_claim_exceeded": true,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 0.0,
  "ytd_remaining": 50000.0,
  "after_ytd_cap": 15000.0,
  "final_approved_amount": 0.0,
  "caps_hit": [
    "PER_CLAIM"
  ]
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): REJECTED: Pre-authorization required for MRI above the threshold. Claim amount ₹15,000 requires prior approval, which was not obtained. Please obtain pre-authorization from the insurer for this test, then resubmit the claim with the pre-auth reference number.
  ```json
{
  "status": "REJECTED",
  "approved_amount": 0.0,
  "rejection_reasons": [
    "PRE_AUTH_MISSING",
    "PER_CLAIM_EXCEEDED"
  ],
  "confidence": 0.908
}
  ```

---

## TC008 — Per-Claim Limit Exceeded

**Result**: PASS

**Expected**:
```json
{
  "decision": "REJECTED",
  "rejection_reasons": [
    "PER_CLAIM_EXCEEDED"
  ],
  "system_must": [
    "State the per-claim limit and the claimed amount clearly in the rejection message"
  ]
}
```

**Decision (actual)**:
- Status: **REJECTED**
- Approved: ₹0.00 of ₹7500.00
- Confidence: 0.962
- Rejection reasons: ['PER_CLAIM_EXCEEDED']
- Summary: Claimed amount ₹7,500 exceeds per-claim limit of ₹5,000
- User message: Your claim has been rejected because the claimed amount ₹7,500 exceeds the per-claim limit of ₹5,000 under this policy. Please split the claim or contact your HR team.
- Degraded: False, failed components: —

**system_must checks**:
- [x] State the per-claim limit and the claimed amount clearly in the rejection message

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Amit Verma
  ```json
{
  "member_id": "EMP003",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 7500.0,
  "treatment_date": "2024-10-20",
  "found_member": true,
  "document_count": 2,
  "member_name": "Amit Verma"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for CONSULTATION (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": []
}
  ```
- **extraction_validation** — `WARNING` (0ms): 1 extraction validation issue(s) flagged across 1 document(s)
  ```json
{
  "issues_by_file": {
    "F015": [
      "patient_name missing on PRESCRIPTION (expected on this doc type)"
    ]
  }
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F015",
      "type": "PRESCRIPTION",
      "patient": null,
      "diagnosis": "Gastroenteritis",
      "total": null,
      "line_items": 0,
      "confidence": 0.8
    },
    {
      "file_id": "F016",
      "type": "HOSPITAL_BILL",
      "patient": null,
      "diagnosis": null,
      "total": 7500.0,
      "line_items": 2,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **re_verification** — `WARNING` (0ms): Re-extracted 1 document(s) with provider=mock; no measurable improvement (provider=mock may not act on feedback, or the underlying document didn't support a better extraction)
  ```json
{
  "iteration": 1,
  "cap": 1,
  "provider": "mock",
  "targets": [
    "F015"
  ],
  "retried": [
    "F015"
  ],
  "improved": [],
  "failed": []
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [],
  "hospital_names": []
}
  ```
- **policy_adjudication** — `OK` (0ms): 13 policy rule(s) evaluated; 0 failed
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹7,500 -> discount 0 -> co-pay 750 -> final ₹0 (caps hit: ['PER_CLAIM'])
  ```json
{
  "claimed_amount": 7500.0,
  "line_items_total_submitted": 7500.0,
  "line_items_accepted_total": 7500.0,
  "line_items_rejected_total": 0.0,
  "gross_after_line_items": 7500.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 7500.0,
  "copay_percent": 10,
  "copay_amount": 750.0,
  "after_copay": 6750.0,
  "sub_limit": 2000,
  "sub_limit_warning": false,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 5000.0,
  "per_claim_exceeded": true,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 10000.0,
  "ytd_remaining": 40000.0,
  "after_ytd_cap": 6750.0,
  "final_approved_amount": 0.0,
  "caps_hit": [
    "PER_CLAIM"
  ]
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): REJECTED: Claimed amount ₹7,500 exceeds per-claim limit of ₹5,000
  ```json
{
  "status": "REJECTED",
  "approved_amount": 0.0,
  "rejection_reasons": [
    "PER_CLAIM_EXCEEDED"
  ],
  "confidence": 0.962
}
  ```

---

## TC009 — Fraud Signal — Multiple Same-Day Claims

**Result**: PASS

**Expected**:
```json
{
  "decision": "MANUAL_REVIEW",
  "system_must": [
    "Flag the unusual same-day claim pattern",
    "Route to manual review rather than auto-rejecting",
    "Include the specific signals that triggered the flag in the output"
  ]
}
```

**Decision (actual)**:
- Status: **MANUAL_REVIEW**
- Approved: ₹4320.00 of ₹4800.00
- Confidence: 0.932
- Rejection reasons: —
- Summary: Fraud signals require manual review
- User message: Your claim has been routed to a human reviewer because we detected unusual patterns: Same-day claim count 4 exceeds limit 2. You'll hear back within 2 business days.
- Degraded: False, failed components: —

**system_must checks**:
- [x] Flag the unusual same-day claim pattern
- [x] Route to manual review rather than auto-rejecting
- [x] Include the specific signals that triggered the flag in the output

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Ravi Menon
  ```json
{
  "member_id": "EMP008",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 4800.0,
  "treatment_date": "2024-10-30",
  "found_member": true,
  "document_count": 2,
  "member_name": "Ravi Menon"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for CONSULTATION (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": []
}
  ```
- **extraction_validation** — `WARNING` (0ms): 1 extraction validation issue(s) flagged across 1 document(s)
  ```json
{
  "issues_by_file": {
    "F017": [
      "patient_name missing on PRESCRIPTION (expected on this doc type)"
    ]
  }
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F017",
      "type": "PRESCRIPTION",
      "patient": null,
      "diagnosis": "Migraine",
      "total": null,
      "line_items": 0,
      "confidence": 0.8
    },
    {
      "file_id": "F018",
      "type": "HOSPITAL_BILL",
      "patient": null,
      "diagnosis": null,
      "total": 4800.0,
      "line_items": 0,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **re_verification** — `WARNING` (0ms): Re-extracted 1 document(s) with provider=mock; no measurable improvement (provider=mock may not act on feedback, or the underlying document didn't support a better extraction)
  ```json
{
  "iteration": 1,
  "cap": 1,
  "provider": "mock",
  "targets": [
    "F017"
  ],
  "retried": [
    "F017"
  ],
  "improved": [],
  "failed": []
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [],
  "hospital_names": []
}
  ```
- **policy_adjudication** — `OK` (0ms): 13 policy rule(s) evaluated; 0 failed
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹4,800 -> discount 0 -> co-pay 480 -> final ₹4,320 (caps hit: ['SUB_LIMIT'])
  ```json
{
  "claimed_amount": 4800.0,
  "line_items_total_submitted": null,
  "line_items_accepted_total": null,
  "line_items_rejected_total": null,
  "gross_after_line_items": 4800.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 4800.0,
  "copay_percent": 10,
  "copay_amount": 480.0,
  "after_copay": 4320.0,
  "sub_limit": 2000,
  "sub_limit_warning": true,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 5000.0,
  "per_claim_exceeded": false,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 0.0,
  "ytd_remaining": 50000.0,
  "after_ytd_cap": 4320.0,
  "final_approved_amount": 4320.0,
  "caps_hit": [
    "SUB_LIMIT"
  ]
}
  ```
- **fraud_detection** — `WARNING` (0ms): 1 fraud signal(s)
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 3,
  "monthly_count": 3,
  "signals": [
    "Same-day claim count 4 exceeds limit 2"
  ]
}
  ```
- **decision_synthesizer** — `OK` (0ms): MANUAL_REVIEW: Fraud signals require manual review
  ```json
{
  "status": "MANUAL_REVIEW",
  "approved_amount": 4320.0,
  "rejection_reasons": [],
  "confidence": 0.932
}
  ```

---

## TC010 — Network Hospital — Discount Applied

**Result**: PASS

**Expected**:
```json
{
  "decision": "APPROVED",
  "approved_amount": 3240,
  "notes": "Network discount (20%) applied first on \u20b94,500 = \u20b93,600. Co-pay (10%) applied on \u20b93,600 = \u20b9360 deducted. Final: \u20b93,240.",
  "system_must": [
    "Apply network discount before co-pay, not after",
    "Show the breakdown of discount and co-pay in the decision output"
  ]
}
```

**Decision (actual)**:
- Status: **APPROVED**
- Approved: ₹3240.00 of ₹4500.00
- Confidence: 0.985
- Rejection reasons: —
- Summary: Approved ₹3,240.00
- User message: Approved: ₹3,240.00 of ₹4,500 claimed. Network discount applied: ₹900 (20%). Co-pay deducted: ₹360 (10%).
- Degraded: False, failed components: —

**system_must checks**:
- [x] Apply network discount before co-pay, not after
- [x] Show the breakdown of discount and co-pay in the decision output

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Deepak Shah
  ```json
{
  "member_id": "EMP010",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 4500.0,
  "treatment_date": "2024-11-03",
  "found_member": true,
  "document_count": 2,
  "member_name": "Deepak Shah"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for CONSULTATION (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": [
    "Deepak Shah",
    "Deepak Shah"
  ]
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F019",
      "type": "PRESCRIPTION",
      "patient": "Deepak Shah",
      "diagnosis": "Acute Bronchitis",
      "total": null,
      "line_items": 0,
      "confidence": 0.95
    },
    {
      "file_id": "F020",
      "type": "HOSPITAL_BILL",
      "patient": "Deepak Shah",
      "diagnosis": null,
      "total": 4500.0,
      "line_items": 2,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [
    "Deepak Shah"
  ],
  "hospital_names": [
    "Apollo Hospitals"
  ]
}
  ```
- **policy_adjudication** — `OK` (0ms): 13 policy rule(s) evaluated; 0 failed
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹4,500 -> discount 900 -> co-pay 360 -> final ₹3,240 (caps hit: ['SUB_LIMIT'])
  ```json
{
  "claimed_amount": 4500.0,
  "line_items_total_submitted": 4500.0,
  "line_items_accepted_total": 4500.0,
  "line_items_rejected_total": 0.0,
  "gross_after_line_items": 4500.0,
  "is_network_hospital": true,
  "network_discount_percent": 20,
  "network_discount_amount": 900.0,
  "after_discount": 3600.0,
  "copay_percent": 10,
  "copay_amount": 360.0,
  "after_copay": 3240.0,
  "sub_limit": 2000,
  "sub_limit_warning": true,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 5000.0,
  "per_claim_exceeded": false,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 8000.0,
  "ytd_remaining": 42000.0,
  "after_ytd_cap": 3240.0,
  "final_approved_amount": 3240.0,
  "caps_hit": [
    "SUB_LIMIT"
  ]
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): APPROVED: Approved ₹3,240.00
  ```json
{
  "status": "APPROVED",
  "approved_amount": 3240.0,
  "rejection_reasons": [],
  "confidence": 0.985
}
  ```

---

## TC011 — Component Failure — Graceful Degradation

**Result**: PASS

**Expected**:
```json
{
  "decision": "APPROVED",
  "system_must": [
    "Not crash or return a 500 error",
    "Indicate in the output that a component failed and was skipped",
    "Return a confidence score lower than a normal full-pipeline approval",
    "Include a note that manual review is recommended due to incomplete processing"
  ]
}
```

**Decision (actual)**:
- Status: **APPROVED**
- Approved: ₹4000.00 of ₹4000.00
- Confidence: 0.612
- Rejection reasons: —
- Summary: Approved ₹4,000.00
- User message: Approved: ₹4,000.00 of ₹4,000 claimed. Note: a non-critical component did not complete; manual review recommended for full audit.
- Degraded: True, failed components: ['fraud_detection']

**system_must checks**:
- [x] Not crash or return a 500 error
- [x] Indicate in the output that a component failed and was skipped
- [x] Return a confidence score lower than a normal full-pipeline approval
- [x] Include a note that manual review is recommended due to incomplete processing

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Kavita Nair
  ```json
{
  "member_id": "EMP006",
  "policy_id": "PLUM_GHI_2024",
  "category": "ALTERNATIVE_MEDICINE",
  "claimed_amount": 4000.0,
  "treatment_date": "2024-10-28",
  "found_member": true,
  "document_count": 2,
  "member_name": "Kavita Nair"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for ALTERNATIVE_MEDICINE (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": []
}
  ```
- **extraction_validation** — `WARNING` (0ms): 1 extraction validation issue(s) flagged across 1 document(s)
  ```json
{
  "issues_by_file": {
    "F021": [
      "patient_name missing on PRESCRIPTION (expected on this doc type)"
    ]
  }
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F021",
      "type": "PRESCRIPTION",
      "patient": null,
      "diagnosis": "Chronic Joint Pain",
      "total": null,
      "line_items": 0,
      "confidence": 0.8
    },
    {
      "file_id": "F022",
      "type": "HOSPITAL_BILL",
      "patient": null,
      "diagnosis": null,
      "total": 4000.0,
      "line_items": 2,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **re_verification** — `WARNING` (0ms): Re-extracted 1 document(s) with provider=mock; no measurable improvement (provider=mock may not act on feedback, or the underlying document didn't support a better extraction)
  ```json
{
  "iteration": 1,
  "cap": 1,
  "provider": "mock",
  "targets": [
    "F021"
  ],
  "retried": [
    "F021"
  ],
  "improved": [],
  "failed": []
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [],
  "hospital_names": [
    "Ayur Wellness Centre"
  ]
}
  ```
- **policy_adjudication** — `OK` (0ms): 13 policy rule(s) evaluated; 0 failed
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹4,000 -> discount 0 -> co-pay 0 -> final ₹4,000
  ```json
{
  "claimed_amount": 4000.0,
  "line_items_total_submitted": 4000.0,
  "line_items_accepted_total": 4000.0,
  "line_items_rejected_total": 0.0,
  "gross_after_line_items": 4000.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 4000.0,
  "copay_percent": 0,
  "copay_amount": 0.0,
  "after_copay": 4000.0,
  "sub_limit": 8000,
  "sub_limit_warning": false,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 8000.0,
  "per_claim_exceeded": false,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 0.0,
  "ytd_remaining": 50000.0,
  "after_ytd_cap": 4000.0,
  "final_approved_amount": 4000.0,
  "caps_hit": []
}
  ```
- **fraud_detection** — `ERROR` (0ms): fraud_detection failed; pipeline continuing in degraded mode
  - error: `SimulatedComponentFailure: Simulated component failure for graceful-degradation test`
  ```json
{}
  ```
- **decision_synthesizer** — `OK` (0ms): APPROVED: Approved ₹4,000.00
  ```json
{
  "status": "APPROVED",
  "approved_amount": 4000.0,
  "rejection_reasons": [],
  "confidence": 0.612
}
  ```

---

## TC012 — Excluded Treatment

**Result**: PASS

**Expected**:
```json
{
  "decision": "REJECTED",
  "rejection_reasons": [
    "EXCLUDED_CONDITION"
  ],
  "confidence_score": "above 0.90"
}
```

**Decision (actual)**:
- Status: **REJECTED**
- Approved: ₹0.00 of ₹8000.00
- Confidence: 0.955
- Rejection reasons: ['EXCLUDED_CONDITION', 'WAITING_PERIOD', 'PER_CLAIM_EXCEEDED']
- Summary: Diagnosis/treatment matches excluded condition: 'Obesity and weight loss programs'.
- User message: Your claim has been rejected because the diagnosis/treatment ('Morbid Obesity — BMI 37') is excluded under this policy ('Obesity and weight loss programs'). Excluded conditions are not covered regardless of amount or waiting period — please contact your HR team about alternative benefits if you need coverage for this.
- Degraded: False, failed components: —

**system_must checks**:

**Trace**:
- **intake** — `OK` (0ms): Intake validated for member Anita Desai
  ```json
{
  "member_id": "EMP009",
  "policy_id": "PLUM_GHI_2024",
  "category": "CONSULTATION",
  "claimed_amount": 8000.0,
  "treatment_date": "2024-10-18",
  "found_member": true,
  "document_count": 2,
  "member_name": "Anita Desai"
}
  ```
- **document_verification** — `OK` (0ms): All 2 document(s) verified for CONSULTATION (required: ['PRESCRIPTION', 'HOSPITAL_BILL'])
  ```json
{
  "uploaded_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "required_types": [
    "PRESCRIPTION",
    "HOSPITAL_BILL"
  ],
  "qualities": [
    "GOOD",
    "GOOD"
  ],
  "patient_names": []
}
  ```
- **extraction_validation** — `WARNING` (0ms): 1 extraction validation issue(s) flagged across 1 document(s)
  ```json
{
  "issues_by_file": {
    "F023": [
      "patient_name missing on PRESCRIPTION (expected on this doc type)"
    ]
  }
}
  ```
- **extraction** — `OK` (0ms): Extracted 2 document(s) with provider=mock
  ```json
{
  "documents": [
    {
      "file_id": "F023",
      "type": "PRESCRIPTION",
      "patient": null,
      "diagnosis": "Morbid Obesity \u2014 BMI 37",
      "total": null,
      "line_items": 0,
      "confidence": 0.8
    },
    {
      "file_id": "F024",
      "type": "HOSPITAL_BILL",
      "patient": null,
      "diagnosis": null,
      "total": 8000.0,
      "line_items": 2,
      "confidence": 0.95
    }
  ],
  "provider": "mock"
}
  ```
- **re_verification** — `WARNING` (0ms): Re-extracted 1 document(s) with provider=mock; no measurable improvement (provider=mock may not act on feedback, or the underlying document didn't support a better extraction)
  ```json
{
  "iteration": 1,
  "cap": 1,
  "provider": "mock",
  "targets": [
    "F023"
  ],
  "retried": [
    "F023"
  ],
  "improved": [],
  "failed": []
}
  ```
- **contradiction_detection** — `OK` (0ms): No cross-document contradictions detected
  ```json
{
  "patient_names": [],
  "hospital_names": []
}
  ```
- **policy_adjudication** — `WARNING` (0ms): 13 policy rule(s) evaluated; 2 failed: WAITING_PERIOD_OBESITY, EXCLUDED_CONDITION
  ```json
{
  "rules_evaluated": [
    {
      "rule_id": "COVERAGE_CHECK",
      "code": "COVERAGE_CHECK",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_DIABETES",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_HYPERTENSION",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_THYROID",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_JOINT_REPLACEMENT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MATERNITY",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_MENTAL_HEALTH",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_OBESITY",
      "code": "WAITING_PERIOD",
      "passed": false,
      "severity": "REJECT"
    },
    {
      "rule_id": "WAITING_PERIOD_HERNIA",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_CATARACT",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "WAITING_PERIOD_INITIAL",
      "code": "WAITING_PERIOD",
      "passed": true,
      "severity": "INFO"
    },
    {
      "rule_id": "EXCLUDED_CONDITION",
      "code": "EXCLUDED_CONDITION",
      "passed": false,
      "severity": "REJECT"
    },
    {
      "rule_id": "PRESCRIPTION_REQUIRED",
      "code": "PRESCRIPTION_MISSING",
      "passed": true,
      "severity": "INFO"
    }
  ]
}
  ```
- **financial_calculation** — `OK` (0ms): ₹8,000 -> discount 0 -> co-pay 800 -> final ₹0 (caps hit: ['PER_CLAIM'])
  ```json
{
  "claimed_amount": 8000.0,
  "line_items_total_submitted": 8000.0,
  "line_items_accepted_total": 8000.0,
  "line_items_rejected_total": 0.0,
  "gross_after_line_items": 8000.0,
  "is_network_hospital": false,
  "network_discount_percent": 0,
  "network_discount_amount": 0.0,
  "after_discount": 8000.0,
  "copay_percent": 10,
  "copay_amount": 800.0,
  "after_copay": 7200.0,
  "sub_limit": 2000,
  "sub_limit_warning": false,
  "per_claim_limit": 5000,
  "effective_per_claim_cap": 5000.0,
  "per_claim_exceeded": true,
  "annual_opd_limit": 50000,
  "ytd_claims_amount": 0.0,
  "ytd_remaining": 50000.0,
  "after_ytd_cap": 7200.0,
  "final_approved_amount": 0.0,
  "caps_hit": [
    "PER_CLAIM"
  ]
}
  ```
- **fraud_detection** — `OK` (0ms): No fraud signals raised
  ```json
{
  "thresholds": {
    "same_day_claims_limit": 2,
    "monthly_claims_limit": 6,
    "high_value_claim_threshold": 25000,
    "auto_manual_review_above": 25000,
    "fraud_score_manual_review_threshold": 0.8
  },
  "same_day_count": 0,
  "monthly_count": 0
}
  ```
- **decision_synthesizer** — `OK` (0ms): REJECTED: Diagnosis/treatment matches excluded condition: 'Obesity and weight loss programs'.
  ```json
{
  "status": "REJECTED",
  "approved_amount": 0.0,
  "rejection_reasons": [
    "EXCLUDED_CONDITION",
    "WAITING_PERIOD",
    "PER_CLAIM_EXCEEDED"
  ],
  "confidence": 0.955
}
  ```

---
