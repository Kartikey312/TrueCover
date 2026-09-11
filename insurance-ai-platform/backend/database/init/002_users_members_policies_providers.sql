-- Internal staff (adjusters, supervisors, compliance officers, admins).
-- Not requested explicitly, but assigned_adjuster_id / approver / actor
-- foreign keys need a target table to reference.
CREATE TABLE users (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name   VARCHAR(200) NOT NULL,
    email       VARCHAR(255) NOT NULL UNIQUE,
    role        user_role NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE members (
    member_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_number   VARCHAR(50) NOT NULL UNIQUE,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    date_of_birth   DATE NOT NULL,
    gender          VARCHAR(20),
    email           VARCHAR(255),
    phone           VARCHAR(30),
    address_line1   VARCHAR(255),
    address_line2   VARCHAR(255),
    city            VARCHAR(100),
    state           VARCHAR(100),
    postal_code     VARCHAR(20),
    country         VARCHAR(100),
    status          member_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE policies (
    policy_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_number       VARCHAR(50) NOT NULL UNIQUE,
    member_id           UUID NOT NULL REFERENCES members(member_id) ON DELETE RESTRICT,
    plan_name           VARCHAR(150) NOT NULL,
    coverage_type       VARCHAR(50) NOT NULL,
    effective_date      DATE NOT NULL,
    expiration_date     DATE,
    premium_amount      NUMERIC(12, 2) NOT NULL CHECK (premium_amount >= 0),
    deductible_amount   NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (deductible_amount >= 0),
    out_of_pocket_max   NUMERIC(12, 2) CHECK (out_of_pocket_max >= 0),
    status              policy_status NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expiration_date IS NULL OR expiration_date > effective_date)
);

CREATE TABLE providers_hospitals (
    provider_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    npi_number      VARCHAR(20) UNIQUE,
    name            VARCHAR(255) NOT NULL,
    provider_type   provider_type NOT NULL,
    specialty       VARCHAR(150),
    address_line1   VARCHAR(255),
    address_line2   VARCHAR(255),
    city            VARCHAR(100),
    state           VARCHAR(100),
    postal_code     VARCHAR(20),
    country         VARCHAR(100),
    phone           VARCHAR(30),
    email           VARCHAR(255),
    tax_id          VARCHAR(50),
    network_status  network_status NOT NULL DEFAULT 'out_of_network',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_members_status ON members(status);
CREATE INDEX idx_policies_member_id ON policies(member_id);
CREATE INDEX idx_policies_status ON policies(status);
CREATE INDEX idx_providers_network_status ON providers_hospitals(network_status);
