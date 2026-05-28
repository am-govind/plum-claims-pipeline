# Component Contracts

For every significant component, this doc states:
- the input it accepts
- the output it produces (i.e. what it writes onto `ClaimState`)
- the typed errors it can raise
- the trace step it emits
- the domain events it records (where applicable)

Read together with the domain models under
[`backend/app/domain/`](../backend/app/domain) — those are the
executable spec. This doc is the reading order for a new engineer.

## Layering and wiring

The backend follows hex-layer naming:

- `backend/app/domain/` — pure types and rules (no I/O).
- `backend/app/application/` — pipeline, agents, and abstract ports.
- `backend/app/infrastructure/` — concrete adapters (SQLAlchemy, JSON
  loaders, Gemini/Mock providers, in-memory event bus + handlers).
- `backend/app/interfaces/http/` — FastAPI routers and `Depends()`
  providers.

Everything is constructed at the composition root
([`backend/app/composition.py`](../backend/app/composition.py)) into a
single `Container` and handed out via `Depends()`. There are no
module-level singletons.

## Shared types

Defined under [`backend/app/domain/`](../backend/app/domain):

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
- `DomainEvent` and seven concrete events
  (`ClaimApproved`, `ClaimPartiallyApproved`, `ClaimRejected`,
  `ManualReviewRequired`, `ClaimHaltedEarly`, `ComponentDegraded`,
  `FraudSignalsRaised`) under
  [`backend/app/domain/events/`](../backend/app/domain/events). Frozen
  dataclasses carrying `claim_id`, `occurred_at`, and a small,
  hand-picked payload per event.

`ClaimState` also exposes three aggregate methods:

- `state.record_event(event)` — buffer a domain event for later dispatch.
- `state.pull_events()` — return all buffered events and clear the
  buffer (called once per pipeline run by the API layer / eval runner).
- `state.halt_early(reason, user_message)` — set the three
  `early_stop*` fields **and** record a `ClaimHaltedEarly` event in
  one atomic step. All early-stop sites (intake + document
  verification) go through this method so the field set and the event
  can never drift apart.

Errors all derive from `ClaimError` and translate to user-facing messages
through `error_to_user_message` ([backend/app/domain/errors.py](../backend/app/domain/errors.py)).

---

## IntakeAgent

