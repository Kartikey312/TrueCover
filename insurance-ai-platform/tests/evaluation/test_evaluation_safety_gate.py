"""The release gate this whole harness exists for: run the fixed synthetic
dataset and fail loudly if the system would ever auto-process a claim
against adjuster ground truth. Run with:

    PYTHONPATH=<repo>/insurance-ai-platform/backend python3 -m pytest \\
        insurance-ai-platform/tests/evaluation -v

(PYTHONPATH must include backend/ so `graph` resolves -- same convention
as backend/graph/tests.)
"""

import pytest

from run_evaluation import load_dataset, evaluate_case


CASES = load_dataset()
CASE_IDS = [case["case_id"] for case in CASES]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_auto_processed_claims_never_disagree_with_ground_truth(case):
    result = evaluate_case(case)

    if result.auto_processed_correctly is False:
        pytest.fail(
            f"{case['case_id']}: auto-processed as '{result.final_decision}' but ground truth is "
            f"'{result.ground_truth_decision}' ({case['ground_truth_rationale']}). "
            "This is a release blocker -- do not widen auto-processing eligibility while this fails."
        )


def test_dataset_has_at_least_one_case_per_decision_path():
    results = [evaluate_case(case) for case in CASES]
    paths = {r.decision_path for r in results}
    assert "auto_process" in paths, "Dataset should include at least one case that actually auto-processes."
    assert "human_review" in paths, "Dataset should include at least one case that requires a human."


def test_overall_recommendation_agreement_rate_is_reported():
    """Not a pass/fail gate (recommendation disagreement on an
    escalated claim is safe, just informational) -- this only ensures the
    metric itself is computable, so a CI job can log it over time as the
    dataset grows before anyone considers widening auto-processing.
    """
    results = [evaluate_case(case) for case in CASES]
    scored = [r for r in results if r.recommendation_agrees_with_ground_truth is not None]
    assert scored, "No cases produced a scorable recommendation -- dataset or mapping is broken."
    agreement_rate = sum(r.recommendation_agrees_with_ground_truth for r in scored) / len(scored)
    assert 0.0 <= agreement_rate <= 1.0
