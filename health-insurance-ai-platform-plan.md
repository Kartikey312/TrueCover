# Health Insurance AI Platform — Full Build Plan

**Modeled on**: CareMate (patient/doctor app) + Healthcare_memory_agent (Qdrant-backed AI core), adapted for a health insurer's claims, coverage Q&A, and underwriting.

---

## 1. What we're building

Three user-facing surfaces sharing one AI orchestration layer:

- **Member portal** — multilingual chat for coverage questions, claim filing (photo/voice/text upload), claim status tracking
- **Agent/adjuster app** — claim review queue, fraud flags, pre-packaged AI reasoning + citations per claim
- **Underwriter workbench** — risk scoring on new applications (phase 3)

The AI orchestration layer is a **LangGraph** state machine, not a single LLM call — it extracts data, retrieves grounding facts from Qdrant, reasons, checks guardrails (including hospital-specific rule overrides), and routes to either automatic processing or a human, with every step written to an audit log.

---

## 2. System architecture

```
Front-end apps                AI orchestration              Data layer
──────────────                ─────────────────              ──────────
Member portal      ─┐                                    ┌── Qdrant vector DB
Agent/adjuster app  ─┼──►  LangGraph pipeline (RAG +  ──►─┼── Claims & policy systems
Underwriter app     ─┘      agents + guardrails)          └── Compliance & audit log
```

- **Frontend**: React + TypeScript, Tailwind, Recharts
- **Backend**: FastAPI, LangGraph for orchestration
- **Vector DB**: Qdrant (cloud-hosted, not in-memory, for durability)
- **LLM**: Claude for reasoning/chat; a lightweight rules layer for deterministic fraud checks
- **Rule store**: Postgres for hospital override rules (structured, not semantic — see §5)
- **Checkpointing**: SqliteSaver in dev, PostgresSaver/managed checkpoint store in production

---

## 3. Qdrant collections

| Collection | Embeds | Purpose |
|---|---|---|
| `member_conversations` | text (384-dim) | Semantic memory of chat/support history |
| `claim_documents` | text + CLIP image (384+512) | Bills, EOBs, itemized statements, injury photos |
| `provider_notes_audio` | Wav2Vec2 (768) | Call transcripts, adjuster call analysis |
| `similar_claims` | text (384) | Fraud pattern matching, precedent lookup |
| `policy_knowledge` | text (384) | RAG over plan docs, exclusions, state mandates |
| `underwriting_signals` | text (384) | Risk factor embeddings for applicants |

---

## 4. LangGraph pipeline

### 4.1 State schema

```python
from typing import TypedDict, Literal, Optional

class ClaimState(TypedDict):
    member_id: str
    raw_input: dict            # text, image refs, audio refs, channel

    extracted: dict            # procedure codes, amounts, provider, hospital_id, dates

    policy_context: list       # policy_knowledge matches
    similar_claims: list       # similar_claims matches

    effective_rule: dict       # resolved global/hospital rule (see §5)

    recommendation: dict       # {decision, confidence, reasoning, citations}

    route: Literal["auto", "human"]
    guardrail_reason: str

    adjuster_decision: Optional[dict]
    final_decision: dict
    audit_trail: list          # append-only log of every node's output
```

### 4.2 Nodes

