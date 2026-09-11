CREATE TABLE rules (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code       VARCHAR(100) NOT NULL,
    rule_name       VARCHAR(200) NOT NULL,
    description     TEXT,
    rule_type       rule_type NOT NULL,
    -- Condition/action tree evaluated by the rules engine.
    rule_definition JSONB NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    status          rule_status NOT NULL DEFAULT 'draft',
    created_by      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    effective_from  TIMESTAMPTZ,
    effective_to    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (rule_code, version),
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from)
);

CREATE INDEX idx_rules_status ON rules(status);
CREATE INDEX idx_rules_rule_type ON rules(rule_type);
CREATE INDEX idx_rules_definition_gin ON rules USING GIN (rule_definition);

-- rule_approvals below ties to a specific (rule_id, version) pair, so that
-- pair must be unique before it can be referenced as a composite FK.
ALTER TABLE rules ADD CONSTRAINT uq_rules_id_version UNIQUE (rule_id, version);

CREATE TABLE rule_approvals (
    approval_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID NOT NULL REFERENCES rules(rule_id) ON DELETE CASCADE,
    rule_version    INTEGER NOT NULL,
    approver_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    approval_status approval_status NOT NULL DEFAULT 'pending',
    comments        TEXT,
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (rule_id, rule_version) REFERENCES rules(rule_id, version)
);

CREATE INDEX idx_rule_approvals_rule_id ON rule_approvals(rule_id);
CREATE INDEX idx_rule_approvals_approver_id ON rule_approvals(approver_id);
CREATE INDEX idx_rule_approvals_status ON rule_approvals(approval_status);
