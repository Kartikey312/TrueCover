import enum


class UserRole(str, enum.Enum):
    adjuster = "adjuster"
    supervisor = "supervisor"
    compliance_officer = "compliance_officer"
    admin = "admin"


class MemberStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class PolicyStatus(str, enum.Enum):
    active = "active"
    lapsed = "lapsed"
    cancelled = "cancelled"
    pending = "pending"


class ProviderType(str, enum.Enum):
    hospital = "hospital"
    clinic = "clinic"
    physician = "physician"
    lab = "lab"
    pharmacy = "pharmacy"
    other = "other"


class NetworkStatus(str, enum.Enum):
    in_network = "in_network"
    out_of_network = "out_of_network"


class ClaimStatus(str, enum.Enum):
    submitted = "submitted"
    under_review = "under_review"
    pending_documents = "pending_documents"
    pending_adjuster_review = "pending_adjuster_review"
    approved = "approved"
    denied = "denied"
    appealed = "appealed"
    closed = "closed"
    paid = "paid"


class ClaimType(str, enum.Enum):
    medical = "medical"
    dental = "dental"
    vision = "vision"
    pharmacy = "pharmacy"
    other = "other"


class FinalDecisionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    partially_approved = "partially_approved"


class DocumentType(str, enum.Enum):
    medical_record = "medical_record"
    invoice = "invoice"
    receipt = "receipt"
    id_proof = "id_proof"
    discharge_summary = "discharge_summary"
    prescription = "prescription"
    other = "other"


class AssignmentReason(str, enum.Enum):
    initial = "initial"
    reassignment = "reassignment"
    escalation = "escalation"
    workload_balancing = "workload_balancing"


class ActorType(str, enum.Enum):
    user = "user"
    system = "system"
    ai_agent = "ai_agent"


class RuleType(str, enum.Enum):
    eligibility = "eligibility"
    fraud_detection = "fraud_detection"
    auto_approval = "auto_approval"
    auto_denial = "auto_denial"
    compliance = "compliance"
    pricing = "pricing"


class RuleStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    active = "active"
    deprecated = "deprecated"
    rejected = "rejected"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"


class AIRecommendationType(str, enum.Enum):
    approve = "approve"
    deny = "deny"
    request_more_info = "request_more_info"
    flag_for_fraud = "flag_for_fraud"
    escalate = "escalate"


class AIRecommendationStatus(str, enum.Enum):
    pending_review = "pending_review"
    accepted = "accepted"
    overridden = "overridden"
    rejected = "rejected"
