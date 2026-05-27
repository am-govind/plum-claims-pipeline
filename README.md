# Multi-Agent Claims Pipeline

> Read [`assignment.md`](assignment.md) in full before reading the code — it
> defines what the system must do and what the deliverables are.

A multi-agent health-insurance claims processing system. A Python
(FastAPI + LangGraph) backend coordinates eight specialised agents over
a shared `ClaimState` object, with two deliberation cycles for
re-extraction and policy reconsideration. A Next.js frontend renders
the decision, an interactive explanation tree, the per-step trace, and
the formal confidence breakdown.

Highlights:

- **All 12 test cases pass deterministically** ([`docs/EVAL_REPORT.md`](docs/EVAL_REPORT.md)).
- **JSON-driven rule engine** — every policy rule lives in
  [`policy_rules.json`](policy_rules.json) and is evaluated by a tiny
  custom DSL ([`backend/app/domain/policy/rules.py`](backend/app/domain/policy/rules.py)).
- **Cross-document contradiction detection** ([`backend/app/application/agents/contradiction_detection.py`](backend/app/application/agents/contradiction_detection.py)).
- **Post-extraction validator** flags hallucinations, bad dates, and
  amount-reconciliation failures ([`backend/app/domain/services/extraction_validator.py`](backend/app/domain/services/extraction_validator.py)).
- **Formal confidence math** — `Σ wᵢ·Cᵢ − α·contradiction − β·degraded`
  ([`backend/app/domain/services/confidence.py`](backend/app/domain/services/confidence.py)).
- **Hex-layer DDD architecture** — `domain` / `application` / `infrastructure` / `interfaces`, constructor-injected dependencies wired in one composition root ([`backend/app/composition.py`](backend/app/composition.py)).
- **Domain events** — `ClaimApproved`, `ClaimRejected`, `ManualReviewRequired`, `ClaimHaltedEarly`, `ComponentDegraded`, `FraudSignalsRaised` etc., published via an in-memory `EventBus` after every claim run ([`backend/app/domain/events/`](backend/app/domain/events), [`backend/app/infrastructure/events/`](backend/app/infrastructure/events)).
- **Decision Explanation Tree** rendered as a clickable tree with
  per-node evidence ([`frontend/components/DecisionTree.tsx`](frontend/components/DecisionTree.tsx)).
- **Token / cost / latency tracking** per LLM call, surfaced on the
  decision card and the eval report.
- **Architecture**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- **Component contracts**: [`docs/COMPONENT_CONTRACTS.md`](docs/COMPONENT_CONTRACTS.md).

## 30-second quick start

```bash
docker compose up --build
# UI:  http://localhost:3000
# API: http://localhost:8000/docs
```

That uses the deterministic mock LLM provider so it runs offline. To use
real Gemini for live document upload:

```bash
export GEMINI_API_KEY=...
export LLM_PROVIDER=gemini
docker compose up --build
```

## Local dev (without Docker)

```bash
# Backend
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Run the test suite

```bash
cd backend && pytest
```

55 tests: 12 integration tests (one per `test_cases.json` case) plus 43
unit tests covering the rule engine, contradiction detection,
extraction validator, confidence formula, deliberation routing, document
verification, and policy primitives. The integration tests use the mock
provider, so the run is deterministic and offline.

## Run the eval suite (regenerate `docs/EVAL_REPORT.md`)

```bash
make eval
```

Or directly:

```bash
cd backend && python -m eval.runner
```

Produces a Rich-formatted summary in the terminal and rewrites
[`docs/EVAL_REPORT.md`](docs/EVAL_REPORT.md) with per-case decision,
expected-vs-actual, full trace, and `system_must` checklist.

## Layout

```
multi_agent_claims_pipeline/
├── README.md                        # this file
├── assignment.md                    # untouched (Plum-provided)
├── policy_terms.json                # untouched (Plum-provided, loaded at runtime)
├── test_cases.json                  # untouched (Plum-provided, drives the eval suite)
├── sample_documents_guide.md        # untouched (Plum-provided, drives extraction prompts)
├── backend/                         # FastAPI + LangGraph pipeline
├── frontend/                        # Next.js 15 + Tailwind UI
├── docs/                            # ARCHITECTURE, COMPONENT_CONTRACTS, EVAL_REPORT
├── docker-compose.yml
└── Makefile
```

## What goes through the pipeline

1. `POST /api/claims` → submit a claim (member, category, date, amount, documents).
2. **IntakeAgent** validates the member and policy.
3. **DocumentVerificationAgent** runs three checks (type, quality,
   patient match). Failures stop here with a specific user message —
   "Wrong type", "Re-upload F004", "Documents belong to different
   patients" — never a generic error (TC001–TC003).
4. **ExtractionAgent** uses Gemini (or the mock provider) to extract
   structured fields per document, then runs the deterministic
   extraction validator (bill total reconciliation, date sanity, doctor
   registration regex, hallucination flags). Token / cost / latency are
   recorded per call.
5. **(deliberation) `re_verification`** triggers when extraction
   confidence is low or a validation issue is flagged; capped at 1
   cycle.
6. **ContradictionDetectionAgent** checks patient-name, date,
   hospital-name, amount-reconciliation, and diagnosis-treatment
   compatibility across documents.
7. **PolicyAdjudicationAgent** runs the JSON rule engine
   (`policy_rules.json`): coverage, exclusions, waiting periods,
   pre-auth, prescription-required.
8. **FinancialCalculationAgent** does the deterministic six-step math:
   line-item exclusions → per-claim cap → network discount → co-pay → YTD cap.
9. **FraudDetectionAgent** scans for same-day, monthly, and high-value signals.
10. **(deliberation) `policy_reconsider`** triggers when fraud raised
    signals but no policy rule failed; capped at 1 cycle.
11. **DecisionSynthesizerAgent** routes to one of `APPROVED / PARTIAL /
    REJECTED / MANUAL_REVIEW / NEEDS_CLARIFICATION /
    ESCALATED_MEDICAL_REVIEW / FRAUD_INVESTIGATION` depending on
    findings + contradictions + signals + degradation; computes the
    formal confidence number; builds the explanation tree; attaches the
    cost rollup.

Every step writes a structured `TraceStep` so reviewers can reconstruct
the decision in the UI.

## Environment variables

| Var | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | `mock` or `gemini` |
| `GEMINI_API_KEY` | — | Required if `LLM_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp` | Override Gemini model |
| `DATABASE_URL` | `sqlite+aiosqlite:///./claims.db` | Any SQLAlchemy async URL |
| `POLICY_TERMS_PATH` | repo root `policy_terms.json` | Override policy file |
| `POLICY_RULES_PATH` | repo root `policy_rules.json` | Override declarative rules + confidence weights |
| `TEST_CASES_PATH` | repo root `test_cases.json` | Override eval cases |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated |
| `LOG_LEVEL` | `INFO` | Backend log level |

## Deployment

The Dockerfiles and `docker-compose.yml` are production-shaped:

- **Backend** image (`backend/Dockerfile`) is a slim Python 3.11
  container running uvicorn on port 8000. Deploy to Render / Fly.io /
  Cloud Run by mounting `policy_terms.json` and `test_cases.json` into
  `/policy/` and pointing `POLICY_TERMS_PATH` and `TEST_CASES_PATH` at
  them. SQLite mounts to `/data` by default; switch to Postgres by
  setting `DATABASE_URL`.
- **Frontend** image (`frontend/Dockerfile`) is a Next.js standalone
  build. Deploy to Vercel by pointing the project at `frontend/` and
  setting `NEXT_PUBLIC_API_URL` to the backend's deployed URL.
