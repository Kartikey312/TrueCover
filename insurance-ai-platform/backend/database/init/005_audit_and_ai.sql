-- Append-only audit trail. Rows are never updated or deleted by the
-- application; corrections are new events, not edits.
CREATE TABLE audit_events (
    event_id    BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id   UUID NOT NULL,
    event_type  VARCHAR(100) NOT NULL,
    actor_type  actor_type NOT NULL,
    actor_id    UUID REFERENCES users(user_id) ON DELETE SET NULL,
    old_value   JSONB,
    new_value   JSONB,
    description TEXT,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_events_entity ON audit_events(entity_type, entity_id);
CREATE INDEX idx_audit_events_created_at ON audit_events(created_at);
CREATE INDEX idx_audit_events_actor_id ON audit_events(actor_id);

CREATE TABLE ai_recommendations (
    recommendation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id              UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    graph_thread_id       VARCHAR(255),
    recommendation_type   ai_recommendation_type NOT NULL,
    confidence_score      NUMERIC(5, 4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    reasoning             TEXT,
    -- References to supporting rule_ids, qdrant_point_ids, document_ids, etc.
    -- consulted to produce this recommendation. Kept as JSONB rather than
    -- normalized join tables since the evidence shape varies by model/run.
    supporting_evidence   JSONB,
    model_name            VARCHAR(150) NOT NULL,
    status                ai_recommendation_status NOT NULL DEFAULT 'pending_review',
    reviewed_by           UUID REFERENCES users(user_id) ON DELETE SET NULL,
    reviewed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_recommendations_claim_id ON ai_recommendations(claim_id);
CREATE INDEX idx_ai_recommendations_status ON ai_recommendations(status);
CREATE INDEX idx_ai_recommendations_graph_thread_id ON ai_recommendations(graph_thread_id);
