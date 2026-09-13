// Mirrors backend/api/app/schemas/*.py. Keep in sync by hand -- there's no
// shared schema generation between the two yet.

export type ClaimStatus =
  | "submitted"
  | "under_review"
  | "pending_documents"
  | "pending_adjuster_review"
  | "approved"
  | "denied"
  | "appealed"
  | "closed"
  | "paid";

export type ClaimType = "medical" | "dental" | "vision" | "pharmacy" | "other";

export type FinalDecisionStatus = "pending" | "approved" | "denied" | "partially_approved";

export type DocumentType =
  | "medical_record"
  | "invoice"
  | "receipt"
  | "id_proof"
  | "discharge_summary"
  | "prescription"
  | "other";

export type AIRecommendationType = "approve" | "deny" | "request_more_info" | "flag_for_fraud" | "escalate";

export type AIRecommendationStatus = "pending_review" | "accepted" | "overridden" | "rejected";

export interface ClaimRead {
  claim_id: string;
  claim_number: string;
  member_id: string;
  policy_id: string;
  provider_id: string | null;
  status: ClaimStatus;
  claim_type: ClaimType;
  date_of_service: string;
  procedure_codes: string[];
  diagnosis_codes: string[];
  submitted_at: string;
  assigned_adjuster_id: string | null;
  current_graph_thread_id: string | null;
  billed_amount: string | null;
  approved_amount: string | null;
  paid_amount: string | null;
  final_decision: FinalDecisionStatus;
  final_decision_reason: string | null;
  final_decision_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdjusterQueueItem {
  claim_id: string;
  claim_number: string;
  member_id: string;
  member_name: string;
  status: ClaimStatus;
  claim_type: ClaimType;
  billed_amount: string | null;
  date_of_service: string;
  submitted_at: string;
  assigned_adjuster_id: string | null;
}

export interface AdjusterRead {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
}

export interface ClaimDocumentRead {
  document_id: string;
  claim_id: string;
  document_type: DocumentType;
  file_name: string;
  storage_path: string;
  mime_type: string | null;
  file_size_bytes: number | null;
  uploaded_by: string | null;
  uploaded_at: string;
}

export interface TimelineEvent {
  event_id: number;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  description: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  created_at: string;
}

export interface AIRecommendationRead {
  recommendation_id: string;
  claim_id: string;
  graph_thread_id: string | null;
  recommendation_type: AIRecommendationType;
  confidence_score: string | null;
  reasoning: string | null;
  supporting_evidence: Record<string, unknown> | null;
  model_name: string;
  status: AIRecommendationStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface GuardrailCheckRead {
  name: string;
  passed: boolean;
  reason: string;
}

export interface RuleMatchRead {
  rule_code: string;
  rule_type: string;
  action: string | null;
  reason: string;
}

export interface SimilarClaimRead {
  claim_id: string;
  claim_number: string;
  status: string;
  final_decision: string;
  claim_type: string;
  billed_amount: string | null;
  date_of_service: string;
  submitted_at: string;
}

export interface PolicyCitation {
  source: string;
  text?: string;
  claim_type?: string;
  provider_id?: string;
  network_status?: string;
  forces_human_review?: boolean;
  reason?: string;
  [key: string]: unknown;
}

export interface ClaimReviewPacket {
  claim_id: string;
  claim_number: string;
  status: string;
  graph_thread_id: string | null;

  member_name: string;
  policy_number: string;
  provider_name: string | null;
  claim_type: string;
  billed_amount: string | null;
  date_of_service: string;

  extracted_fields: Record<string, unknown>;
  policy_citations: PolicyCitation[];
  similar_claims: SimilarClaimRead[];

  recommendation_type: AIRecommendationType | null;
  confidence_score: string | null;
  reasoning: string | null;

  guardrail_reason: string | null;
  guardrail_checks: GuardrailCheckRead[];
  matched_rules: RuleMatchRead[];

  audit_history: TimelineEvent[];
}

export interface ClaimDecisionCreate {
  decided_by: string;
  final_decision: Exclude<FinalDecisionStatus, "pending">;
  approved_amount?: string | null;
  reason: string;
  idempotency_key: string;
}

export interface RequestInfoCreate {
  requested_by: string;
  message: string;
}

export interface ApiErrorBody {
  detail?: string;
}
