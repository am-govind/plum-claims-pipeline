# Component Contracts

For every significant component, this doc states:
- the input it accepts
- the output it produces (i.e. what it writes onto `ClaimState`)
- the typed errors it can raise
- the trace step it emits

Read together with the [Pydantic models](../backend/app/models) — those are
the executable spec. This doc is the reading order for a new engineer.

## Shared types

All defined in [backend/app/models/](../backend/app/models):

- `ClaimInput` — submission payload (member, category, treatment date,
  amount, hospital, YTD, claims_history, documents, simulate flag).
- `ClaimState` — the single mutable object flowing through the graph.
  Now also carries `agent_results: dict[str, AgentResult]`, `contradictions:
  list[Contradiction]`, `cost: CostBreakdown`, and `deliberation_iterations:
  dict[str, int]`.
- `ExtractedDocument` — structured fields produced by the extraction agent;
  `validation_issues: list[str]` is appended by the post-extraction validator.
- `PolicyFinding` — `{code, passed, message, evidence, evidence_links,
  severity, rule_id}`. Each rule emits one.
- `RuleResult` — output of the JSON rule engine. Carries
  `rule_id, code, passed, action, severity, message, evidence,
  evidence_links` and is converted to `PolicyFinding` by the
  `PolicyAdjudicationAgent`.
- `AgentResult` — per-agent confidence record consumed by the formal
  formula: `{confidence, evidence_strength, contradiction_score, notes}`.
- `EvidenceLink` — pointer back to source document/field/snippet, attached
  to findings, contradictions, and decision-tree nodes.
- `Contradiction` — `{kind, description, severity, evidence,
  confidence}`; emitted by the contradiction agent.
- `LineItemDecision` — per-line-item approve/reject for partials.
- `DecisionNode` — recursive tree node for the explanation tree.
- `CostBreakdown` — pipeline-wide token + latency rollup.
  `LLMUsage` records sit on `cost.llm_calls`; node latencies on
  `cost.node_latencies`.
- `Decision` — final synthesized output: status, approved amount,
  confidence, reasons, user message, breakdown, **plus**
  `explanation_tree: DecisionNode`, `cost: CostBreakdown`,
  `evidence_links: list[EvidenceLink]`, `confidence_breakdown: dict`.
- `TraceStep` — `{step, status, summary, evidence, confidence_delta, latency_ms, error}`.
- `DecisionStatus` enum: `APPROVED`, `PARTIAL`, `REJECTED`,
  `MANUAL_REVIEW`, `NEEDS_REUPLOAD`, `NEEDS_CORRECTION`,
  `NEEDS_CLARIFICATION`, `ESCALATED_MEDICAL_REVIEW`,
  `FRAUD_INVESTIGATION`.

Errors all derive from `ClaimError` and translate to user-facing messages
through `error_to_user_message` ([backend/app/models/errors.py](../backend/app/models/errors.py)).

---

## IntakeAgent

