-- Hospital-scoped rules: a rule with provider_id set applies only to that
-- hospital and takes precedence over global rules (provider_id IS NULL)
-- during resolution. priority breaks ties among rules in the same scope.
-- approved_by denormalizes the compliance sign-off onto the rule itself
-- for fast lookup; the full approval history still lives in
-- rule_approvals.
ALTER TABLE rules ADD COLUMN provider_id UUID REFERENCES providers_hospitals(provider_id) ON DELETE CASCADE;
ALTER TABLE rules ADD COLUMN priority INTEGER NOT NULL DEFAULT 0;
ALTER TABLE rules ADD COLUMN approved_by UUID REFERENCES users(user_id) ON DELETE SET NULL;

CREATE INDEX idx_rules_provider_id ON rules(provider_id);
