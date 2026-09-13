// Mirrors backend/api/app/schemas/*.py relevant to the member portal.

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

export interface MemberRead {
  member_id: string;
  member_number: string;
  first_name: string;
  last_name: string;
}

export interface MemberPolicyRead {
  policy_id: string;
  policy_number: string;
  plan_name: string;
  coverage_type: string;
  status: string;
  effective_date: string;
  expiration_date: string | null;
}

export interface ProviderRead {
  provider_id: string;
  name: string;
  provider_type: string;
  network_status: string;
}

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

export interface ClaimCreate {
  member_id: string;
  policy_id: string;
  provider_id?: string | null;
  claim_type: ClaimType;
  date_of_service: string;
  billed_amount?: string | null;
  procedure_codes?: string[];
  diagnosis_codes?: string[];
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

export interface ClaimDocumentRead {
  document_id: string;
  claim_id: string;
  document_type: string;
  file_name: string;
  mime_type: string | null;
  file_size_bytes: number | null;
  uploaded_at: string;
}

export interface ApiErrorBody {
  detail?: string;
}

export interface MemberLoginRequest {
  member_number: string;
  date_of_birth: string;
}

export interface MemberTokenResponse {
  access_token: string;
  token_type: string;
  member: MemberRead;
}
