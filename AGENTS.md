# AGENTS.md

Reference for everyone (humans and coding agents) working in this repo.

This file lists every agent in the multi-agent claims pipeline, the
deliberation cycles that wrap them, and the ports they depend on. For
the *what* of the architecture (layers, DI, why these choices), see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). For low-level method
signatures and JSON contracts on the API and DB, see
[`docs/COMPONENT_CONTRACTS.md`](docs/COMPONENT_CONTRACTS.md).

This file is the single grep-target reviewers will use to answer the
question *"which agent does what, and what happens when it fails?"*

---

## Pipeline order

```
intake
  └─ document_verification
       └─ extraction ──▶ [re_verification] ──▶ contradiction_detection
                                                    └─ policy_adjudication
                                                         └─ financial_calculation
                                                              └─ fraud_detection ──▶ [policy_reconsider]
                                                                                          └─ decision_synthesizer
```

Solid arrows are unconditional. The two bracketed nodes are
deliberation cycles — they only run when an upstream agent left
evidence that we should look again. Hard cap of one iteration each.

Wiring lives in
[`backend/app/application/pipeline.py`](backend/app/application/pipeline.py)
(`build_pipeline`).

---

## Agents

Every agent inherits from
[`BaseAgent`](backend/app/application/agents/base.py) and exposes one
async method, `run(state: ClaimState) -> ClaimState`. Each agent has
two class-level flags:

| Flag | Meaning |
| --- | --- |
| `name: str` | Trace step key; appears in `state.trace[i].step`. |
| `is_critical: bool` | If `False`, the orchestrator catches exceptions, marks `state.degraded`, drops confidence, and continues. Critical failures propagate. |

The trace step key, the events emitted, and the early-stop conditions
below are the public contract — downstream code, the eval harness, and
the frontend all read them.

### 1. `intake` — IntakeAgent

[`backend/app/application/agents/intake.py`](backend/app/application/agents/intake.py)

- **Critical:** yes.
- **Reads:** `state.input` (member_id, policy_id, claim_category,
  claimed_amount, ytd_claims_amount, treatment_date, claims_history).
- **Writes:** trace step `intake`; may call
  `state.halt_early(reason, user_message)` for the four early-stop
  conditions.
- **Early-stop reasons:** `MEMBER_NOT_FOUND`, `POLICY_MISMATCH`,
  `INVALID_DATE_LOGIC`, `BELOW_MIN_CLAIM`.
- **Events:** `ClaimHaltedEarly` (via `halt_early`).
- **Does not call the LLM.** Pure policy-data lookup, fail-fast checks
  so we never burn tokens on an invalid claim.

### 2. `document_verification` — DocumentVerificationAgent

[`backend/app/application/agents/document_verification.py`](backend/app/application/agents/document_verification.py)

- **Critical:** yes.
- **Reads:** `state.input.documents` (file_id, actual_type, quality,
  patient_name_on_doc); `policy.document_requirements`.
- **Writes:** trace step `document_verification`; may halt early.
- **Early-stop reasons:** `DOCUMENT_TYPE_MISMATCH`,
  `DOCUMENT_UNREADABLE`, `PATIENT_MISMATCH`.
- **Events:** `ClaimHaltedEarly`.
- **Does not call the LLM.** Catches the failures the assignment
  expects to never reach extraction (TC001–TC003). The user message
  always names the specific file_id and what to do next.

### 3. `extraction` — ExtractionAgent

[`backend/app/application/agents/extraction.py`](backend/app/application/agents/extraction.py)

- **Critical:** no.
- **Depends on:** [`LLMProvider`](backend/app/application/ports/llm.py)
  port. Concrete adapters:
  [`MockProvider`](backend/app/infrastructure/llm/mock.py) (default,
  deterministic, reads pre-extracted `content` from the test fixture)
  and [`GeminiProvider`](backend/app/infrastructure/llm/gemini.py)
  (vision-capable, reads `bytes_b64` from a real upload).
- **Reads:** `state.input.documents`.
- **Writes:** `state.extracted: list[ExtractedDocument]`,
  `state.cost.add_llm(usage)` per document, trace steps `extraction`
  and `extraction_validation`. Each `ExtractedDocument` carries
  `extraction_confidence` (0–1) and `validation_issues: list[str]` set
  by the deterministic post-extractor
  ([`extraction_validator.py`](backend/app/domain/services/extraction_validator.py)).
- **Failure mode:** per-document failures are swallowed; the doc
  contributes a `failures[]` entry. If *every* doc fails, the agent
  marks `state.degraded` and continues; the synthesizer will route to
  `MANUAL_REVIEW`.

### 4. `re_verification` — deliberation cycle (factory node)

In `pipeline.py`, `_make_re_verification_node(provider)`.

- **Critical:** no — exceptions inside the node are caught per-doc and
  surfaced on the trace; the cycle never raises out.
