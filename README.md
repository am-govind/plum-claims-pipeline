# Plum Claims Pipeline

> A multi-agent health-insurance claims processing system — every decision is auditable,
> every component is replaceable, and every failure is graceful.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1f6feb.svg)](https://github.com/langchain-ai/langgraph)
[![Tests](https://img.shields.io/badge/tests-106%20passing-brightgreen.svg)](backend/tests)
[![Eval](https://img.shields.io/badge/eval-12%2F12-brightgreen.svg)](docs/EVAL_REPORT.md)

A FastAPI + LangGraph backend orchestrates **eight specialised agents** and **two
deliberation cycles** over a single immutable `ClaimState`. A Next.js 15
frontend renders the decision, a clickable explanation tree, the per-step
trace, and a formal weighted-confidence breakdown. The system runs fully
offline against a deterministic mock LLM provider, and swaps in Google
Gemini for real document upload with a single environment variable.

> The full assignment brief lives in [`assignment.md`](assignment.md).
> Read it before the code if you're reviewing this for Plum.

---

## Table of contents

- [Why this design](#why-this-design)
- [Quick start](#quick-start)
- [Local development](#local-development)
- [Pipeline at a glance](#pipeline-at-a-glance)
- [Architecture](#architecture)
- [HTTP API](#http-api)
- [Configuration](#configuration)
- [Tests and evaluation](#tests-and-evaluation)
- [Project layout](#project-layout)
- [Documentation index](#documentation-index)
- [Deployment](#deployment)
- [Known limitations](#known-limitations)

---

## Why this design

| Concern | How it's handled |
| --- | --- |
| **Wrong / unreadable / mismatched documents** | Caught by `DocumentVerificationAgent` before any LLM call. The user gets a specific message naming the file and the action — never a generic error. |
| **Hallucinated extractions** | Every extracted document is passed through a deterministic validator (bill-total reconciliation, date sanity, doctor-registration regex). Failures trigger the `re_verification` deliberation cycle. |
| **Cross-document inconsistencies** | `ContradictionDetectionAgent` checks patient name, dates, hospital name, amount reconciliation, and diagnosis–treatment compatibility across all uploaded documents. |
| **Policy logic in code** | Every rule lives in [`policy_rules.json`](policy_rules.json) and is evaluated by a small custom DSL in [`backend/app/domain/policy/rules.py`](backend/app/domain/policy/rules.py). Adding a rule is a JSON change, not a Python change. |
| **Calculation order ambiguity** | `FinancialCalculationAgent` runs a fixed six-step ledger: line-item exclusions → network discount → co-pay → sub-limit cap → per-claim cap → YTD cap. The ordering is what makes TC010's `₹3,240` come out correct. |
| **Component failures** | Non-critical agent exceptions are caught by the LangGraph wrapper; the trace records the failure, `state.degraded` is set, confidence drops, and the pipeline continues. TC011 exercises this end-to-end. |
| **Explainability** | Every node writes a structured `TraceStep`. The synthesizer assembles a causal `DecisionExplanationTree` from the findings, contradictions, and signals — rendered as a clickable tree in the UI. |
| **Confidence is not a vibe** | Computed by a formal weighted formula in [`backend/app/domain/services/confidence.py`](backend/app/domain/services/confidence.py): `Σ wᵢ · Cᵢ − α · contradictions − β · degraded`, with weights loaded from `policy_rules.json`. |
| **Side effects are decoupled** | Agents publish `DomainEvent`s onto a `ClaimState` buffer; the HTTP layer drains them into an `InMemoryEventBus` after each run. Built-in subscribers: structured logging and a notification stub. |

---

## Quick start

```bash
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| API root | http://localhost:8000 |
| Interactive API docs (Swagger) | http://localhost:8000/docs |
| Health probe | http://localhost:8000/health |

The default `LLM_PROVIDER=mock` makes the whole stack deterministic and
offline — perfect for the eval suite and integration tests. To run the
extraction step against real Gemini for live document uploads:

```bash
export GEMINI_API_KEY=...
export LLM_PROVIDER=gemini
docker compose up --build
```

---

## Local development

Requires **Python 3.11 or 3.12** and **Node 18+**. Either Python version
works against the project; the Dockerfile pins 3.12 for reproducibility.

**Backend**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend** (separate terminal)

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev      # http://localhost:3000
```

> **macOS file-watcher tip.** Next.js's default `fs.watch` can exceed
> macOS's per-process kqueue budget and flood the console with
> `Watchpack Error: EMFILE`. If you see that, start the frontend with
> `WATCHPACK_POLLING=true CHOKIDAR_USEPOLLING=true npm run dev`.

**Convenience targets**

```bash
make install     # backend (editable + dev extras) and frontend deps
make backend     # uvicorn --reload on :8000
make frontend    # next dev on :3000
make test        # pytest
make eval        # regenerate docs/EVAL_REPORT.md
make docker      # docker compose up --build
make clean       # wipe caches and dev DB
```

---

## Pipeline at a glance

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
**deliberation cycles** — they only run when an upstream agent left
evidence that the pipeline should look again. Each is hard-capped at
one iteration.

| Step | Critical? | Calls LLM? | Responsibility |
| --- | :-: | :-: | --- |
| `intake` | yes | no | Member + policy validation, date sanity, early stop on invalid claims. |
| `document_verification` | yes | no | Required document types, readability, patient-name match. Early stop on TC001–TC003. |
| `extraction` | no | yes | Structured `ExtractedDocument` per upload, with confidence and validation issues. |
| `re_verification` (deliberation) | no | yes* | Retries extraction on low-confidence / flagged docs with feedback. *(1× cap)* |
| `contradiction_detection` | no | no | Cross-document checks: names, dates, hospitals, amounts, diagnosis ↔ treatment. |
| `policy_adjudication` | no | no | Evaluates the JSON rule engine: coverage, exclusions, waiting periods, pre-auth. |
| `financial_calculation` | no | no | Six-step ledger to compute approved amount and breakdown. |
| `fraud_detection` | no | no | Same-day claims, monthly volume, high-value signals. |
| `policy_reconsider` (deliberation) | no | no | Recommends manual review when fraud disagrees with a clean policy pass. *(1× cap)* |
| `decision_synthesizer` | yes | no | Picks the final status, primary reason, confidence, explanation tree, cost rollup. |

For per-agent inputs/outputs, events, and failure modes, see
[`AGENTS.md`](AGENTS.md).

---

## Architecture

The backend follows a strict **hexagonal (ports & adapters)** layout
with a one-way dependency rule (inner layers never know about outer
layers):

```
interfaces/   FastAPI routers · request/response models · Depends() providers
    ▼
application/  pipeline · agents · ports/* (abstract interfaces)
    ▼
domain/       ClaimState · PolicyTerms · Decision · events · rule DSL  (pure Python)
    ▲
    │ implements ports
    │
infrastructure/  SQLAlchemy repo · JSON policy loader · Mock/Gemini providers
                 InMemoryEventBus · structlog + notification handlers
```

Every collaborator is **constructor-injected**, wired in exactly one
place — [`backend/app/composition.py`](backend/app/composition.py) — and
exposed to FastAPI via the `Container` on `app.state`. No module-level
singletons, no global `get_settings()`, no `lru_cache`d providers. This
is why the test suite can build its own `Container` per fixture
without monkey-patching.

The LLM is just another port. Two adapters live behind it:

- **`MockProvider`** — deterministic, reads pre-extracted `content` from
  the test fixture. Default; used by the eval suite and all integration
  tests so the run is offline and reproducible.
- **`GeminiProvider`** — vision-capable, calls Google `gemini-2.0-flash-exp`
  over `bytes_b64` from real uploads. Honours the *one Gemini call per
  uploaded document* invariant by short-circuiting when the
  `extract-preview` endpoint already produced an extraction in the
  current session.

For a deeper treatment of the boundaries, deliberation rationale, and
trade-offs considered and rejected, see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/claims` | Submit a claim; runs the full pipeline. Returns claim id + complete `ClaimState`. |
| `GET` | `/api/claims` | List recent claims (summary view). |
| `GET` | `/api/claims/{claim_id}` | Fetch a previously processed claim. |
| `POST` | `/api/claims/extract-preview` | Run only the extraction step on an uploaded document so the `/submit` form can auto-fill fields. Provider failures return `{ok: false, reason, message}` with HTTP 200. |
| `GET` | `/api/members` | Member roster from `policy_terms.json` (powers the UI dropdown). |
| `GET` | `/api/policy` | Policy metadata: categories, document requirements, network hospitals, fraud thresholds. |
| `GET` | `/api/eval/run` | Run all 12 fixtures through the live pipeline and return per-case results. |
| `GET` | `/health` | Liveness probe; also reports the active LLM provider. |

Full request/response shapes are in
[`docs/COMPONENT_CONTRACTS.md`](docs/COMPONENT_CONTRACTS.md).

---

## Configuration

Configuration is loaded by `pydantic-settings` from process env or
`backend/.env`. See [`backend/.env.example`](backend/.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | `mock` or `gemini`. |
| `GEMINI_API_KEY` | — | Required when `LLM_PROVIDER=gemini`. If unset, the factory silently falls back to `mock`. |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp` | Override the Gemini model id. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./claims.db` | Any SQLAlchemy async URL (use Postgres in prod). |
| `POLICY_TERMS_PATH` | repo `policy_terms.json` | Override the policy file. |
| `POLICY_RULES_PATH` | repo `policy_rules.json` | Override the declarative rules + confidence weights. |
| `TEST_CASES_PATH` | repo `test_cases.json` | Override the eval fixture set. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origin list. |
| `LOG_LEVEL` | `INFO` | Backend log level. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | (Frontend) Backend base URL at build time. |
| `NEXT_PUBLIC_DEV_MODE` | `true` | (Frontend) Hides the `/submit` failure-simulation toggle and `/eval` page when set to `false` for production builds. |

---

## Tests and evaluation

### Unit and integration tests

```bash
cd backend && pytest
```

**106 tests** — 12 integration tests (one per `test_cases.json` case),
4 integration tests for the `extract-preview` endpoint, 9 integration
tests for domain-event dispatch, and 81 focused unit tests covering the
rule engine, contradiction detection, extraction validator, confidence
formula, deliberation routing, document verification, decision
precedence, the mock provider, the Gemini content-fallback path, and
each agent in isolation. Integration tests use the mock provider, so
the suite is deterministic and offline.

### Eval report

```bash
make eval
# or:  cd backend && python -m eval.runner
```

Produces a Rich-formatted summary in the terminal and rewrites
[`docs/EVAL_REPORT.md`](docs/EVAL_REPORT.md) with per-case decision,
expected-vs-actual, full trace, `system_must` checklist, latency / token
aggregates, an extraction-confidence histogram, and a rule-coverage
matrix.

**Current status: 12/12 cases pass deterministically.**

---

## Project layout

```
multi_agent_claims_pipeline/
├── README.md                          ← you are here
├── AGENTS.md                          ← per-agent contract + deliberation cycles
├── assignment.md                      ← Plum-provided assignment brief (untouched)
├── policy_terms.json                  ← Plum-provided policy data    (untouched)
├── policy_rules.json                  ← declarative rules + confidence weights
├── test_cases.json                    ← Plum-provided eval fixtures   (untouched)
├── sample_documents_guide.md          ← Plum-provided extraction guidance (untouched)
├── docker-compose.yml
├── Makefile
├── backend/
│   ├── app/
│   │   ├── composition.py             ← the single composition root
│   │   ├── config.py                  ← pydantic-settings
│   │   ├── domain/                    ← pure-Python core (no IO)
│   │   ├── application/               ← agents, pipeline, ports/*
│   │   ├── infrastructure/            ← Gemini/Mock, SQLAlchemy, event bus
│   │   └── interfaces/http/           ← FastAPI routers + DI providers
│   ├── eval/                          ← runner that emits docs/EVAL_REPORT.md
│   └── tests/                         ← unit/ and integration/
├── frontend/                          ← Next.js 15 + Tailwind (App Router)
│   ├── app/{submit,eval,claims,page.tsx}
│   └── components/{ClaimForm,DecisionCard,DecisionTree,TraceTimeline,...}
└── docs/
    ├── ARCHITECTURE.md
    ├── COMPONENT_CONTRACTS.md
    ├── DEMO_SCRIPT.md
    └── EVAL_REPORT.md
```

---

## Documentation index

| Document | What's in it |
| --- | --- |
| [`assignment.md`](assignment.md) | The original Plum problem statement and evaluation criteria. |
| [`AGENTS.md`](AGENTS.md) | Every agent's name, criticality, reads/writes, events, failure mode. The deliberation cycles. The LLM provider port. The event bus. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layering, dependency rules, composition root, deliberation rationale, alternatives considered. |
| [`docs/COMPONENT_CONTRACTS.md`](docs/COMPONENT_CONTRACTS.md) | Per-component input/output/error contracts (precise enough to reimplement any single component without reading its code). |
| [`docs/EVAL_REPORT.md`](docs/EVAL_REPORT.md) | Auto-generated. Per-case decision, expected vs actual, full trace, aggregates. |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | 8–12 minute demo walkthrough used for the technical review. |

---

## Deployment

The Dockerfiles and `docker-compose.yml` are production-shaped:

- **Backend** (`backend/Dockerfile`) — slim Python 3.12 image running
  uvicorn on `:8000`. For Render / Fly.io / Cloud Run, mount
  `policy_terms.json`, `policy_rules.json`, and `test_cases.json` into
  `/policy/`, then point the corresponding `*_PATH` env vars at them.
  Persist `/data` for the SQLite database, or set `DATABASE_URL` to
  Postgres.
- **Frontend** (`frontend/Dockerfile`) — Next.js standalone build. For
  Vercel, point the project at `frontend/` and set `NEXT_PUBLIC_API_URL`
  to the deployed backend's URL.

---

## Known limitations

Honest list, in case the reviewer is curious where to push next:

- **Single-instance state.** The event bus is in-memory; if the API
  scales horizontally, swap `InMemoryEventBus` for a queue-backed
  adapter behind the same port.
- **Rule DSL is intentionally small.** The custom operators in
  `domain/policy/rules.py` cover the assignment's policy surface, not
  every conceivable insurance rule. Open Policy Agent would be the
  natural escape hatch at higher complexity.
- **Gemini-only LLM adapter.** Adding an OpenAI / Anthropic adapter is
  a new file under `infrastructure/llm/` and one branch in
  `factory.build_llm_provider`. The port is provider-agnostic.
- **Confidence is calibrated against the eval set.** The weights in
  `policy_rules.json` were tuned to keep the 12 cases honest; production
  use would want a real calibration dataset.
- **Deliberation caps are conservative.** Both cycles are hard-capped at
  one iteration to bound latency and cost. A production deployment
  could let the budget be policy-driven.

