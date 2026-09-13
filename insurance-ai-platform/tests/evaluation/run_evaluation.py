"""Runs the fixed synthetic claim dataset through the real compiled graph
and compares the AI's output against adjuster ground truth.

This is a product-safety gate, not a unit test: the question it answers is
"if we let the system act on its own recommendation for these claims,
would it ever disagree with a human adjuster?" Any claim the guardrails
would let through automatically (decision_path == "auto_process") MUST
match ground truth exactly -- that mismatch is what the harness treats as
a release blocker. Claims that require a human either way are scored for
informational agreement only: a mismatch there means the AI would have
been wrong if we widened auto-processing to cover it, which is exactly
the signal this harness exists to surface before that widening happens.

Run directly for a human-readable report:
    PYTHONPATH=<repo>/insurance-ai-platform/backend python3 \\
        insurance-ai-platform/tests/evaluation/run_evaluation.py

Or import `run_dataset()` / `evaluate_case()` from a pytest test (see
test_evaluation_safety_gate.py) for an automated pass/fail gate.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from graph.build_graph import build_graph

DATASET_PATH = Path(__file__).parent / "fixtures" / "synthetic_claims.json"

Decision = Literal["approved", "denied", "pending"]

# How a recommendation_type maps onto the same approved/denied/pending
# vocabulary ground truth is expressed in. "escalate" carries no opinion
# (the rules engine had nothing to say) and is scored separately as "no
# recommendation" rather than forced into one of these three.
RECOMMENDATION_TO_DECISION: dict[str, Decision] = {
    "approve": "approved",
    "deny": "denied",
    "flag_for_fraud": "denied",
    "request_more_info": "pending",
}


@dataclass
class CaseResult:
    case_id: str
    description: str
    ground_truth_decision: Decision
    ground_truth_rationale: str
    decision_path: str  # "auto_process" | "human_review"
    ai_recommendation_type: str | None
    ai_recommendation_decision: Decision | None  # None if "escalate"/unmapped
    final_decision: str  # what the claim record ends up with after this run
    auto_processed_correctly: bool | None  # None if not auto-processed at all
    recommendation_agrees_with_ground_truth: bool | None  # None if no opinion


def load_dataset() -> list[dict[str, Any]]:
    return json.loads(DATASET_PATH.read_text())


def evaluate_case(case: dict[str, Any]) -> CaseResult:
    graph = build_graph()
    thread_id = f"eval-{case['case_id']}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: dict[str, Any] = {
        "claim_id": case["raw_input"]["claim_id"],
        "raw_input": case["raw_input"],
    }
    if "rule_definitions" in case:
        initial_state["rule_definitions"] = case["rule_definitions"]

    result = graph.invoke(initial_state, config=config)

    # `reasoning_output` is already in state before human_review_node ever
    # runs, so there's no need to resume a paused claim just to read the
    # AI's recommendation -- only decision_path and final_decision (which
    # only exist for the auto-processed path) depend on a human's input.
    is_paused = "__interrupt__" in result
    reasoning_output = result.get("reasoning_output") or {}
    final_outcome = result.get("final_outcome") or {}

    recommendation_type = reasoning_output.get("recommendation_type")
    recommendation_decision = RECOMMENDATION_TO_DECISION.get(recommendation_type) if recommendation_type else None

    decision_path = "human_review" if is_paused else final_outcome.get("decision_path", "unknown")
    ground_truth = case["ground_truth_decision"]

    auto_processed_correctly = None
    if decision_path == "auto_process":
        auto_processed_correctly = final_outcome.get("final_decision") == ground_truth

    agrees = None
    if recommendation_decision is not None:
        agrees = recommendation_decision == ground_truth

    return CaseResult(
        case_id=case["case_id"],
        description=case["description"],
        ground_truth_decision=ground_truth,
        ground_truth_rationale=case["ground_truth_rationale"],
        decision_path=decision_path,
        ai_recommendation_type=recommendation_type,
        ai_recommendation_decision=recommendation_decision,
        final_decision=final_outcome.get("final_decision", "pending_human_review"),
        auto_processed_correctly=auto_processed_correctly,
        recommendation_agrees_with_ground_truth=agrees,
    )


def run_dataset() -> list[CaseResult]:
    return [evaluate_case(case) for case in load_dataset()]


def print_report(results: list[CaseResult]) -> None:
    auto_processed = [r for r in results if r.auto_processed_correctly is not None]
    auto_processed_wrong = [r for r in auto_processed if not r.auto_processed_correctly]

    scored = [r for r in results if r.recommendation_agrees_with_ground_truth is not None]
    agreements = [r for r in scored if r.recommendation_agrees_with_ground_truth]

    print(f"\n{'=' * 72}\nSynthetic claim evaluation: {len(results)} case(s)\n{'=' * 72}")
    for r in results:
        marker = "AUTO" if r.decision_path == "auto_process" else "HUMAN"
        safety = ""
        if r.auto_processed_correctly is False:
            safety = "  <-- SAFETY VIOLATION: auto-processed against ground truth"
        agree = ""
        if r.recommendation_agrees_with_ground_truth is False:
            agree = "  (AI disagreed with ground truth -- informational)"
        print(
            f"[{marker:5}] {r.case_id:32} ground_truth={r.ground_truth_decision:9} "
            f"ai={r.ai_recommendation_type or '-':18}{safety}{agree}"
        )

    print(f"\n{'-' * 72}")
    print(f"Auto-processed cases:        {len(auto_processed)}")
    print(f"  Safety violations:         {len(auto_processed_wrong)}  (must be 0)")
    print(f"Recommendation agreement:    {len(agreements)}/{len(scored)} scored cases " f"(escalate cases excluded)")
    print(f"{'-' * 72}\n")


if __name__ == "__main__":
    print_report(run_dataset())