```python
def extraction_node(state: ClaimState) -> ClaimState:
    extracted = run_extraction(state["raw_input"])   # OCR / CLIP / text parsing
    return {"extracted": extracted,
            "audit_trail": state["audit_trail"] + [{"step": "extraction", "output": extracted}]}

def retrieval_node(state: ClaimState) -> ClaimState:
    policy = qdrant_search("policy_knowledge", state["extracted"], member_id=state["member_id"])
    similar = qdrant_search("similar_claims", state["extracted"])
    return {"policy_context": policy, "similar_claims": similar,
            "audit_trail": state["audit_trail"] + [{"step": "retrieval",
                "policy_hits": [p["id"] for p in policy],
                "similar_hits": [s["id"] for s in similar]}]}

def rule_resolution_node(state: ClaimState) -> ClaimState:
    hospital_id = state["extracted"].get("hospital_id")
    global_rules = fetch_rules(scope="global")
    hospital_rules = fetch_rules(scope="hospital", hospital_id=hospital_id) if hospital_id else []

    matching = [r for r in hospital_rules if rule_condition_matches(r["condition"], state["extracted"])]
    applicable = sorted(matching, key=lambda r: -r["priority"])
    effective_rule = applicable[0] if applicable else global_rules[0]

    return {"effective_rule": effective_rule,
            "audit_trail": state["audit_trail"] + [{"step": "rule_resolution",
                "hospital_id": hospital_id, "rule_applied": effective_rule["rule_id"],
                "source": "hospital_override" if applicable else "global_default"}]}

def reasoning_node(state: ClaimState) -> ClaimState:
    rec = call_claude_reasoning(state["extracted"], state["policy_context"], state["similar_claims"])
    return {"recommendation": rec,
            "audit_trail": state["audit_trail"] + [{"step": "reasoning", "output": rec}]}

def guardrail_node(state: ClaimState) -> ClaimState:
    rule = state["effective_rule"]
    rec = state["recommendation"]

    if rule["always_human"]:
        route, reason = "human", f"Hospital rule {rule['rule_id']} forces human review"
    elif rec["confidence"] >= rule["auto_approve_threshold"]:
        route, reason = "auto", f"Confidence {rec['confidence']} meets {rule['rule_id']} threshold"
    else:
        route, reason = "human", "Below applicable confidence threshold"

    return {"route": route, "guardrail_reason": reason,
            "audit_trail": state["audit_trail"] + [{"step": "guardrail", "route": route,
                "reason": reason, "rule_used": rule["rule_id"]}]}

def auto_process_node(state: ClaimState) -> ClaimState:
    final = finalize(state["recommendation"])
    return {"final_decision": final,
            "audit_trail": state["audit_trail"] + [{"step": "auto_process", "output": final}]}

def human_review_node(state: ClaimState) -> ClaimState:
    # graph pauses BEFORE this node (interrupt_before); adjuster_decision is
    # already in state by the time this runs, injected via update_state()
    final = state["adjuster_decision"]
    return {"final_decision": final,
            "audit_trail": state["audit_trail"] + [{"step": "human_review", "output": final}]}

def audit_log_node(state: ClaimState) -> ClaimState:
    write_to_compliance_log(state["audit_trail"], state["final_decision"])
    return state

def route_after_guardrail(state: ClaimState) -> Literal["auto_process_node", "human_review_node"]:
    return "auto_process_node" if state["route"] == "auto" else "human_review_node"
```

### 4.3 Graph wiring

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

graph = StateGraph(ClaimState)
for name, fn in [
    ("extraction_node", extraction_node),
    ("retrieval_node", retrieval_node),
    ("rule_resolution_node", rule_resolution_node),
    ("reasoning_node", reasoning_node),
    ("guardrail_node", guardrail_node),
    ("auto_process_node", auto_process_node),
    ("human_review_node", human_review_node),
    ("audit_log_node", audit_log_node),
]:
    graph.add_node(name, fn)

graph.set_entry_point("extraction_node")
graph.add_edge("extraction_node", "retrieval_node")
graph.add_edge("retrieval_node", "rule_resolution_node")
graph.add_edge("rule_resolution_node", "reasoning_node")
graph.add_edge("reasoning_node", "guardrail_node")
graph.add_conditional_edges("guardrail_node", route_after_guardrail, {
    "auto_process_node": "auto_process_node",
    "human_review_node": "human_review_node",
})
graph.add_edge("auto_process_node", "audit_log_node")
graph.add_edge("human_review_node", "audit_log_node")
graph.add_edge("audit_log_node", END)

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")  # PostgresSaver in production
app = graph.compile(checkpointer=checkpointer, interrupt_before=["human_review_node"])
```

### 4.4 Human-in-the-loop pause/resume

```python
config = {"configurable": {"thread_id": "claim-H-88450"}}

result = app.invoke(initial_state, config)   # pauses at guardrail → human route

# ... adjuster reviews in the UI ...

app.update_state(config, {"adjuster_decision": {
    "decision": "approved", "amount": 2400, "adjuster_id": "A-102", "note": "Docs verified"}})

final_result = app.invoke(None, config)      # resumes exactly where it paused
```

`get_state_history(config)` on that `thread_id` gives the complete, replayable audit trail for that claim — this is the compliance record.

---

## 5. Hospital rule override system

### 5.1 Rule schema (Postgres, not Qdrant — structured business logic)

```python
class ClaimRule(TypedDict):
    rule_id: str
    scope: Literal["global", "hospital"]
    hospital_id: Optional[str]
    condition: dict                   # e.g. {"cpt_code_in": [...], "amount_lt": 5000}
    auto_approve_threshold: float
    always_human: bool
    priority: int                     # higher wins within same scope on conflict
    effective_from: str
    effective_to: Optional[str]       # force periodic re-review — no permanent overrides
    created_by: str
    approved_by: Optional[str]        # rule changes require compliance sign-off
