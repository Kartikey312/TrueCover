"""Integration test setup: a real (throwaway) Postgres database, the real
graph runtime (Postgres-backed checkpointer, not a mock), and an in-process
ASGI client against the actual FastAPI app.

These are integration tests on purpose -- claim processing here means the
API, the graph, and Postgres all agreeing with each other, which a mocked
DB session can't prove. Requires a reachable Postgres server (the same one
`docker compose up -d postgres` starts); a separate `insurance_ai_test`
database is created and torn down on it so dev data is never touched.
"""

import os
import tempfile
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

# Must happen before any `from app...` import anywhere in the test run --
# app.config/app.database build the engine at import time.
_STORAGE_DIR = tempfile.mkdtemp(prefix="insurance-api-test-storage-")
TEST_DB_NAME = "insurance_ai_test"
_ADMIN_HOST_DSN = os.environ.get("TEST_ADMIN_DSN", "postgresql://insurance_admin:changeme@localhost:5432/postgres")
_TEST_HOST_DSN = os.environ.get("TEST_DSN", f"postgresql://insurance_admin:changeme@localhost:5432/{TEST_DB_NAME}")
os.environ["DATABASE_URL"] = _TEST_HOST_DSN.replace("postgresql://", "postgresql+asyncpg://")
os.environ["STORAGE_ROOT"] = _STORAGE_DIR

import asyncpg  # noqa: E402
import bcrypt  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

