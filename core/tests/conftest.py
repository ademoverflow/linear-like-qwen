"""Shared pytest fixtures.

Strategy (ADR 0001): tests run against a dedicated ``<dbname>_test`` database on the same
Postgres server as development. The database is created on demand, migrated once per
session through the app lifespan, and every table is truncated after each test.

Test-side database access is **synchronous** (psycopg2). The app runs inside
``TestClient`` on its own event loop; sharing the asyncpg engine with pytest's loop
raises "attached to a different loop" errors, so tests never touch ``core.database.engine``
directly. Arrange state through the API where possible, or through the helpers here.

Exception: the seed tests (``test_seed.py``) drive ``core.seed`` (async) with a fresh
asyncpg engine created per test, so each test's event loop owns its own pool.

IMPORTANT: ``DATABASE_URL`` is rewritten *before* any ``core`` import, because settings are
cached at import time in several modules.
"""

import os
import uuid
from collections.abc import Callable, Iterator

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import connection as pg_connection


def _test_database_url() -> str:
    base = os.environ.get("DATABASE_URL")
    if base is None:
        msg = "DATABASE_URL must be set (it is in Docker via .env)"
        raise RuntimeError(msg)
    return base if base.endswith("_test") else f"{base}_test"


def _ensure_database_exists(url: str) -> None:
    """Create the test database if it does not exist yet."""
    admin_url, _, dbname = url.rpartition("/")
    conn = psycopg2.connect(f"{admin_url}/postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    finally:
        conn.close()


TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# TestClient requests target host "testserver"; a cookie ``Domain`` attribute
# from the dev .env would never round-trip, so tests run without one.
os.environ["COOKIE_DOMAIN"] = ""

# Only now is it safe to import the application.
from core.main import app  # noqa: E402
from core.models.user import User  # noqa: E402
from core.security.password import hash_password  # noqa: E402
from core.security.token import create_access_token_for_user  # noqa: E402
from core.services.auth import reset_login_rate_limiter  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """App client with lifespan (runs ``alembic upgrade head`` on the test DB)."""
    _ensure_database_exists(TEST_DATABASE_URL)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def pg() -> Iterator[pg_connection]:
    """Autocommit psycopg2 connection to the test database for arranging/asserting state."""
    conn = psycopg2.connect(TEST_DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clear_client_cookies(client: TestClient) -> None:
    """Cookies from earlier tests must not leak into the next test."""
    client.cookies.clear()


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter() -> Iterator[None]:
    """Give every test a fresh login rate-limit budget (ADR 0009)."""
    reset_login_rate_limiter()
    yield
    reset_login_rate_limiter()


@pytest.fixture(autouse=True)
def _truncate_tables(request: pytest.FixtureRequest) -> Iterator[None]:
    """Wipe every application table after each test. Keeps ``alembic_version``.

    Skipped for ``tests/domain/`` so pure domain tests never touch the database.
    """
    if "domain" in request.path.parts:
        yield
        return
    pg = request.getfixturevalue("pg")
    request.getfixturevalue("client")  # ensure the schema exists before the test runs
    yield
    tables = [t.name for t in SQLModel.metadata.sorted_tables]
    if not tables:
        return
    with pg.cursor() as cur:
        cur.execute(
            sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                sql.SQL(", ").join(sql.Identifier(t) for t in tables)
            )
        )


MakeUser = Callable[..., User]

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "correct horse battery staple"  # noqa: S105 (test-only fixture password)


def register_admin(client: TestClient) -> dict:
    """Register the bootstrap Admin via the API and log the client in.

    Returns the ``me`` payload of the created Admin; the client ends up
    authenticated as that Admin.
    """
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert logged_in.status_code == 200
    return registered.json()


@pytest.fixture
def make_user(pg: pg_connection) -> MakeUser:
    """Build a factory that inserts a User row with a known password.

    Usage: ``user = make_user(email="a@b.c", is_active=False)``
    """

    def _make(
        email: str | None = None,
        password: str = "correct horse battery staple",  # noqa: S107
        *,
        is_active: bool = True,
    ) -> User:
        resolved_email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        with pg.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, hashed_password, is_active) "
                "VALUES (%s, %s, %s) RETURNING id, created_at, updated_at",
                (resolved_email, hash_password(password), is_active),
            )
            row = cur.fetchone()
        assert row is not None
        user_id, created_at, updated_at = row
        return User(
            id=user_id,
            email=resolved_email,
            hashed_password="<not returned>",  # noqa: S106
            is_active=is_active,
            created_at=created_at,
            updated_at=updated_at,
        )

    return _make


def login_as(client: TestClient, user: User) -> TestClient:
    """Attach a valid access-token cookie for ``user`` to the client and return it."""
    client.cookies.set("access_token", create_access_token_for_user(user.id, user.email))
    return client
