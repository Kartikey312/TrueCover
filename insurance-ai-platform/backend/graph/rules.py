"""Deterministic rule set evaluated by rule_resolution_node.

This mirrors the shape of the `rules` Postgres table (rule_code, rule_type,
action, condition) but is hardcoded here as a stand-in for phase 1 of the
graph. Once a DB-backed rules engine exists, DEFAULT_RULES becomes seed
data rather than the only source -- rule_resolution_node's contract
(extracted_data + retrieved_context -> list of RuleResult) does not need
to change.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

RuleAction = str  # "auto_approve" | "auto_deny" | "flag_fraud" | "require_review"

# Higher number wins when multiple rules match the same claim -- a deny
# always overrides a mere review or approve suggestion.
RULE_PRIORITY: dict[RuleAction, int] = {
    "auto_deny": 4,
    "flag_fraud": 3,
    "require_review": 2,
    "auto_approve": 1,
}

HIGH_VALUE_THRESHOLD = Decimal("10000")
LOW_VALUE_AUTO_APPROVE_THRESHOLD = Decimal("500")
KNOWN_CLAIM_TYPES = {"medical", "dental", "vision", "pharmacy", "other"}


@dataclass(frozen=True)
class Rule:
    code: str
    name: str
    rule_type: str
    action: RuleAction
    condition: Callable[[dict[str, Any], list[dict[str, Any]]], bool]
    reason: str


def _billed_amount(extracted: dict[str, Any]) -> Decimal | None:
    raw = extracted.get("billed_amount")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _amount_at_most(extracted: dict[str, Any], threshold: Decimal) -> bool:
    amount = _billed_amount(extracted)
    return amount is not None and amount <= threshold


def _amount_above(extracted: dict[str, Any], threshold: Decimal) -> bool:
    amount = _billed_amount(extracted)
    return amount is not None and amount > threshold


def _is_out_of_network(context: list[dict[str, Any]]) -> bool:
    return any(item.get("network_status") == "out_of_network" for item in context)


def _has_documents(extracted: dict[str, Any]) -> bool:
    return bool(extracted.get("documents"))


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(
        code="ELG-INVALID-CLAIM-TYPE",
        name="Unrecognized claim type",
        rule_type="eligibility",
        action="auto_deny",
        condition=lambda extracted, context: extracted.get("claim_type") not in KNOWN_CLAIM_TYPES,
        reason="Claim type is not a recognized coverage category.",
    ),
    Rule(
        code="ELG-MISSING-DOCS",
        name="Missing supporting documentation",
        rule_type="eligibility",
        action="require_review",
        condition=lambda extracted, context: not _has_documents(extracted),
        reason="No supporting documents attached to the claim.",
    ),
    Rule(
        code="FRAUD-OUT-OF-NETWORK",
        name="Out-of-network provider on a non-trivial claim",
        rule_type="fraud_detection",
        action="flag_fraud",
        condition=lambda extracted, context: (
            _is_out_of_network(context) and _amount_above(extracted, LOW_VALUE_AUTO_APPROVE_THRESHOLD)
        ),
        reason="Out-of-network provider combined with a claim above the low-value threshold.",
    ),
    Rule(
        code="COMPLIANCE-HIGH-VALUE",
        name="High-value claim requires manual review",
        rule_type="compliance",
        action="require_review",
        condition=lambda extracted, context: _amount_above(extracted, HIGH_VALUE_THRESHOLD),
        reason=f"Billed amount exceeds the {HIGH_VALUE_THRESHOLD} auto-processing ceiling.",
    ),
    Rule(
        code="AUTO-APPROVE-LOW-VALUE",
        name="Low-value in-network claim with documentation",
        rule_type="auto_approval",
        action="auto_approve",
        condition=lambda extracted, context: (
            _has_documents(extracted)
            and not _is_out_of_network(context)
            and _amount_at_most(extracted, LOW_VALUE_AUTO_APPROVE_THRESHOLD)
        ),
        reason=f"Billed amount at or below {LOW_VALUE_AUTO_APPROVE_THRESHOLD}, in-network, fully documented.",
    ),
)


def evaluate_rules(
    extracted_data: dict[str, Any],
    retrieved_context: list[dict[str, Any]],
    rules: tuple[Rule, ...] = DEFAULT_RULES,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rule in rules:
        matched = bool(rule.condition(extracted_data, retrieved_context))
        results.append(
            {
                "rule_code": rule.code,
                "rule_type": rule.rule_type,
                "matched": matched,
                "action": rule.action if matched else None,
                "reason": rule.reason if matched else "",
            }
        )
    return results


def resolve_verdict(rule_results: list[dict[str, Any]]) -> str:
    matched_actions = [r["action"] for r in rule_results if r["matched"]]
    if not matched_actions:
        return "no_match"
    return max(matched_actions, key=lambda action: RULE_PRIORITY.get(action, 0))
