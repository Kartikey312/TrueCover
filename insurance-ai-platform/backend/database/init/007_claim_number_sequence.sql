-- Backs claim_number generation in the API (CLM-{year}-{seq}) so concurrent
-- submissions never collide.
CREATE SEQUENCE IF NOT EXISTS claim_number_seq START 1;
