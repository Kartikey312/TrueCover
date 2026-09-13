-- Without this, a fresh deployment has zero active rules in Postgres, and
-- every claim resolves to no_match: pipeline_service always passes
-- `rule_definitions` (even an empty list) once a claim's provider is
-- looked up, and rule_resolution_node correctly treats an empty *supplied*
-- list as "no rules configured" rather than falling back to
-- backend/graph/rules.py's DEFAULT_GLOBAL_RULES (that fallback is only for
-- when the key is absent entirely, i.e. graph-only tests). These rows
-- mirror DEFAULT_GLOBAL_RULES exactly so real deployments start with the
-- same baseline behavior.
--
-- These are seeded pre-active by the deployment migration itself, not
-- through the /rules compliance-approval workflow -- that workflow gates
-- runtime CHANGES to the rule set, not the initial baseline configuration
-- shipped with the system (analogous to any other seed data). Any
-- subsequent change to these rules -- editing, deprecating, replacing --
-- must go through that workflow like any other rule.
INSERT INTO rules (rule_code, rule_name, description, rule_type, rule_definition, status, priority)
VALUES
    (
        'ELG-INVALID-CLAIM-TYPE',
        'Unrecognized claim type',
        'System default global rule seeded at deployment.',
        'eligibility',
        '{
            "condition": {"field": "claim_type", "op": "not_in", "value": ["medical", "dental", "vision", "pharmacy", "other"]},
            "action": "auto_deny",
            "reason": "Claim type is not a recognized coverage category."
        }'::jsonb,
        'active',
        100
    ),
    (
        'FRAUD-OUT-OF-NETWORK',
        'Out-of-network provider on a non-trivial claim',
        'System default global rule seeded at deployment.',
        'fraud_detection',
        '{
            "condition": {"all": [
                {"field": "out_of_network", "op": "eq", "value": true},
                {"field": "billed_amount", "op": "gt", "value": 500}
            ]},
            "action": "flag_fraud",
            "reason": "Out-of-network provider combined with a claim above the low-value threshold."
        }'::jsonb,
        'active',
        80
    ),
    (
        'ELG-MISSING-DOCS',
        'Missing supporting documentation',
        'System default global rule seeded at deployment.',
        'eligibility',
        '{
            "condition": {"field": "has_documents", "op": "eq", "value": false},
            "action": "require_review",
            "reason": "No supporting documents attached to the claim."
        }'::jsonb,
        'active',
        60
    ),
    (
        'COMPLIANCE-HIGH-VALUE',
        'High-value claim requires manual review',
        'System default global rule seeded at deployment.',
        'compliance',
        '{
            "condition": {"field": "billed_amount", "op": "gt", "value": 10000},
            "action": "require_review",
            "reason": "Billed amount exceeds the 10000 auto-processing ceiling."
        }'::jsonb,
        'active',
        60
    ),
    (
        'AUTO-APPROVE-LOW-VALUE',
        'Low-value in-network claim with documentation',
        'System default global rule seeded at deployment.',
        'auto_approval',
        '{
            "condition": {"all": [
                {"field": "has_documents", "op": "eq", "value": true},
                {"field": "out_of_network", "op": "eq", "value": false},
                {"field": "billed_amount", "op": "lte", "value": 500}
            ]},
            "action": "auto_approve",
            "reason": "Billed amount at or below 500, in-network, fully documented."
        }'::jsonb,
        'active',
        40
    );
