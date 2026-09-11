-- Enumerated types shared across the schema.

CREATE TYPE user_role AS ENUM ('adjuster', 'supervisor', 'compliance_officer', 'admin');

CREATE TYPE member_status AS ENUM ('active', 'inactive', 'suspended');

CREATE TYPE policy_status AS ENUM ('active', 'lapsed', 'cancelled', 'pending');

CREATE TYPE provider_type AS ENUM ('hospital', 'clinic', 'physician', 'lab', 'pharmacy', 'other');

CREATE TYPE network_status AS ENUM ('in_network', 'out_of_network');

CREATE TYPE claim_status AS ENUM (
    'submitted',
    'under_review',
    'pending_documents',
    'pending_adjuster_review',
    'approved',
    'denied',
    'appealed',
    'closed',
    'paid'
);

CREATE TYPE claim_type AS ENUM ('medical', 'dental', 'vision', 'pharmacy', 'other');

CREATE TYPE final_decision_status AS ENUM ('pending', 'approved', 'denied', 'partially_approved');

CREATE TYPE document_type AS ENUM (
    'medical_record',
    'invoice',
    'receipt',
    'id_proof',
    'discharge_summary',
    'prescription',
    'other'
);

CREATE TYPE assignment_reason AS ENUM ('initial', 'reassignment', 'escalation', 'workload_balancing');

CREATE TYPE rule_type AS ENUM (
    'eligibility',
    'fraud_detection',
    'auto_approval',
    'auto_denial',
    'compliance',
    'pricing'
);

CREATE TYPE rule_status AS ENUM ('draft', 'pending_approval', 'active', 'deprecated', 'rejected');

CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected', 'changes_requested');

CREATE TYPE actor_type AS ENUM ('user', 'system', 'ai_agent');

CREATE TYPE ai_recommendation_type AS ENUM (
    'approve',
    'deny',
    'request_more_info',
    'flag_for_fraud',
    'escalate'
);

CREATE TYPE ai_recommendation_status AS ENUM ('pending_review', 'accepted', 'overridden', 'rejected');