[backend/app/application/agents/intake.py](../backend/app/application/agents/intake.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input` (member_id, policy_id, claimed_amount) |
| **Writes** | `state.findings` (BELOW_MIN_CLAIM if applicable). On member-not-found or policy-mismatch calls `state.halt_early(reason, user_message)`, which sets `early_stop` / `early_stop_reason` / `early_stop_user_message` and records `ClaimHaltedEarly` |
| **Events** | `ClaimHaltedEarly` (via `state.halt_early`) on early-stop paths |
| **Trace step** | `intake` |
| **Errors** | None raised; failures recorded as early-stop |
| **Critical?** | Yes (re-raised on unhandled exception) |

---

## DocumentVerificationAgent

[backend/app/application/agents/document_verification.py](../backend/app/application/agents/document_verification.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input.documents`, `state.input.claim_category`, `policy.document_requirements` |
| **Writes** | On failure calls `state.halt_early(err.code, error_to_user_message(err))`, which sets the three `early_stop*` fields and records `ClaimHaltedEarly` |
| **Events** | `ClaimHaltedEarly` (via `state.halt_early`) on every failure path |
| **Trace step** | `document_verification` |
| **Errors raised internally** | `DocumentTypeMismatchError`, `UnreadableDocumentError`, `PatientMismatchError` (each translated to a specific user message) |
| **Critical?** | Yes |

The three early-stop conditions cover TC001 (wrong type), TC002
(unreadable), TC003 (patient mismatch). The user message is built by
`error_to_user_message`. The agent never mutates the early-stop fields
directly — it always goes through `state.halt_early` so the field set
and the `ClaimHaltedEarly` event stay coupled.

---

## ExtractionAgent

[backend/app/application/agents/extraction.py](../backend/app/application/agents/extraction.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input.documents` |
| **Writes** | `state.extracted` (list of ExtractedDocument with `validation_issues` set), `state.cost.llm_calls`, `state.agent_results["extraction"]` |
| **Trace steps** | `extraction`, `extraction_validation` |
| **Errors** | `ProviderError`, `LLMTimeoutError` per document; aggregated into the trace; total failure marks `state.degraded=True` |
| **Critical?** | No (orchestrator catches; degrades) |

After the LLM call, every extracted doc passes through
[`validate_extraction`](../backend/app/domain/services/extraction_validator.py):
bill-total reconciliation, document-date sanity, doctor-registration
regex, negative-amount check, patient-name presence. Each failed check
appends a string to `validation_issues` and lowers
`extraction_confidence` by 0.15 (floored at 0).

---

## ContradictionDetectionAgent

[backend/app/application/agents/contradiction_detection.py](../backend/app/application/agents/contradiction_detection.py)

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

[backend/app/application/agents/policy_adjudication.py](../backend/app/application/agents/policy_adjudication.py)

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

[backend/app/application/agents/financial_calculation.py](../backend/app/application/agents/financial_calculation.py)

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

[backend/app/application/agents/fraud_detection.py](../backend/app/application/agents/fraud_detection.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.input` (claims_history, claimed_amount, simulate flag), `policy.fraud_thresholds` |
| **Writes** | `state.fraud_signals`, FRAUD_SIGNALS finding |
| **Events** | `FraudSignalsRaised` whenever at least one signal is produced |
| **Trace step** | `fraud_detection` |
| **Errors raised** | `SimulatedComponentFailure` if `simulate_component_failure=True`; orchestrator catches and degrades (TC011) |
| **Critical?** | No |

Signals: same-day count (TC009), trailing-30-day count, high-value /
auto-MR threshold breach.

---

## DecisionSynthesizerAgent

[backend/app/application/agents/decision_synthesizer.py](../backend/app/application/agents/decision_synthesizer.py)

| Field | Value |
| --- | --- |
| **Reads** | `state.findings`, `state.line_decisions`, `state.fraud_signals`, `state.contradictions`, `state.agent_results`, `state.degraded`, `state.failed_components`, `state.cost` |
| **Writes** | `state.decision` (Decision, including `explanation_tree`, `cost`, `confidence_breakdown`), `state.confidence` |
| **Events** | One of `ClaimApproved`, `ClaimPartiallyApproved`, `ClaimRejected`, or `ManualReviewRequired` based on the final `DecisionStatus` |
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
[`backend/app/domain/services/confidence.py`](../backend/app/domain/services/confidence.py):
`C_final = clip(Σ wᵢ·Cᵢ − α·contradiction − β·degraded, 0, 1)`. Each
`wᵢ·Cᵢ` term is exposed on `decision.confidence_breakdown` and rendered
in the UI.

The synthesizer also builds the `DecisionNode` explanation tree
(via [`build_explanation_tree`](../backend/app/domain/services/explanation_builder.py))
and attaches `state.cost` (with all per-LLM-call usage and per-node
latency records) to the decision.

---

## Deliberation cycles

Two LangGraph cycles add a "second opinion" loop, both with hard caps to
guarantee termination.

### `re_verification` (cap = 1)

Triggers when any extracted doc has `extraction_confidence < 0.7` OR any
`validation_issues`. For each flagged document it re-calls
`provider.extract_document(doc, feedback=...)`, passing the prior
validation issues as feedback. The Gemini adapter incorporates the
feedback into the prompt and bumps temperature from 0.1 to 0.4 so the
model is actually allowed to change its answer; the Mock adapter records
the feedback on `raw` (mock content is deterministic, so the answer is
unchanged) and the trace explicitly notes that. The new entry is
re-run through the deterministic validator and swapped into
`state.extracted` in place. Per-doc retry failures are non-fatal — the
original extraction is kept and the failure is recorded on the trace.
Bumps `state.deliberation_iterations["re_extraction"]` exactly once per
invocation and routes to `contradiction_detection` (no need to loop
back through `extraction`).

### `policy_reconsider` (cap = 1)

Triggers when fraud raised signals AND no policy finding failed —
"fraud sees something the rule engine didn't". Records a trace step,
forces `MANUAL_REVIEW` semantics in the synthesizer downstream, then
routes to decision synthesis. TC009 (multi same-day claims with all
policy checks passing) does fire this cycle and the trace shows it.

---

## LLMProvider

[backend/app/application/ports/llm.py](../backend/app/application/ports/llm.py) (port)
· [backend/app/infrastructure/llm/](../backend/app/infrastructure/llm) (adapters)

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

### Provider branches for the upload + preview path

Both providers have three input shapes. Branch selection is deterministic:

| Branch | Trigger | Behaviour | LLM call? |
| --- | --- | --- | --- |
| **Vision OCR** | `bytes_b64` + `mime_type` set | Real OCR on the uploaded image/PDF. Gemini only — mock falls into the "upload stub" branch instead. | Yes (Gemini) |
| **Upload stub (mock)** | `bytes_b64` set, no `content`, mock provider | Returns an explicitly low-confidence stub (`extraction_confidence=0.45`, `raw._mock_source="uploaded_bytes_stub"`) so the demo flow is visible without a Gemini key. | No |
| **Content fallback** | `content` populated, no `bytes_b64` | Builds `ExtractedDocument` from `content` directly. Used by both providers at submit-time after the preview has already extracted (so we don't pay for OCR twice or hallucinate from a filename). | No |
| **Typed-only fallback** | No `bytes_b64`, no `content` | Skeleton extraction from `doc.actual_type` / `doc.patient_name_on_doc` with medium confidence. Eval suite path when a fixture omits `content`. | No |

**Invariant**: exactly one Gemini call per uploaded document across the
whole `preview → autofill → submit → pipeline` flow. The preview is the
canonical extraction; submit-time extraction is content-driven.

---

## TraceRecorder

[backend/app/application/recorder.py](../backend/app/application/recorder.py) · `TraceStep` model in [backend/app/domain/trace/](../backend/app/domain/trace)

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

[backend/app/interfaces/http/](../backend/app/interfaces/http)

| Method | Path | Body / params | Returns |
| --- | --- | --- | --- |
| POST | `/api/claims` | `ClaimInput` JSON | `{claim_id, state}` (full ClaimState JSON) |
| POST | `/api/claims/extract-preview` | `{document: DocumentInput, hint_category?: str}` | `ExtractPreviewResponse` (see below) |
| GET | `/api/claims/{id}` | — | `{claim_id, state}` |
| GET | `/api/claims?limit=50` | — | List of summary records |
| GET | `/api/members` | — | Member roster from `policy_terms.json` |
| GET | `/api/policy` | — | Policy summary (categories, doc requirements, network hospitals, thresholds) |
| GET | `/api/eval/run` | — | `{total, passed, failed, results: [...]}` |
| GET | `/health` | — | `{status, llm_provider}` |

### `POST /api/claims/extract-preview`

Runs only the configured LLM provider on one uploaded document so the
form can pre-fill the typed fields. No pipeline, no persistence, no
events. Failure is encoded inline (HTTP 200) so the UI shows
actionable guidance instead of a generic 500:

```jsonc
// success
{
  "ok": true,
  "extracted": { /* ExtractedDocument */ },
  "usage":     { "model": "...", "tokens_in": 0, "tokens_out": 0, ... },
  "validation_issues": []
}
// failure (provider timeout / parse error / missing API key)
{
  "ok": false,
  "extracted": null,
  "usage": null,
  "validation_issues": [],
  "reason": "ProviderError",
  "message": "Gemini call failed for F001: ..."
}
```

Errors:
- `422 Unprocessable Entity` if `bytes_b64` exceeds ~10 MB (`MAX_BYTES_B64_LEN = 14_000_000` chars). The size validator on `DocumentInput.bytes_b64` runs before the provider is invoked.
- `{ok: false, reason: "ProviderError" | "LLMTimeoutError" | ...}` for any extraction failure (HTTP 200).

Persistence note: when the full claim is later POSTed to `/api/claims`,
the frontend sends only the typed `content` (auto-filled from this
preview, optionally user-edited). It does not re-send `bytes_b64`. The
SqlAlchemy repository also strips `bytes_b64` and `mime_type` from any
documents it does receive before writing to SQLite, so uploaded images
are never persisted.

The `POST /api/claims` and `GET /api/eval/run` paths both finish with:

```python
state = await pipeline(state)
await claims.save(state)
await event_bus.publish_all(state.pull_events())
```

so domain events are dispatched exactly once per claim, after state is
persisted.

---

## EventBus and handlers

Port: [backend/app/application/ports/event_bus.py](../backend/app/application/ports/event_bus.py)
· Adapter: [backend/app/infrastructure/events/](../backend/app/infrastructure/events)

```python
class EventBus(ABC):
    def subscribe(self, handler: EventHandler) -> None: ...
    async def publish(self, event: DomainEvent) -> None: ...
    async def publish_all(self, events: Iterable[DomainEvent]) -> None: ...

class EventHandler(ABC):
    async def handle(self, event: DomainEvent) -> None: ...
```

| Implementation | Behaviour |
| --- | --- |
| `InMemoryEventBus` | Sequential async fan-out to subscribed handlers; per-handler exception isolation — one failing handler never breaks another or fails the request |
| `StructlogEventHandler` | Logs every event as a structured `domain_event` log line. Default audit sink |
| `NotificationStubHandler` | Logs a `would_notify` line for `ClaimApproved`, `ClaimRejected`, `ClaimPartiallyApproved`, `ManualReviewRequired`, and `ClaimHaltedEarly`. Swap the body for an SMS/email gateway in production |

Both handlers are subscribed by the composition root
([`backend/app/composition.py`](../backend/app/composition.py)); they
are injected into the FastAPI layer via the `get_event_bus` `Depends()`
provider and into the eval runner via the `Container`.

| Event | Raised by | Trigger |
| --- | --- | --- |
| `ClaimApproved` | `DecisionSynthesizerAgent` | Final status = `APPROVED` |
| `ClaimPartiallyApproved` | `DecisionSynthesizerAgent` | Final status = `PARTIAL` |
| `ClaimRejected` | `DecisionSynthesizerAgent` | Final status = `REJECTED` |
| `ManualReviewRequired` | `DecisionSynthesizerAgent` | Final status in `{MANUAL_REVIEW, NEEDS_REUPLOAD, NEEDS_CORRECTION, NEEDS_CLARIFICATION, ESCALATED_MEDICAL_REVIEW, FRAUD_INVESTIGATION}` |
| `ClaimHaltedEarly` | `IntakeAgent`, `DocumentVerificationAgent` (via `state.halt_early`) | Member/policy lookup failure, wrong / unreadable / mismatched documents |
| `ComponentDegraded` | `pipeline._wrap` | Non-critical agent raised an exception caught by the orchestrator |
| `FraudSignalsRaised` | `FraudDetectionAgent` | At least one fraud signal produced |

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