- **Triggered by:** `_needs_re_extraction` — returns `True` when any
  extracted doc has `extraction_confidence < 0.7` or `validation_issues
  > 0` *and* `state.deliberation_iterations["re_extraction"] < 1`.
- **Behaviour:** calls `provider.extract_document(doc, feedback=...)`
  on each flagged doc, passing the validation issues as feedback. The
  Gemini adapter incorporates the feedback into the prompt and bumps
  temperature to 0.4; the Mock adapter records the feedback on `raw`
  and returns the same content (it's deterministic — the cycle is
  honest about this on the trace). Re-runs the validator on every new
  entry, swaps it into `state.extracted`, and increments
  `state.deliberation_iterations["re_extraction"]`.
- **Exits to:** `contradiction_detection` (skipping the no-op second
  pass through `extraction`).

### 5. `contradiction_detection` — ContradictionDetectionAgent

[`backend/app/application/agents/contradiction_detection.py`](backend/app/application/agents/contradiction_detection.py)

- **Critical:** no.
- **Reads:** `state.extracted` and `state.input`.
- **Writes:** `state.contradictions`, trace step
  `contradiction_detection`.
- **Does not call the LLM.** Cross-document checks (e.g. diagnosis on
  prescription vs medicines billed; clinical-pattern mismatch).
  Contradictions become evidence consumed by both `policy_adjudication`
  and the synthesizer's primary-reason picker.

### 6. `policy_adjudication` — PolicyAdjudicationAgent

[`backend/app/application/agents/policy_adjudication.py`](backend/app/application/agents/policy_adjudication.py)

- **Critical:** no.
- **Depends on:** [`RuleEngine`](backend/app/application/ports/rule_engine.py)
  port, implemented by
  [`DslRuleEngine`](backend/app/domain/policy/rules.py).
- **Reads:** the rule set in
  [`policy_rules.json`](policy_rules.json) (loaded once at composition
  time) plus `state`.
- **Writes:** `state.findings: list[PolicyFinding]` (every rule's
  result, passing or failing), trace step `policy_adjudication`.
- **Events:** none (the synthesizer is the one that fires
  `PolicyRulesFailed`).
- **The agent itself is a thin loop.** All actual policy logic lives in
  the JSON rules + the operator implementations in
  `app/domain/policy/rules.py`. Adding a new operator is a conscious
  ~5-line code change.

### 7. `financial_calculation` — FinancialCalculationAgent

[`backend/app/application/agents/financial_calculation.py`](backend/app/application/agents/financial_calculation.py)

- **Critical:** no.
- **Reads:** `state.extracted`, `state.findings`, `state.input`;
  `policy.opd_categories[category]`, `policy.coverage`.
- **Writes:** `state.line_decisions: list[LineItemDecision]` and the
  `breakdown: dict` (gross, line-item exclusions, network discount,
  co-pay, sub-limit cap, per-claim cap, YTD cap), trace step
  `financial_calculation`.
- **Ordering invariant:** network discount → co-pay → sub-limit cap →
  per-claim cap → YTD cap. This ordering is what makes TC010's
  expected `₹3,240` come out correct; flipping any two changes the
  number.

### 8. `fraud_detection` — FraudDetectionAgent

[`backend/app/application/agents/fraud_detection.py`](backend/app/application/agents/fraud_detection.py)

- **Critical:** no — and uniquely, this is the agent that
  `simulate_component_failure` will explicitly raise from to exercise
  the TC011 graceful-degradation path.
- **Reads:** `state.input.claims_history`, `state.input.simulate_component_failure`,
  `policy.fraud_thresholds`.
- **Writes:** `state.fraud_signals: list[str]`, trace step
  `fraud_detection`.
- **Events:** `FraudSignalsRaised` (on any signal),
  `ComponentDegraded` (on simulated failure).

### 9. `policy_reconsider` — deliberation cycle (plain node)

In `pipeline.py`, `_policy_reconsider_node`.

- **Triggered by:** `_needs_policy_reconsider` — returns `True` when
  `state.fraud_signals` is non-empty *and* no policy finding failed.
  Capped at one iteration.
- **Behaviour:** records a trace step explaining the disagreement
  (policy says clean, fraud says suspicious) and flags the claim for
  manual review by adding a `MANUAL_REVIEW_RECOMMENDED` note. The
  synthesizer then picks `MANUAL_REVIEW` status from those notes plus
  the fraud signals.

### 10. `decision_synthesizer` — DecisionSynthesizerAgent

[`backend/app/application/agents/decision_synthesizer.py`](backend/app/application/agents/decision_synthesizer.py)

- **Critical:** yes.
- **Reads:** everything on `state`.
- **Writes:** `state.decision: Decision` (status, approved_amount,
  rejection_reasons, confidence, summary, user_message, notes,
  breakdown, line_items), trace step `decision_synthesizer`.
