CREATE TABLE claims (
    claim_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_number            VARCHAR(50) NOT NULL UNIQUE,
    member_id               UUID NOT NULL REFERENCES members(member_id) ON DELETE RESTRICT,
    policy_id               UUID NOT NULL REFERENCES policies(policy_id) ON DELETE RESTRICT,
    provider_id             UUID REFERENCES providers_hospitals(provider_id) ON DELETE SET NULL,
    status                  claim_status NOT NULL DEFAULT 'submitted',
    claim_type              claim_type NOT NULL,
    date_of_service         DATE NOT NULL,
    submitted_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_adjuster_id    UUID REFERENCES users(user_id) ON DELETE SET NULL,
    -- Correlates the claim with its orchestration thread in the AI agent
    -- graph (LangGraph or similar), so a claim's AI workflow can be resumed.
    current_graph_thread_id VARCHAR(255),
    billed_amount           NUMERIC(12, 2) CHECK (billed_amount >= 0),
    approved_amount         NUMERIC(12, 2) CHECK (approved_amount >= 0),
    paid_amount             NUMERIC(12, 2) CHECK (paid_amount >= 0),
    final_decision          final_decision_status NOT NULL DEFAULT 'pending',
    final_decision_reason   TEXT,
    final_decision_at       TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_claims_member_id ON claims(member_id);
CREATE INDEX idx_claims_policy_id ON claims(policy_id);
CREATE INDEX idx_claims_provider_id ON claims(provider_id);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_assigned_adjuster_id ON claims(assigned_adjuster_id);
CREATE INDEX idx_claims_submitted_at ON claims(submitted_at);
CREATE INDEX idx_claims_graph_thread_id ON claims(current_graph_thread_id);

CREATE TABLE claim_documents (
    document_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id            UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    document_type       document_type NOT NULL,
    file_name           VARCHAR(255) NOT NULL,
    storage_path        TEXT NOT NULL,
    mime_type           VARCHAR(100),
    file_size_bytes     BIGINT CHECK (file_size_bytes >= 0),
    ocr_extracted_text  TEXT,
    -- Pointer only: the embedding itself lives in Qdrant. Postgres stays
    -- the source of truth for the document record; Qdrant is not queried
    -- to determine what documents exist.
    qdrant_point_id     VARCHAR(255),
    uploaded_by         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_claim_documents_claim_id ON claim_documents(claim_id);
CREATE INDEX idx_claim_documents_type ON claim_documents(document_type);

CREATE TABLE adjuster_assignments (
    assignment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id            UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    adjuster_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    assigned_by         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    assignment_reason   assignment_reason NOT NULL DEFAULT 'initial',
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    unassigned_at       TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (unassigned_at IS NULL OR unassigned_at >= assigned_at)
);

CREATE INDEX idx_adjuster_assignments_claim_id ON adjuster_assignments(claim_id);
CREATE INDEX idx_adjuster_assignments_adjuster_id ON adjuster_assignments(adjuster_id);
-- Enforce at most one active assignment per claim.
CREATE UNIQUE INDEX uq_adjuster_assignments_active_per_claim
    ON adjuster_assignments(claim_id)
    WHERE is_active;