[backend/app/agents/intake.py](../backend/app/agents/intake.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input` (member_id, policy_id, claimed_amount) |
| **Writes** | `state.findings` (BELOW_MIN_CLAIM if applicable); `state.early_stop` + `state.early_stop_user_message` if member or policy not found |
| **Trace step** | `intake` |
| **Errors** | None raised; failures recorded as early-stop |
| **Critical?** | Yes (re-raised on unhandled exception) |

---

## DocumentVerificationAgent

[backend/app/agents/document_verification.py](../backend/app/agents/document_verification.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input.documents`, `state.input.claim_category`, `policy.document_requirements` |
| **Writes** | `state.early_stop`, `state.early_stop_reason`, `state.early_stop_user_message` on failure |
| **Trace step** | `document_verification` |
| **Errors raised internally** | `DocumentTypeMismatchError`, `UnreadableDocumentError`, `PatientMismatchError` (each translated to a specific user message) |
| **Critical?** | Yes |

The three early-stop conditions cover TC001 (wrong type), TC002
(unreadable), TC003 (patient mismatch). The user message is built by
`error_to_user_message`.

---

## ExtractionAgent

[backend/app/agents/extraction.py](../backend/app/agents/extraction.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input.documents` |
| **Writes** | `state.extracted` (list of ExtractedDocument with `validation_issues` set), `state.cost.llm_calls`, `state.agent_results["extraction"]` |
| **Trace steps** | `extraction`, `extraction_validation` |
| **Errors** | `ProviderError`, `LLMTimeoutError` per document; aggregated into the trace; total failure marks `state.degraded=True` |
| **Critical?** | No (orchestrator catches; degrades) |

After the LLM call, every extracted doc passes through
[`validate_extraction`](../backend/app/agents/extraction_validator.py):
bill-total reconciliation, document-date sanity, doctor-registration
regex, negative-amount check, patient-name presence. Each failed check
appends a string to `validation_issues` and lowers
`extraction_confidence` by 0.15 (floored at 0).

---

## ContradictionDetectionAgent

[backend/app/agents/contradiction_detection.py](../backend/app/agents/contradiction_detection.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.extracted`, `state.input.treatment_date`, `state.input.claimed_amount` |
| **Writes** | `state.contradictions`, `state.agent_results["contradiction_detection"]` |
| **Trace step** | `contradiction_detection` |
| **Critical?** | No |

Checks (each emits a `Contradiction` if it fires):

| Kind | Trigger |
| --- | --- |
| `PATIENT_NAME_INCONSISTENT` | Fuzzy patient-name match across docs falls below 80 |
| `DATE_DISCREPANCY` | Any extracted document_date is more than ±7 days from submitted treatment_date |
| `HOSPITAL_NAME_INCONSISTENT` | Hospital name fuzzy-matches below 75 across docs |
| `AMOUNT_RECONCILIATION_FAILED` | `sum(line_items)` differs from `total_amount` by more than 5% |
| `CLAIMED_EXCEEDS_BILLS` | Claimed amount exceeds the highest bill total by more than 5% |
| `DIAGNOSIS_TREATMENT_MISMATCH` | Diagnosis keyword present but no expected treatment/test/medicine matches the lightweight allowlist |

None of the 12 fixture cases trigger these (intentional contradictions in
TC003 are caught upstream by document verification), so the eval suite
stays green.

---

## PolicyAdjudicationAgent

[backend/app/agents/policy_adjudication.py](../backend/app/agents/policy_adjudication.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.extracted`, `state.input`, policy, `policy_rules.json` |
| **Writes** | `state.findings` (one PolicyFinding per rule), `state.agent_results["policy_adjudication"]` |
| **Trace step** | `policy_adjudication` |
| **Critical?** | No |

The agent is a thin loop over the JSON rule engine. Rule IDs in
`policy_rules.json` map to legacy `code` values so the synthesizer
logic and eval suite are unchanged:

| Rule ID | code | Notes |
| --- | --- | --- |
| `COVERAGE_CHECK` | `COVERAGE_CHECK` | inverse_pass; fires when category covered |
| `WAITING_PERIOD_DIABETES` | `WAITING_PERIOD` | Uses `${policy.waiting_periods.specific_conditions.diabetes}` |
| `WAITING_PERIOD_HYPERTENSION` … `WAITING_PERIOD_CATARACT` | `WAITING_PERIOD` | One per condition |
| `WAITING_PERIOD_INITIAL` | `WAITING_PERIOD` | 30-day catch-all |
| `EXCLUDED_CONDITION` | `EXCLUDED_CONDITION` | TC012; reuses `diagnosis_excluded_reason` helper |
| `PRE_AUTH_DIAGNOSTIC_HIGH_VALUE` | `PRE_AUTH_MISSING` | TC007 |
| `PRESCRIPTION_REQUIRED` | `PRESCRIPTION_MISSING` | per-category requirement |

---

## FinancialCalculationAgent

[backend/app/agents/financial_calculation.py](../backend/app/agents/financial_calculation.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.extracted`, `state.input.claim_category`, `state.input.claimed_amount`, `state.input.hospital_name`, `state.input.ytd_claims_amount`, policy |
| **Writes** | `state.line_decisions`, `state.findings` (FINANCIAL_CALCULATION + cap findings) |
| **Trace step** | `financial_calculation` |
| **Critical?** | No |

Cap-related findings:

| Finding code | When |
| --- | --- |
| `FINANCIAL_CALCULATION` | Always; carries the breakdown |
| `PER_CLAIM_EXCEEDED` | `gross_after_line_items > max(per_claim_limit, sub_limit)` |
| `SUB_LIMIT_EXCEEDED` | After-copay > category sub_limit (informational, not enforced) |
| `YTD_LIMIT_EXCEEDED` | Capped at YTD remaining |
| `LINE_ITEM_EXCLUDED` | At least one line item filtered out |

Breakdown keys (for the `Decision.breakdown` dict): `claimed_amount`,
`gross_after_line_items`, `is_network_hospital`, `network_discount_percent`,
`network_discount_amount`, `after_discount`, `copay_percent`, `copay_amount`,
`after_copay`, `sub_limit`, `sub_limit_warning`, `per_claim_limit`,
`effective_per_claim_cap`, `per_claim_exceeded`, `annual_opd_limit`,
`ytd_claims_amount`, `ytd_remaining`, `after_ytd_cap`,
`final_approved_amount`, `caps_hit`.

---

## FraudDetectionAgent

[backend/app/agents/fraud_detection.py](../backend/app/agents/fraud_detection.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input` (claims_history, claimed_amount, simulate flag), `policy.fraud_thresholds` |
| **Writes** | `state.fraud_signals`, FRAUD_SIGNALS finding |
| **Trace step** | `fraud_detection` |
| **Errors raised** | `SimulatedComponentFailure` if `simulate_component_failure=True`; orchestrator catches and degrades (TC011) |
| **Critical?** | No |

Signals: same-day count (TC009), trailing-30-day count, high-value /
auto-MR threshold breach.

---

## DecisionSynthesizerAgent

[backend/app/agents/decision_synthesizer.py](../backend/app/agents/decision_synthesizer.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.findings`, `state.line_decisions`, `state.fraud_signals`, `state.contradictions`, `state.agent_results`, `state.degraded`, `state.failed_components`, `state.cost` |
| **Writes** | `state.decision` (Decision, including `explanation_tree`, `cost`, `confidence_breakdown`), `state.confidence` |
| **Trace step** | `decision_synthesizer` |
| **Critical?** | Yes |

Status precedence:

1. **REJECTED** if any hard-rejection finding (`WAITING_PERIOD`,
   `EXCLUDED_CONDITION`, `PRE_AUTH_MISSING`, `PER_CLAIM_EXCEEDED`,
   `PRESCRIPTION_MISSING`, `BELOW_MIN_CLAIM`) failed, or coverage failed.
2. **FRAUD_INVESTIGATION** if fraud signals AND a high-severity
   contradiction (`PATIENT_NAME_INCONSISTENT` /
   `AMOUNT_RECONCILIATION_FAILED`) are both present.
3. **ESCALATED_MEDICAL_REVIEW** if a `DIAGNOSIS_TREATMENT_MISMATCH`
   contradiction was raised.
4. **MANUAL_REVIEW** if fraud signals present, or degraded with
   `final_amount <= 0`.
5. **NEEDS_CLARIFICATION** if extraction succeeded but a doc has 2+
   validation issues or very low confidence and no other rejection
   decided the case.
6. **PARTIAL** if line-item exclusions present and `final_amount > 0`.
7. **APPROVED** if `final_amount > 0`. If `state.degraded`, status stays
   `APPROVED` but `requires_manual_review=True` and a note is added.
8. **REJECTED** as fallback when `final_amount == 0` and no other reason.

Confidence comes from the formal formula in
[`backend/app/decision/confidence.py`](../backend/app/decision/confidence.py):
`C_final = clip(Σ wᵢ·Cᵢ − α·contradiction − β·degraded, 0, 1)`. Each
`wᵢ·Cᵢ` term is exposed on `decision.confidence_breakdown` and rendered
in the UI.

The synthesizer also builds the `DecisionNode` explanation tree
(via [`build_explanation_tree`](../backend/app/decision/explanation_builder.py))
and attaches `state.cost` (with all per-LLM-call usage and per-node
latency records) to the decision.

---

## Deliberation cycles

Two LangGraph cycles add a "second opinion" loop, both with hard caps to
guarantee termination.

### `re_verification` (cap = 1)

Triggers when any extracted doc has `extraction_confidence < 0.7` OR any
`validation_issues`. Bumps `state.deliberation_iterations["re_extraction"]`,
records a trace step, and routes back to extraction. None of the 12
fixture cases trigger this (mock confidences are 0.95).

### `policy_reconsider` (cap = 1)

Triggers when fraud raised signals AND no policy finding failed —
"fraud sees something the rule engine didn't". Records a trace step,
forces `MANUAL_REVIEW` semantics in the synthesizer downstream, then
routes to decision synthesis. TC009 (multi same-day claims with all
policy checks passing) does fire this cycle and the trace shows it.

---

## LLMProvider

[backend/app/llm/base.py](../backend/app/llm/base.py)

```python
class LLMProvider(ABC):
    name: str
    model: str

    async def extract_document(
        self,
        doc: DocumentInput,
        *,
        hint_category: str | None = None,
    ) -> tuple[ExtractedDocument, LLMUsage]:
        ...
```

`LLMUsage` carries `model`, `tokens_in`, `tokens_out`, `latency_ms`, and
`usd_estimate` (computed via `app.models.cost.estimate_usd` against a
small per-model rate table). The orchestrator appends each usage record
to `state.cost.llm_calls`.

| Implementation | When used | Errors |
| --- | --- | --- |
| `MockProvider` | Tests, eval suite, missing API key | `ProviderError` for malformed mock content; usage is synthesized from payload size |
| `GeminiProvider` | `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` set | `ProviderError`, `LLMTimeoutError` (30s timeout); usage pulled from `response.usage_metadata` |

---

## TraceRecorder

[backend/app/trace/recorder.py](../backend/app/trace/recorder.py)

```python
class TraceRecorder:
    def __init__(self, state: ClaimState): ...
    def record(self, step: str, *, status, summary, evidence=None,
               confidence_delta=0.0, latency_ms=0, error=None) -> TraceStep
    @contextmanager
    def time_step(self, step: str) -> Iterator[dict[str, Any]]
```

`time_step` measures elapsed ms; the agent reads `ctx['latency_ms']` after
the block and passes it to `record`. This is the only place latency is
captured.

---

## API endpoints

[backend/app/api/](../backend/app/api)

| Method | Path | Body / params | Returns |
| --- | --- | --- | --- |
| POST | `/api/claims` | `ClaimInput` JSON | `{claim_id, state}` (full ClaimState JSON) |
| GET | `/api/claims/{id}` | — | `{claim_id, state}` |
| GET | `/api/claims?limit=50` | — | List of summary records |
| GET | `/api/members` | — | Member roster from `policy_terms.json` |
| GET | `/api/policy` | — | Policy summary (categories, doc requirements, network hospitals, thresholds) |
| GET | `/api/eval/run` | — | `{total, passed, failed, results: [...]}` |
| GET | `/health` | — | `{status, llm_provider}` |

---

## Errors raised across the system (and their codes)

| Error | Code | Where | Maps to user message in |
| --- | --- | --- | --- |
| `DocumentTypeMismatchError` | `DOCUMENT_TYPE_MISMATCH` | Verification | Lists uploaded vs required vs missing types |
| `UnreadableDocumentError` | `DOCUMENT_UNREADABLE` | Verification | Names the file_id; tells member to re-upload only that file |
| `PatientMismatchError` | `PATIENT_MISMATCH` | Verification | Names every patient and the file each came from |
| `ProviderError` | n/a | Extraction | Recorded on trace; per-doc failure |
| `LLMTimeoutError` | n/a | Extraction | Recorded on trace; per-doc failure |
| `SimulatedComponentFailure` | n/a | Fraud | Caught by orchestrator; degrades |
| Rejection codes | `WAITING_PERIOD`, `EXCLUDED_CONDITION`, `PRE_AUTH_MISSING`, `PER_CLAIM_EXCEEDED`, etc. | Synthesizer | Each gets a tailored user message in `decision_synthesizer._user_message_for_rejection` |
