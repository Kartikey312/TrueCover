"""One-off local-dev helper: sets known passwords on the seeded demo staff
users so /auth/login can actually be exercised. There is no user-management
endpoint yet (creating/rotating staff credentials would be an admin-only
feature of its own) -- this script is the stand-in until one exists.

Usage (from the repo root, with the Docker Postgres running):
    python backend/scripts/seed_demo_credentials.py
"""

import asyncio
import os

import asyncpg
import bcrypt

DSN = os.environ.get("DEMO_DB_DSN", "postgresql://insurance_admin:changeme@localhost:5432/insurance_ai")

DEMO_CREDENTIALS = {
    "alex@example.com": "adjuster123",
    "carla@example.com": "compliance123",
}


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for email, password in DEMO_CREDENTIALS.items():
            result = await conn.execute(
                "UPDATE users SET password_hash = $1 WHERE email = $2", _hash(password), email
            )
            matched = result.split()[-1] != "0"
            print(f"{email}: {'updated' if matched else 'NOT FOUND -- no such user in this database'}")
    finally:
        await conn.close()

    print("\nDemo credentials (adjuster console login):")
    for email, password in DEMO_CREDENTIALS.items():
        print(f"  {email} / {password}")


if __name__ == "__main__":
    asyncio.run(main())
