"""Rule evaluation engine for rule_resolution_node.

Rules are plain data (a JSON-safe condition DSL), not Python callables --
they need to travel from Postgres JSONB through a caller into this DB-free
graph, and a hospital-authored rule must never be able to run arbitrary
code. DEFAULT_GLOBAL_RULES is the fallback used when no external rule set
is supplied (e.g. in graph-only tests); a real caller fetches active rules
from Postgres and passes them in instead.

Resolution is two-tier: any matching hospital-scoped rule wins outright
(highest `priority` among matches), and the global rule set is only
consulted when no hospital rule matched.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

RuleSource = Literal["global", "hospital"]

HIGH_VALUE_THRESHOLD = Decimal("10000")
LOW_VALUE_AUTO_APPROVE_THRESHOLD = Decimal("500")
KNOWN_CLAIM_TYPES = ("medical", "dental", "vision", "pharmacy", "other")


@dataclass(frozen=True)
class Rule:
    code: str
    rule_type: str
    action: str  # "auto_approve" | "auto_deny" | "flag_fraud" | "require_review"
    condition: dict[str, Any]
    reason: str
    priority: int = 0
    source: RuleSource = "global"
    rule_id: str | None = None
    version: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def rule_from_dict(data: dict[str, Any]) -> Rule:
    """Builds a Rule from the JSON-safe shape a caller (e.g. the API's
    pipeline_service, reading from Postgres) passes across the graph
    boundary as `rule_definitions`.
    """
    return Rule(
        code=data["rule_code"],
        rule_type=data["rule_type"],
        action=data["action"],
        condition=data["condition"],
        reason=data.get("reason", ""),
        priority=data.get("priority", 0),
        source=data.get("source", "global"),
        rule_id=data.get("rule_id"),
        version=data.get("version"),
        effective_from=_parse_dt(data.get("effective_from")),
        effective_to=_parse_dt(data.get("effective_to")),
    )


# --- Facts -----------------------------------------------------------

def _billed_amount(extracted: dict[str, Any]) -> Decimal | None:
    raw = extracted.get("billed_amount")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _is_out_of_network(context: list[dict[str, Any]]) -> bool:
    return any(item.get("network_status") == "out_of_network" for item in context)


def _is_billed_amount_outlier(context: list[dict[str, Any]]) -> bool:
    return any(item.get("source") == "amount_anomaly" and item.get("is_outlier") for item in context)


def build_facts(extracted_data: dict[str, Any], retrieved_context: list[dict[str, Any]]) -> dict[str, Any]:
    """Flat, JSON-safe view of a claim that conditions are evaluated
    against. Anything a rule needs to test belongs here.
    """
    return {
        "claim_type": extracted_data.get("claim_type"),
        "billed_amount": _billed_amount(extracted_data),
        "has_documents": bool(extracted_data.get("documents")),
        "out_of_network": _is_out_of_network(retrieved_context),
        "billed_amount_is_outlier": _is_billed_amount_outlier(retrieved_context),
        "diagnosis_codes": extracted_data.get("diagnosis_codes") or [],
        "procedure_codes": extracted_data.get("procedure_codes") or [],
        "provider_id": extracted_data.get("provider_id"),
    }


# --- Condition DSL -----------------------------------------------------
# Leaf: {"field": str, "op": str, "value": Any}
# Combinators: {"all": [condition, ...]} | {"any": [...]} | {"not": condition}

def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "is_empty":
        return not actual
    if op == "is_not_empty":
        return bool(actual)
    if actual is None:
        return False
    if isinstance(actual, Decimal) and not isinstance(expected, Decimal):
        expected = Decimal(str(expected))
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "contains":
        return expected in actual
    raise ValueError(f"Unknown rule condition operator: {op!r}")


def evaluate_condition(condition: dict[str, Any], facts: dict[str, Any]) -> bool:
    if "all" in condition:
        return all(evaluate_condition(c, facts) for c in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(c, facts) for c in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], facts)
    return _compare(facts.get(condition["field"]), condition["op"], condition.get("value"))


def _is_effective(rule: Rule, as_of: datetime) -> bool:
    if rule.effective_from and as_of < rule.effective_from:
        return False
    if rule.effective_to and as_of >= rule.effective_to:
        return False
    return True


# --- Default global rules ---------------------------------------------
# Seed/fallback rule set, used only when a caller doesn't supply
# `rule_definitions` (e.g. graph-only tests). A real deployment's global
# rules live in Postgres like everything else.

DEFAULT_GLOBAL_RULES: tuple[Rule, ...] = (
    Rule(
        code="ELG-INVALID-CLAIM-TYPE",
        rule_type="eligibility",
        action="auto_deny",
        condition={"field": "claim_type", "op": "not_in", "value": list(KNOWN_CLAIM_TYPES)},
        reason="Claim type is not a recognized coverage category.",
        priority=100,
    ),
    Rule(
        code="FRAUD-OUT-OF-NETWORK",
        rule_type="fraud_detection",
        action="flag_fraud",
        condition={
            "all": [
                {"field": "out_of_network", "op": "eq", "value": True},
                {"field": "billed_amount", "op": "gt", "value": float(LOW_VALUE_AUTO_APPROVE_THRESHOLD)},
            ]
        },
        reason="Out-of-network provider combined with a claim above the low-value threshold.",
        priority=80,
    ),
    Rule(
        code="FRAUD-STATISTICAL-OUTLIER",
        rule_type="fraud_detection",
        action="flag_fraud",
        condition={"field": "billed_amount_is_outlier", "op": "eq", "value": True},
        reason="Billed amount is a statistical outlier compared to similar historical claims.",
        priority=90,
    ),
    Rule(
        code="ELG-MISSING-DOCS",
        rule_type="eligibility",
        action="require_review",
        condition={"field": "has_documents", "op": "eq", "value": False},
        reason="No supporting documents attached to the claim.",
        priority=60,
    ),
    Rule(
        code="COMPLIANCE-HIGH-VALUE",
        rule_type="compliance",
        action="require_review",
        condition={"field": "billed_amount", "op": "gt", "value": float(HIGH_VALUE_THRESHOLD)},
        reason=f"Billed amount exceeds the {HIGH_VALUE_THRESHOLD} auto-processing ceiling.",
        priority=60,
    ),
    Rule(
        code="AUTO-APPROVE-LOW-VALUE",
        rule_type="auto_approval",
        action="auto_approve",
        condition={
            "all": [
                {"field": "has_documents", "op": "eq", "value": True},
                {"field": "out_of_network", "op": "eq", "value": False},
                {"field": "billed_amount", "op": "lte", "value": float(LOW_VALUE_AUTO_APPROVE_THRESHOLD)},
            ]
        },
        reason=f"Billed amount at or below {LOW_VALUE_AUTO_APPROVE_THRESHOLD}, in-network, fully documented.",
        priority=40,
    ),
)


def evaluate_rules(
    extracted_data: dict[str, Any],
    retrieved_context: list[dict[str, Any]],
    rules: tuple[Rule, ...] = DEFAULT_GLOBAL_RULES,
    *,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Evaluates every rule against the claim. Expired/future rules are
    still reported (matched=False) for audit transparency, but can never
    match -- their effective window is checked before their condition is.
    """
    as_of = as_of or datetime.now(timezone.utc)
    facts = build_facts(extracted_data, retrieved_context)

    results: list[dict[str, Any]] = []
    for rule in rules:
        matched = _is_effective(rule, as_of) and evaluate_condition(rule.condition, facts)
        results.append(
            {
                "rule_id": rule.rule_id,
                "rule_code": rule.code,
                "rule_type": rule.rule_type,
                "version": rule.version,
                "source": rule.source,
                "priority": rule.priority,
                "matched": matched,
                "action": rule.action if matched else None,
                "reason": rule.reason if matched else "",
            }
        )
    return results


def resolve_verdict(rule_results: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    """Hospital rules take full precedence: if any matched, the
    highest-priority one wins outright and global rules are never
    consulted. Only when no hospital rule matched do global rules apply.
    Returns (action, winning_rule) -- winning_rule is None on no_match.
    """

    def _best(source: str) -> dict[str, Any] | None:
        matches = [r for r in rule_results if r["matched"] and r["source"] == source]
        return max(matches, key=lambda r: r["priority"]) if matches else None

    winner = _best("hospital") or _best("global")
    if winner is None:
        return "no_match", None
    return winner["action"], winner