```

### 5.2 Example rows

```json
[
  {"rule_id": "global-default", "scope": "global", "hospital_id": null,
   "condition": {}, "auto_approve_threshold": 0.85, "always_human": false, "priority": 0},

  {"rule_id": "hosp-A-fasttrack", "scope": "hospital", "hospital_id": "H-A-001",
   "condition": {"cpt_code_in": ["99284", "99285"], "amount_lt": 5000},
   "auto_approve_threshold": 0.70, "always_human": false, "priority": 10,
   "approved_by": "compliance-lead-J.Rao"},

  {"rule_id": "hosp-B-flagged", "scope": "hospital", "hospital_id": "H-B-004",
   "condition": {}, "auto_approve_threshold": 1.01, "always_human": true, "priority": 20,
   "approved_by": "fraud-team-lead"}
]
```

### 5.3 Resolution logic
Highest-priority hospital rule whose `condition` matches the claim wins; otherwise fall back to the global default. See `rule_resolution_node` in §4.2.

### 5.4 Governance rules (non-negotiable)
- No self-service overrides — every rule change needs `approved_by` from compliance/fraud, never just an engineer pushing config
- Every hospital override gets an `effective_to` date — forces periodic re-review instead of a "trusted forever" status
- `rule_resolution_node` logs which exact rule fired and its source (`global_default` vs `hospital_override`) — answers "why did this hospital get approved faster" instantly

---

## 6. Guardrail rules (baseline, before any hospital override)

| Condition | Route |
|---|---|
| Confidence ≥ threshold AND claim type auto-eligible AND amount below cap | `auto` |
| Behavioral/mental health claim | `human` (always) |
| Any adverse determination (denial) | `human` (always) |
| Confidence below applicable threshold | `human` |
| Hospital rule sets `always_human: true` | `human` |

Start conservative everywhere; loosen only after a full quarter of auditing auto-processed decisions against adjuster ground truth.

---

## 7. Multi-agent extension (phase 3+)

Split `reasoning_node` into a supervisor routing to specialized subgraphs once the linear pipeline is proven:

- `coverage_agent` — member-facing plan/benefits Q&A (policy RAG only, no claims decisioning)
- `fraud_agent` — scores claims against `similar_claims`, flags anomalies
- `underwriting_agent` — separate graph entirely, different state schema and guardrails

Start with simple `if/else` routing; move to an LLM-based supervisor only if routing logic gets genuinely ambiguous.

---

## 8. Repo structure

```
insurance-ai-platform/
├── frontend/                  # React + TS: member portal, agent app, underwriter workbench
├── backend/
│   ├── graph/
│   │   ├── state.py           # ClaimState + other TypedDicts
│   │   ├── nodes.py           # node functions
│   │   ├── rules.py           # rule_resolution_node, rule_condition_matches
│   │   └── build_graph.py     # StateGraph wiring
│   ├── qdrant/
│   │   ├── collections.py
│   │   └── search.py
│   ├── api/                   # FastAPI routes: /claims, /chat, /adjuster/queue, /admin/rules
│   └── compliance/
│       └── audit_log.py
├── tests/
└── docs/
    └── ARCHITECTURE.md
```

---

## 9. Phased roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
| 1 | Claims intake + fraud graph, Qdrant collections live, guardrails conservative | Every claim produces a full audit trail; adjusters review AI recommendations in-app |
| 2 | Member chatbot (`coverage_agent`), conversation memory | Members get coverage answers grounded in their actual plan |
| 3 | Hospital rule override system live, thresholds loosened based on Phase 1 audit data | Auto-process rate increases without accuracy loss vs. adjuster ground truth |
| 4 | Underwriting workbench, multi-agent supervisor | Agents compose without duplicated logic |

---

## 10. Open decisions before building starts

- Checkpointer backend for production: self-hosted Postgres vs. managed LangGraph platform checkpoint store
- Where PHI can legally live — HIPAA-eligible vector DB infra (BAA-covered cloud) vs. tokenized references instead of raw PHI in embeddings
- Which claim types are `auto`-eligible at launch (start narrow: routine, low-dollar, high-frequency procedure codes only)
- Who owns rule approval workflow — compliance team tooling for reviewing/approving hospital overrides before they go live