# A low cost factor keeps per-test login fast -- this is only ever used
# against the throwaway test database, never a real credential.
SEED_PASSWORD = "test-password-123"
_SEED_PASSWORD_HASH = bcrypt.hashpw(SEED_PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("utf-8")

INIT_SQL_DIR = Path(__file__).resolve().parents[2] / "database" / "init"
# Re-applied after every per-test TRUNCATE, since it seeds the `rules`
# table -- otherwise only the first test in the session would ever see the
# default global rules that real claim processing depends on.
_SEED_RULES_SQL_FILE = INIT_SQL_DIR / "010_seed_default_global_rules.sql"

# `client` and `_database` below are session-scoped async fixtures (a fresh
# AsyncPostgresSaver + connection pool per test would be needlessly slow,
# and app.database's engine is a module-level singleton anyway -- it can
# only ever belong to one event loop for the life of the process). Every
# test module must carry `pytestmark = pytest.mark.asyncio(loop_scope="session")`
# so it runs in that same loop; pytest-asyncio 0.24 has no global default for
# a *test's* loop scope (only `asyncio_default_fixture_loop_scope`, set in
# pytest.ini, which covers fixtures), and injecting the marker via
# `pytest_collection_modifyitems` does not reliably take effect -- it must
# be a real module-level `pytestmark`.

TABLES_TO_TRUNCATE = (
    "audit_events",
    "ai_recommendations",
    "claim_decision_requests",
    "claim_documents",
    "adjuster_assignments",
    "claims",
    "rule_approvals",
    "rules",
    "policies",
    "providers_hospitals",
    "members",
    "users",
    "checkpoints",
    "checkpoint_writes",
    "checkpoint_blobs",
)


async def _recreate_test_database() -> None:
    conn = await asyncpg.connect(_ADMIN_HOST_DSN)
    try:
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            TEST_DB_NAME,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()

    test_conn = await asyncpg.connect(_TEST_HOST_DSN)
    try:
        for sql_file in sorted(INIT_SQL_DIR.glob("*.sql")):
            await test_conn.execute(sql_file.read_text())
    finally:
        await test_conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _stub_policy_retrieval():
    """Real policy retrieval hits a live Qdrant server and lazily downloads
    an embedding model on first use -- neither is available or desirable
    in this test run. Every test here exercises the same fallback path a
    real Qdrant outage takes (policy_context=None -> retrieval_node's
    placeholder); the Qdrant-backed path itself is covered by
    backend/qdrant's own test suite and graph/tests/test_nodes.py's
    retrieval_node tests.
    """
    from app.services import policy_retrieval_service

    original = policy_retrieval_service.fetch_policy_context
    policy_retrieval_service.fetch_policy_context = lambda **kwargs: None
    yield
    policy_retrieval_service.fetch_policy_context = original


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    await _recreate_test_database()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(_database):
    yield
    conn = await asyncpg.connect(_TEST_HOST_DSN)
    try:
        await conn.execute(f"TRUNCATE TABLE {', '.join(TABLES_TO_TRUNCATE)} RESTART IDENTITY CASCADE")
        await conn.execute(_SEED_RULES_SQL_FILE.read_text())
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session")
async def client(_database):
    from app.graph_runtime import init_graph_runtime, shutdown_graph_runtime
    from app.main import app as fastapi_app

    await init_graph_runtime()
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await shutdown_graph_runtime()


@pytest_asyncio.fixture
async def seed(client):
    """A minimal, consistent world: one adjuster, one compliance officer,
    one engineer (role=admin, i.e. NOT compliance -- for testing that the
    approval gate rejects them), one member with an active policy, one
    hospital. Individual tests add whatever else they need (claims, rules,
    documents).

    All three staff users share SEED_PASSWORD; `adjuster_headers` /
    `compliance_headers` / `engineer_headers` are ready-to-use
    Authorization headers from a real /auth/login call, since every
    write action that records an actor now requires one.
    """
    adjuster_id = str(uuid.uuid4())
    compliance_id = str(uuid.uuid4())
    engineer_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    other_member_id = str(uuid.uuid4())
    policy_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())

    conn = await asyncpg.connect(_TEST_HOST_DSN)
    try:
        await conn.execute(
            "INSERT INTO users (user_id, full_name, email, role, password_hash) VALUES "
            "($1,$2,$3,$4,$5), ($6,$7,$8,$9,$10), ($11,$12,$13,$14,$15)",
            adjuster_id,
            "Alex Adjuster",
            "alex@example.com",
            "adjuster",
            _SEED_PASSWORD_HASH,
            compliance_id,
            "Carla Compliance",
            "carla@example.com",
            "compliance_officer",
            _SEED_PASSWORD_HASH,
            engineer_id,
            "Eve Engineer",
            "eve@example.com",
            "admin",
            _SEED_PASSWORD_HASH,
        )
        await conn.execute(
            "INSERT INTO members (member_id, member_number, first_name, last_name, date_of_birth) "
            "VALUES ($1,$2,$3,$4,$5), ($6,$7,$8,$9,$10)",
            member_id,
            "MBR-0001",
            "Jane",
            "Doe",
            date(1990, 1, 1),
            other_member_id,
            "MBR-0002",
            "John",
            "Smith",
            date(1985, 5, 5),
        )
        await conn.execute(
            "INSERT INTO policies "
            "(policy_id, policy_number, member_id, plan_name, coverage_type, effective_date, premium_amount) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            policy_id,
            "POL-0001",
            member_id,
            "Gold PPO",
            "individual",
            date(2026, 1, 1),
            Decimal("450.00"),
        )
        await conn.execute(
            "INSERT INTO providers_hospitals (provider_id, name, provider_type) VALUES ($1,$2,$3)",
            provider_id,
            "City General Hospital",
            "hospital",
        )
    finally:
        await conn.close()

    async def _login(email: str) -> dict[str, str]:
        response = await client.post("/auth/login", json={"email": email, "password": SEED_PASSWORD})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def _member_login(member_number: str, dob: date) -> dict[str, str]:
        response = await client.post(
            "/auth/member-login", json={"member_number": member_number, "date_of_birth": dob.isoformat()}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return SimpleNamespace(
        adjuster_id=adjuster_id,
        compliance_id=compliance_id,
        engineer_id=engineer_id,
        member_id=member_id,
        other_member_id=other_member_id,
        policy_id=policy_id,
        provider_id=provider_id,
        adjuster_headers=await _login("alex@example.com"),
        compliance_headers=await _login("carla@example.com"),
        engineer_headers=await _login("eve@example.com"),
        member_headers=await _member_login("MBR-0001", date(1990, 1, 1)),
        other_member_headers=await _member_login("MBR-0002", date(1985, 5, 5)),
    )
