"""Deterministic guardrails gating automatic claim processing.

For the first release, automatic processing is intentionally narrow: only
a small allowlist of low-value, non-adverse claim categories may ever
bypass human review. Every check below runs independently and ALL must
pass -- there is no override, and a single failure routes the claim to a
human. Checks all run to completion (not short-circuited) so the audit
trail shows the full picture, not just the first thing that failed.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

# --- Configuration -----------------------------------------------------
# Deliberately conservative for the first release. Widening any of these
# is a product/compliance decision, not a code change to make lightly.

# Only these claim types may ever be auto-processed.
AUTO_ELIGIBLE_CLAIM_TYPES: frozenset[str] = frozenset({"dental", "vision"})

# Independent of (and stricter than) the rules engine's own auto-approve
# threshold in rules.py -- that threshold decides what to *recommend*,
# this one decides what's safe to *act on automatically*.
AUTO_PROCESS_AMOUNT_CAP = Decimal("300")

# Per-claim-type confidence bar. A claim type with no entry here falls
# back to a bar high enough that it will not realistically be met --
# newly auto-eligible claim types must be added deliberately, not
# silently inherit a lenient default.
MIN_CONFIDENCE_BY_CLAIM_TYPE: dict[str, float] = {
    "dental": 0.85,
    "vision": 0.85,
}
DEFAULT_MIN_CONFIDENCE = 0.99

# ICD-10 chapter V (mental, behavioral and neurodevelopmental disorders)
# codes start with "F". Any matching diagnosis code routes to a human.
BEHAVIORAL_HEALTH_DIAGNOSIS_PREFIX = "F"

# Rule types that block automatic processing if matched at all --
# regardless of which verdict won priority in rule_resolution_node.
BLOCKING_RULE_TYPES: frozenset[str] = frozenset({"fraud_detection", "compliance"})

# Only a clean approval is eligible for automatic processing. Denials and
# any other non-approval outcome are adverse determinations and always
# require a human.
NON_ADVERSE_RECOMMENDATION_TYPES: frozenset[str] = frozenset({"approve"})


@dataclass(frozen=True)
class GuardrailCheck:
    name: str
    passed: bool
    reason: str  # populated only when passed is False


def _check(name: str, passed: bool, failure_reason: str) -> GuardrailCheck:
    return GuardrailCheck(name=name, passed=passed, reason="" if passed else failure_reason)


def _billed_amount(extracted_data: dict[str, Any]) -> Decimal | None:
    raw = extracted_data.get("billed_amount")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _is_behavioral_health(extracted_data: dict[str, Any]) -> bool:
    diagnosis_codes = extracted_data.get("diagnosis_codes") or []
    return any(str(code).upper().startswith(BEHAVIORAL_HEALTH_DIAGNOSIS_PREFIX) for code in diagnosis_codes)


def _has_blocking_rule_match(applicable_rules: list[dict[str, Any]]) -> bool:
    return any(r.get("matched") and r.get("rule_type") in BLOCKING_RULE_TYPES for r in applicable_rules)


def _hospital_forces_review(retrieved_context: list[dict[str, Any]]) -> bool:
    return any(item.get("forces_human_review") for item in retrieved_context)


def evaluate_guardrails(
    *,
    extracted_data: dict[str, Any],
    applicable_rules: list[dict[str, Any]],
    retrieved_context: list[dict[str, Any]],
    recommendation_type: str,
    confidence_score: float,
) -> list[GuardrailCheck]:
    """Runs all 8 guardrail checks and returns every result."""
    claim_type = extracted_data.get("claim_type")
    billed_amount = _billed_amount(extracted_data)
    min_confidence = MIN_CONFIDENCE_BY_CLAIM_TYPE.get(claim_type, DEFAULT_MIN_CONFIDENCE)

    return [
        _check(
            "claim_type_auto_eligible",
            claim_type in AUTO_ELIGIBLE_CLAIM_TYPES,
            f"Claim type '{claim_type}' is not in the auto-eligible allowlist "
            f"{sorted(AUTO_ELIGIBLE_CLAIM_TYPES)}.",
        ),
        _check(
            "amount_below_cap",
            billed_amount is not None and billed_amount < AUTO_PROCESS_AMOUNT_CAP,
            f"Billed amount ({billed_amount}) is not below the "
            f"{AUTO_PROCESS_AMOUNT_CAP} automatic-processing cap.",
        ),
        _check(
            "confidence_meets_threshold",
            confidence_score >= min_confidence,
            f"Confidence {confidence_score} is below the {min_confidence} bar for '{claim_type}' claims.",
        ),
        _check(
            "not_behavioral_health",
            not _is_behavioral_health(extracted_data),
            "Claim has a behavioral/mental health diagnosis code and always requires human review.",
        ),
        _check(
            "not_adverse_determination",
            recommendation_type in NON_ADVERSE_RECOMMENDATION_TYPES,
            f"Recommendation '{recommendation_type}' is an adverse or non-approval outcome "
            "and requires human review.",
        ),
        _check(
            "required_documents_present",
            bool(extracted_data.get("documents")),
            "Required supporting documents are missing.",
        ),
        _check(
            "no_fraud_or_policy_conflict",
            not _has_blocking_rule_match(applicable_rules),
            "A fraud-detection or compliance rule matched this claim.",
        ),
        _check(
            "no_hospital_override",
            not _hospital_forces_review(retrieved_context),
            "A hospital-specific rule forces human review for this provider.",
        ),
    ]
