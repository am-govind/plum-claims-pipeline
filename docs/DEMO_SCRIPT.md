# Demo Script (8–12 minutes)

A scene-by-scene script for recording the assignment demo. The recording
itself is performed by the human submitter — this script keeps the take
within the 8–12 min budget and ensures the three required things are
covered.

## Setup before recording

```bash
# Terminal 1 — backend
cd backend && source ../.venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev

# Terminal 3 — pre-staged for the eval CLI demo
cd backend && source ../.venv/bin/activate
```

Open in browser tabs in this order:
1. `http://localhost:3000/` (landing)
2. `http://localhost:3000/submit` (claim form)
3. `http://localhost:3000/eval` (eval matrix)
4. The repo in your editor on `backend/app/application/pipeline.py`

## Script

### 0:00 – 0:45 — Frame the problem

> "Plum processes 75,000 claims a year. Today it's manual: someone reads the
> documents, checks them against the policy, and writes a decision. The
> goal is to automate that — reliably, explainably, and resiliently.
> What I built is a multi-agent pipeline that does that for the 12
> reference cases in `test_cases.json`, with a fully auditable trace."

Show the landing page; click through to `/submit`.

### 0:45 – 3:30 — Demo 1: claim stopped early due to a document problem

(TC001-style.)

On `/submit`:
- Member: EMP001 (Rajesh Kumar)
- Category: CONSULTATION
- Treatment date: 2024-11-01
- Claimed amount: 1500
- Documents: leave both as PRESCRIPTION (the default), patient name "Rajesh Kumar" on both.

Submit. Land on `/claims/{id}`.

> "Notice the system never reaches the LLM, never extracts anything,
> never makes a claim decision. It stopped at document verification —
> it saw that we uploaded two prescriptions but a CONSULTATION claim
> needs a prescription _and_ a hospital bill. The user-facing message
> names exactly what's wrong and what's missing. That's the 'no generic
> errors' bar from the assignment."

Click into the trace timeline:
- Show the `intake` step PASSED.
- Show the `document_verification` step EARLY_STOP, expand the JSON to
  show `uploaded_types`, `required_types`, `missing_types`.

### 3:30 – 7:00 — Demo 2: clean end-to-end approval with full trace

Back to `/submit`. Resubmit TC010-style:
- Member: EMP010 (Deepak Shah)
- Category: CONSULTATION
- Date: 2024-11-03
- Claimed: 4500
- Hospital: Apollo Hospitals
- YTD: 8000
- Doc 1: PRESCRIPTION, patient "Deepak Shah", diagnosis "Acute Bronchitis", doctor TN/56789/2013.
- Doc 2: HOSPITAL_BILL, patient "Deepak Shah", hospital "Apollo Hospitals", total 4500.

Submit. On the result page:

> "Approved ₹3,240 of ₹4,500. The breakdown is the math the assignment
> calls out in TC010 — apply the network discount _before_ the co-pay,
> not after. ₹4,500 → 20% off because Apollo is in-network → ₹3,600 →
> 10% co-pay → ₹3,240. We pass that as a unit test in the policy module
> as well."

Walk through the trace timeline:
- intake (passed) → document verification (passed) → extraction (mock provider, both docs)
  → policy adjudication (5 findings, all passed) → financial calculation
  (full breakdown) → fraud detection (no signals) → decision synthesizer.

Expand the financial calculation step's `breakdown` JSON to show every
intermediate amount.

### 7:00 – 9:30 — Demo 3: the eval matrix

Open `/eval`, click "Run eval".

> "12 cases, 12 passed. Each row is one case from `test_cases.json`. I
> can click any row to see the full trace, the user-facing message, and
> the system_must checklist."

Click TC011 (Component Failure — Graceful Degradation):
> "TC011 is the resilience case. We deliberately raise an exception in
> the fraud agent. The orchestrator catches it, marks the claim degraded,
> drops the confidence by 0.25, adds a 'manual review recommended' note —
> and still produces an APPROVED decision with the rest of the pipeline
> intact. No 500 error."

### 9:30 – 10:30 — Deliberation cycle in action

Click TC009 (Fraud Signal — Multiple Same-Day Claims) on the eval page.

> "TC009 is where the multi-agent design earns its keep. The fraud
> detector raises a same-day-claim signal, but every policy rule
> passes. Instead of just flagging it and moving on, the graph routes
> the claim to a `policy_reconsider` node — a deliberation cycle. You
> can see it on the trace as its own step. The cycle has a hard cap of
> one iteration so the loop is always guaranteed to terminate. The
> claim ends up in MANUAL_REVIEW with the fraud signals included in
> the user message, and the trace shows exactly why."

Open the decision card's "How was this confidence calculated?" expander.

> "And here's the formal confidence number — `Σ wᵢ·Cᵢ − α·contradiction
> − β·degraded`. Every agent's contribution to the final 91% is
> visible. There's no magic accumulator anymore."

### 10:30 – 11:00 — One technical decision I'm proud of

> "The piece I'm proudest of is the JSON rule engine plus the explanation
> tree. Policy logic used to be Python code; now every rule is a row in
> `policy_rules.json` with a tiny custom DSL — `matches_diagnosis`,
> `days_since_join_lt`, `${policy.path}` references. I can edit that
> file, re-run `make eval`, and see the effect immediately. And every
> firing rule produces a `DecisionNode` in the explanation tree the UI
> renders, with click-through evidence linking back to the source
> document field that triggered it. That's the audit trail that lets a
> claims ops team explain any rejection, with no engineer in the loop."

### 11:00 – 12:00 — One thing I'd change with more time

> "What I'd change: the extraction agent. Today Gemini does both OCR and
> structured extraction in one call, which is convenient but couples
> two different failure modes. With more time I'd add a dedicated OCR
> pre-step (Tesseract or a cheap fine-tuned model) that produces clean
> text first, then a much smaller LLM call to structure it. That would
> let us cache OCR output by document hash, retry just the structuring
> step on failures, and run a smaller model on most documents — bringing
> per-claim cost down by ~5x while improving accuracy on handwritten
> Indian prescriptions. The cost tracker on the decision card already
> shows tokens and USD per claim, so we can measure the savings the day
> we ship that change."

Wrap up.
