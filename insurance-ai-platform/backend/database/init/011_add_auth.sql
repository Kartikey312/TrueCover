-- Password-based login for internal staff users. Nullable: a user row can
-- exist (e.g. seeded for FK references in tests) before credentials are
-- provisioned, and simply can't log in until one is set.
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);

-- Members authenticate with member_number + date_of_birth (both already
-- collected at enrollment) rather than a separate password -- no schema
-- change needed there.
