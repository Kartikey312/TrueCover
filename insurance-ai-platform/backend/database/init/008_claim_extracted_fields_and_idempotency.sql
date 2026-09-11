-- Procedure/diagnosis codes were only ever held in the AI graph's
-- in-memory extracted_data; they belong on the claim record itself so the
-- adjuster review packet can be built from Postgres alone.
ALTER TABLE claims ADD COLUMN procedure_codes JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE claims ADD COLUMN diagnosis_codes JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Idempotency protection for POST /claims/{id}/decision: a request replayed
-- with the same idempotency_key returns the original result instead of
-- being reprocessed. A key reused with different parameters is rejected.
CREATE TABLE claim_decision_requests (
    idempotency_key VARCHAR(100) PRIMARY KEY,
    claim_id        UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    adjuster_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    final_decision  final_decision_status NOT NULL,
    approved_amount NUMERIC(12, 2),
    reason          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_claim_decision_requests_claim_id ON claim_decision_requests(claim_id);