- **Events:** `DecisionRendered`, `PolicyRulesFailed`,
  `ManualReviewRequired`.
- **Decision precedence (top to bottom — first match wins):**
  1. `state.degraded` or no `state.extracted` → `MANUAL_REVIEW`.
  2. Hard rejection — coverage failed, or any `HARD_REJECT_CODES`
     finding fired. The primary reason that drives the user message is
     picked by `_primary_rejection` using `_PRIMARY_REJECTION_PRIORITY`
     (exclusion > prescription-missing > pre-auth > per-claim >
     waiting-period > deadline > below-min). All hard codes still
     appear in `Decision.rejection_reasons`.
  3. Fraud requires manual review.
  4. Partial approval (some line items rejected but a non-zero amount
     approved).
  5. Approved.

---

## LLM Provider port

[`backend/app/application/ports/llm.py`](backend/app/application/ports/llm.py)

```python
class LLMProvider(ABC):
    name: str
    model: str

    async def extract_document(
        self, doc: DocumentInput, *, hint_category: str | None = None,
        feedback: str | None = None,
    ) -> tuple[ExtractedDocument, LLMUsage]: ...
```

Two adapters live behind this interface:

- **`MockProvider`** — deterministic, reads pre-extracted `content`
  from the fixture. Used by the eval suite, the integration tests, and
  any local run that hasn't set `GEMINI_API_KEY`. Accepts `feedback`
  for the deliberation cycle and records it on `raw` so the trace
  shows the retry happened, but the answer doesn't change.

- **`GeminiProvider`** — uses `google-generativeai` with vision input
  on `bytes_b64`. When `content` is rich (i.e. the
  `/api/claims/extract-preview` endpoint already extracted in this
  session), the adapter short-circuits with a zero-token usage record
  to honour the *one LLM call per uploaded document* invariant. On
  retry, `feedback` is appended to the prompt and the temperature is
  bumped from 0.1 to 0.4 to give the model room to actually change its
  answer.

---

## Event bus

[`backend/app/application/ports/event_bus.py`](backend/app/application/ports/event_bus.py)

Agents do not push to side-effect systems directly. They append
`DomainEvent` records to `state.pending_events` via
`state.record_event(event)` (or via the
`state.halt_early(reason, user_message)` helper for the only event the
state-shape forces). The HTTP layer (and the eval runner) drain those
events into the configured `EventBus` after each pipeline run.

Built-in subscribers (registered in `composition.py`):

| Handler | Responsibility |
| --- | --- |
| [`StructlogEventHandler`](backend/app/infrastructure/events/structlog_handler.py) | One structured log line per event for ops dashboards. |
| [`NotificationStubHandler`](backend/app/infrastructure/events/notification_stub_handler.py) | Stand-in for the future SMS/email integration — surfaces what would be sent to whom. |

Events emitted (search the codebase with `record_event`):

- `ClaimHaltedEarly` — any agent that calls `state.halt_early`.
- `ComponentDegraded` — pipeline wrapper, on non-critical agent exception.
- `FraudSignalsRaised` — `FraudDetectionAgent`.
- `PolicyRulesFailed`, `ManualReviewRequired`, `DecisionRendered` —
  `DecisionSynthesizerAgent`.

Adding a new event:
1. Add a `dataclass(frozen=True)` to
   [`backend/app/domain/events/__init__.py`](backend/app/domain/events/__init__.py).
2. Append it via `state.record_event(...)` from the agent that knows
   to do so.
3. Add a handler under `infrastructure/events/` and subscribe it in
   `composition.py` if you want a side effect.

---

## Adding a new agent

1. Create `backend/app/application/agents/<name>.py` with a class
   extending `BaseAgent`. Set `name = "<name>"` and `is_critical = ...`.
2. Implement `async def run(self, state: ClaimState) -> ClaimState`.
   Use `self.recorder(state).time_step(self.name)` to record a trace
   step; never write to `state.trace` directly.
3. Wire it into `build_pipeline` in
   [`pipeline.py`](backend/app/application/pipeline.py).
4. Add focused unit tests under `backend/tests/unit/test_<name>.py`.
   Inputs go in via `ClaimState`; assert on the trace step, the agent's
   own outputs on `state`, and any `state.pending_events`.

---

## Where things are *not* allowed to go

- **Domain layer** (`backend/app/domain/**`) must not import from
  `application`, `infrastructure`, or `interfaces`. Test this by
  reading the imports at the top of any file under `domain/`; they
  should reference only stdlib, pydantic, and other `domain` modules.
- **Application layer** may import from `domain` and from `application`
  ports. It must not import concrete adapters; those are passed in via
  the `Container` from `composition.py`.
- **The composition root** is the only place that knows about
  concrete LLM providers, the database URL, the rules file path, etc.
  If you find yourself importing `app.composition` from anywhere else,
  the dependency should be passed in instead.
