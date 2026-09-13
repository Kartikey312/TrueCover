# TrueCover — Architecture, Flow, and Interview Guide

An AI-assisted health insurance claims platform: claims are submitted,
run through a deterministic LangGraph pipeline that extracts data,
retrieves policy context, applies business/hospital rules, reasons about
a recommendation, and gates automatic processing behind conservative
guardrails — pausing for a human adjuster whenever it isn't confident,
the claim type isn't cleared for automation, or the decision would be
adverse. Every step is audited.

This document has three parts:
1. [System architecture](#1-system-architecture) — the five services and how they relate
2. [End-to-end flow](#2-end-to-end-claim-flow) — what actually happens to a claim, step by step
3. [Design decisions](#3-key-design-decisions--rationale) and an [interview Q&A](#4-interview-questions--answers) for defending them

---

## 1. System architecture

```
insurance-ai-platform/
├── frontend/          React + TypeScript adjuster console (Vite, Tailwind, React Query)
├── backend/
│   ├── api/           FastAPI — HTTP surface, Postgres access, orchestrates the graph
│   ├── graph/          LangGraph pipeline — pure, DB-free claim-processing logic
│   ├── qdrant/         Policy document ingestion + retrieval (RAG for citations)
│   ├── database/       Postgres schema (numbered SQL migrations)
│   └── compliance/      (reserved — not yet built)
├── tests/
│   └── evaluation/      Synthetic-claim ground-truth safety gate
└── docs/
```

### Why split `graph` from `api`

`backend/graph` has **zero database or network I/O**. Every node is a
plain function `(state: dict) -> dict`. This is the single most
consequential architectural choice in the project:

- It can be unit tested with plain Python dicts — no Postgres, no
  mocking, no fixtures. 109 tests run in under a second.
- It can be safely re-run: the same input always produces the same
  output (the "AI recommendation vs ground truth" evaluation harness in
  `tests/evaluation/` depends on this).
- It's swappable. `retrieval_node` is a hardcoded stub standing in for
  Qdrant; `rule_resolution_node` uses a hardcoded `DEFAULT_GLOBAL_RULES`
  fallback standing in for Postgres-sourced rules. Neither node's
  contract changes when the real backing store is plugged in — only
  what data the caller (`backend/api`) hands it at invocation time.

`backend/api` is where all the I/O lives: it reads/writes Postgres via
SQLAlchemy, owns the LangGraph checkpointer (`AsyncPostgresSaver`, so a
paused review survives an API restart), and is the only service that
imports `backend/graph` directly (via a shared `PYTHONPATH`/Docker
`COPY`, not a package dependency — see `backend/api/Dockerfile`).

### The database is the single source of truth

Every "smart" subsystem is explicitly **not** the source of truth for
business data:

- Qdrant holds vector embeddings for policy citation retrieval, but a
  claim's status, decision, and history all live in Postgres.
- The LangGraph checkpoint (`checkpoints` table, managed entirely by the
  `langgraph-checkpoint-postgres` library) holds *execution state* for
  resuming a paused run — it is never read to render anything a human
  sees. The adjuster review packet (`GET /claims/{id}/review`) is built
  **entirely from Postgres** (`ai_recommendations`, `audit_events`,
  `claims`), not from the graph checkpoint.

---

## 2. End-to-end claim flow

### 2.1 Intake

```
POST /claims                         create the claim row (Postgres)
POST /claims/{id}/documents          attach files, repeatable
POST /claims/{id}/submit             kick off AI processing
```

Claim creation only requires `member_id`, `policy_id`, `claim_type`,
`date_of_service` — `procedure_codes`, `diagnosis_codes`, and
`billed_amount` are optional and can instead come from an uploaded
document's text (Phase 2 intake, see [2.2](#22-text-and-pdf-intake)).
This split exists because `/submit` can't run meaningfully before
documents are attached — running it inside `POST /claims` itself would
mean every claim starts with zero documents and instantly fails the
`required_documents_present` guardrail.

### 2.2 Text and PDF intake

When a document is uploaded (`backend/api/app/routers/claims.py` →
`claims_service.add_document`), if it's a PDF or plain text file,
`storage_service.extract_text()` (`pypdf` for PDFs) pulls its text into
`claim_documents.ocr_extracted_text`. At submit time,
`pipeline_service._build_raw_input()` concatenates every document's
extracted text into `raw_input["document_text"]`.

Inside the graph, `extraction_node` calls
`document_parser.extract_fields_from_text()` — a **deterministic regex
parser**, not OCR or an LLM call — that reads labeled lines
(`Claim Type:`, `Total Billed:`, `Procedure Codes:`, and known
synonyms) and fills in whatever structured fields are still missing.
An explicit field on the claim always wins over a parsed one; the audit
trail records exactly which fields, if any, came from a document
(`fields_from_document`). Scanned/image-only documents (needing real
OCR) are explicitly out of scope until this text path is proven — that
was a deliberate phasing decision, not an oversight.

### 2.3 The graph pipeline

`POST /claims/{id}/submit` → `pipeline_service.submit_claim_for_review()`
invokes the compiled LangGraph (`backend/graph/build_graph.py`):

```
extraction_node
      │  validates/normalizes raw_input (+ document text merge)
      │  routes straight to human_review_node if required fields are missing
      ▼
retrieval_node
      │  hardcoded stand-in for Qdrant: coverage-policy blurb,
      │  provider network status, hospital-override flags
      ▼
rule_resolution_node
      │  evaluates active rules (hospital-scoped rules fully override
      │  global rules when they match; highest `priority` wins within
      │  a tier); records exactly which rule won and its source
      ▼
reasoning_node
      │  maps the rule verdict to a recommendation_type + confidence
      │  (deterministic lookup table today — a real model slots in
      │  later without changing the node's contract)
      ▼
guardrail_node
      │  8 independent checks gate AUTOMATIC processing (see 3.3)
      ▼
   ┌──┴───────────────────────┐
   │                          │
auto_process_node      human_review_node
   │  (only "approve",        │  interrupt() pauses the graph here --
   │   all 8 checks passed)   │  LangGraph persists state to Postgres
   │                          │  and execution stops until resumed
   ▼                          ▼
        audit_log_node → END
```

Every node appends one entry to `audit_trail` (accumulated via a
LangGraph reducer). `pipeline_service` persists that trail into
Postgres' `audit_events` table, plus writes an `ai_recommendations` row
capturing the recommendation, confidence, reasoning, and the full
`supporting_evidence` (extracted fields, policy citations, guardrail
check results, matched rules) that produced it.

### 2.4 Human review, pause, and resume

If `guardrail_node` doesn't clear the claim for automation,
`human_review_node` calls LangGraph's `interrupt()`. This is a real
pause, not a status flag: the graph's execution genuinely stops, and its
state is durably checkpointed in Postgres via `AsyncPostgresSaver`
(`backend/api/app/graph_runtime.py`) — verified to survive a full
process restart, since the graph runtime is reconstructed from
Postgres alone at API startup.

```
GET /claims/{id}/review              adjuster sees:
                                        - extracted fields
                                        - policy citations (frozen at
                                          pause time, not re-queried live)
                                        - similar claims (same member +
                                          claim type, live Postgres query)
                                        - recommendation + confidence
                                        - guardrail reasoning (all 8 checks)
                                        - fraud indicators (matched
                                          fraud/compliance rules)
                                        - full audit history

POST /claims/{id}/decision           adjuster approves/denies; resumes
                                        the paused graph via
                                        Command(resume=...); new audit
                                        events append after the pre-pause
                                        prefix -- nothing is re-persisted

POST /claims/{id}/request-info       marks status='pending_documents',
                                        leaves the graph paused (no
                                        member portal exists yet to
                                        receive this -- it's a
                                        queue-visibility signal only)
```

A crucial invariant, enforced in `guardrails.py`: **denials can never be
automatic.** `not_adverse_determination` only passes for
`recommendation_type == "approve"` — a deny, a fraud flag, or an
escalation always requires a human, regardless of confidence.

### 2.5 Idempotency

`POST /claims/{id}/decision` requires a client-generated
`idempotency_key`. `claim_decision_requests` records
`(key, claim_id, decision, amount, reason)`:

- Same key, same parameters → returns the cached claim state, no
  reprocessing (a page refresh or network retry is safe).
- Same key, different parameters → `409` (a real conflict, not silently
  overwritten).
- A brand-new key against an already-decided claim → `409` (a claim can
  only ever be decided once).

This sits on top of LangGraph's own idempotency: resuming an
already-completed thread returns its cached result rather than
re-executing `human_review_node`, verified directly in
`backend/graph/tests/test_build_graph.py`.

### 2.6 Hospital rules and the compliance gate

Rules are data, not code — `rules.py`'s condition DSL is a small,
sandboxed interpreter (`{"all": [...]}` / `{"any": [...]}` /
`{"field", "op", "value"}` leaves) specifically so a hospital-submitted
rule can never execute arbitrary code. A rule can be scoped to one
hospital (`provider_id` set) or global (`NULL`); at resolution time, any
matching hospital rule **fully overrides** the global rule set.

Governance (`backend/api/app/services/rules_service.py`):

```
POST /rules                                    draft
POST /rules/{id}/versions/{v}/submit           draft -> pending_approval
POST /rules/{id}/versions/{v}/approvals        compliance_officer approves/rejects
                                                (403 if the approver isn't compliance)
POST /rules/{id}/versions/{v}/activate         pending_approval -> active
                                                (403 unless a genuine compliance
                                                approval exists for this exact version --
                                                checked regardless of who calls activate)
```

Activating a new version automatically deprecates whichever version was
previously active for that `rule_code`.

---

## 3. Key design decisions & rationale

### 3.1 Why LangGraph specifically (not a hand-rolled state machine)

The pause/resume requirement is the deciding factor. A claim that needs
a human might sit for hours or days — that's not something you model as
a synchronous function call. LangGraph's `interrupt()` +
`Command(resume=...)` + a durable checkpointer gives pause/resume as a
first-class primitive, including surviving process restarts, without
hand-rolling a state-serialization format.

### 3.2 Why the rules engine is declarative data, not Python

Two independent reasons converge on the same answer:
1. **Security**: hospital users (non-engineers) can author rules. A
   Python callable would mean executing arbitrary hospital-submitted
   code — a real code-injection vector. The DSL only supports a fixed,
   small set of comparison operators.
2. **Persistence**: rules need to live in Postgres (for the governance
   workflow, versioning, and audit trail) and cross the graph's
   DB-free boundary as plain, JSON-safe data.

### 3.3 Guardrails are independent of rules — by design

`guardrails.py`'s 8 checks (claim-type eligibility, amount cap,
per-type confidence threshold, behavioral-health exclusion,
non-adverse-determination, required documents, no fraud/policy
conflict, no hospital override) are a **second, independent** gate on
top of whatever the rules engine recommends. A hospital rule can change
what the AI *recommends* (e.g. raise a per-hospital auto-approve
threshold), but it cannot bypass guardrails — verified directly in
`test_hospital_rules.py::test_active_hospital_rule_changes_claim_resolution`,
where a hospital rule flips the recommendation to "approve" but the
claim still lands with a human because `claim_type` isn't in the
guardrails' auto-eligible allowlist. This is deliberate defense in
depth: one bad rule should never be able to unilaterally widen
automatic processing.

For the first release, the auto-eligible allowlist is intentionally
narrow (`dental`, `vision` only, capped at $300) — "route almost
everything to a human" was an explicit requirement, not a limitation to
apologize for.

### 3.4 Why Qdrant is retrieval, never source of truth

`backend/qdrant` embeds and searches policy documents for citations
(`policy_knowledge` collection). It is filtered by plan/state/effective
date, and every retrieved chunk carries its citation (source document,
page, section) bundled with the text — there's no code path that
returns chunk text without it, which is what lets the review packet
show "why" alongside "what." But claim status, decisions, and history
never live in Qdrant; if it were unavailable, the claims system would
degrade (no citations) rather than break.

### 3.5 Testing strategy: three tiers, different jobs

| Tier | What it proves | Speed |
|---|---|---|
| `backend/graph/tests/` (109 tests) | Node logic is correct in isolation — no DB needed | <1s |
| `backend/api/tests/` (36 tests) | The API, graph, and Postgres agree with each other — real disposable DB, real checkpointer | ~15s |
| `tests/evaluation/` (17 tests) | The AI's recommendations don't diverge from adjuster ground truth on a fixed synthetic dataset | <1s |

The third tier is a **product safety gate**, not a unit test: any claim
the guardrails would let through automatically must match ground truth
*exactly* — a hard failure, not a warning. Claims routed to a human are
scored for informational agreement only, since a human catching an AI
mistake is safe, just not efficient. This is the artifact you'd point
to before ever widening the auto-eligible allowlist.

Building the `backend/api` suite caught a real regression: once
hospital rules shipped, `pipeline_service` always passed
`rule_definitions` from Postgres (even an empty list), but no global
rules were ever seeded there — so every real claim silently resolved to
`no_match`. Fixed by seeding the same rules `DEFAULT_GLOBAL_RULES`
encodes as pre-approved baseline configuration
(`010_seed_default_global_rules.sql`). This is a concrete example of why
integration tests against a real database matter: the graph's own unit
tests couldn't have caught it, since they never touch Postgres.

---

## 4. Interview questions & answers

**Q: Walk me through what happens when a claim is submitted.**
A: `POST /claims` creates the row. Documents get attached separately.
`POST /claims/{id}/submit` builds a `raw_input` dict from the claim +
its documents' extracted text, then invokes the compiled LangGraph with
a `thread_id` derived from the claim id. The graph extracts/normalizes
fields, retrieves policy context, resolves the applicable rule
(hospital-scoped first, falling back to global), generates a
recommendation, and runs it through 8 guardrail checks. If all 8 pass
*and* the recommendation is "approve," it auto-processes; otherwise it
pauses via `interrupt()` for a human. Every step writes an audit event.

**Q: How does the system guarantee a claim is never decided twice?**
A: Two layers. `POST /claims/{id}/decision` requires a client-generated
idempotency key; a replay with the same key and parameters returns the
cached result, a conflicting replay is rejected with 409, and a
brand-new decision attempt on an already-decided claim is also
rejected. Underneath that, LangGraph's own checkpoint semantics mean
resuming an already-completed thread returns its cached final state
rather than re-executing anything, even if the API-level guard were
somehow bypassed.

**Q: Why not just store rules as Python functions if you already trust
your engineers?**
A: Because you don't only trust engineers — the whole point of the
hospital-rules feature is letting hospital users (or their assigned
account managers) propose rules, gated by compliance approval before
activation. A Python callable stored in a database and later `eval`'d
is a code-injection vector. The declarative condition DSL is a closed,
auditable set of operators; there's no way to make it do anything other
than compare claim facts.

**Q: What stops an engineer from activating an unapproved rule?**
A: The activation endpoint doesn't check the *caller's* role — it
checks whether a `rule_approvals` row exists for that exact rule
version with `approval_status='approved'` from a user whose role is
`compliance_officer`, via a join. No such row, no activation, regardless
of who's calling. The approval-recording endpoint has the same
independent check (rejects an "approved" decision from a
non-compliance user), so there's no way to fabricate a qualifying
approval row either.

**Q: How do you keep an AI recommendation from silently becoming an
automatic decision it shouldn't?**
A: Guardrails are deliberately decoupled from the rules engine that
produces the recommendation — a rule can change *what's recommended*,
never *whether it's safe to auto-act on it*. The
`not_adverse_determination` check specifically means denials and fraud
flags can never be automatic, no matter how confident the model is.

**Q: The graph is described as "pure" — what does that actually
buy you?**
A: No I/O means every node is testable with plain dicts, no mocking.
It also means the same claim state always produces the same output,
which is the property the synthetic-evaluation safety gate depends on
— you can't compare "AI recommendation vs. ground truth" meaningfully
if the AI's answer depends on database state that changes between runs.

**Q: What's the actual mechanism behind pause/resume — is the claim
just marked "pending" in a column somewhere?**
A: No — `human_review_node` calls LangGraph's `interrupt()`, which
raises a control-flow signal that the graph runtime catches, persisting
the *entire execution state* (not just a status flag) into Postgres via
`AsyncPostgresSaver`. Resuming later with `Command(resume=decision)`
replays the node from the top (everything before `interrupt()` re-runs,
which is why that part must be side-effect-free) and the call returns
with the injected decision. Verified to survive a full disconnect: a
fresh graph instance with a fresh Postgres connection can resume a
thread paused by a completely different instance.

**Q: Why does the review packet not just read from the graph's
checkpoint?**
A: Because the checkpoint is an internal execution-resumption mechanism,
not meant to be a queryable data model — reading it for display would
make the UI dependent on the graph's internal state shape. Instead,
everything shown to the adjuster is captured into normal Postgres rows
(`ai_recommendations`, `audit_events`) at the moment the graph pauses,
and the review endpoint reads only from Postgres. The checkpoint is
touched exactly once more: to resume.

**Q: How would you extend this to real OCR for scanned documents?**
A: The seam is already there. `extraction_node` accepts
`raw_input["document_text"]` — plain text, however it was obtained.
Today that text comes from `pypdf` (PDFs with embedded text) or a raw
`.txt` file. Swapping in real OCR means adding an image-to-text step at
the API layer (e.g., a vision model or an OCR service) that populates
the same `document_text` field; `extraction_node`, the regex parser, and
everything downstream doesn't need to change at all.

**Q: What would you change if this needed to scale to real production
volume?**
A: A few things stand out: the retrieval and rules-fallback stubs need
their real backends fully wired in (Qdrant retrieval is built but not
yet connected to `retrieval_node`); authentication is currently a
stand-in (an "acting as" picker, not real login) and would need to
become real sessions before this could run with real PHI; and the
evaluation dataset is 15 synthetic cases — before ever widening the
auto-eligible allowlist beyond dental/vision, that dataset should grow
using real historical adjuster decisions as ground truth, not just
hand-written synthetic ones.
