"""Seed tests (ticket 11): full-domain coverage and an idempotent no-op re-run.

The seed is driven directly against ``db_test`` with a fresh async engine per
test (one event loop per test, so no pooled connection ever crosses loops).
The pre-existing-state test arranges data through the API, mirroring the dev
database (bootstrap Admin, one Team, a few Issues).
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from core.security.password import verify_password
from core.seed import ADMIN_EMAIL, USER_PASSWORD, seed
from core.settings import get_settings
from fastapi.testclient import TestClient
from psycopg2 import sql as pgsql
from psycopg2.extensions import connection as pg_connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.conftest import register_admin

API = "/api/v1"

# Every application table (the no-op proof: row counts + timestamp bounds).
TABLES = (
    "users",
    "workspace",
    "teams",
    "workflows",
    "workflow_states",
    "memberships",
    "labels",
    "issues",
    "issue_labels",
    "comments",
    "activity",
    "invitations",
)


def _async_test_url() -> str:
    """Return the async (asyncpg) form of the test database URL."""
    return get_settings().database_url.replace("postgresql", "postgresql+asyncpg")


def _snapshot(pg: pg_connection) -> dict[str, object]:
    """Row count + created/updated bounds for every table (no-op proof)."""
    snapshot: dict[str, object] = {}
    for table in TABLES:
        with pg.cursor() as cur:
            cur.execute(
                pgsql.SQL("SELECT count(*), min(created_at), max(updated_at) FROM {}").format(
                    pgsql.Identifier(table)
                )
            )
            snapshot[table] = cur.fetchone()
    return snapshot


@pytest.fixture
async def seed_engine() -> AsyncIterator[AsyncEngine]:
    """Fresh engine per test: one event loop per test, no cross-loop pooling."""
    engine = create_async_engine(_async_test_url())
    try:
        yield engine
    finally:
        await engine.dispose()


async def test_seed_creates_the_full_domain(seed_engine: AsyncEngine, pg: pg_connection) -> None:
    """One run creates the Admin, 2 Teams, 4 Users and 40 Issues covering everything."""
    async with AsyncSession(seed_engine, expire_on_commit=False) as session:
        report = await seed(session)

    assert report.admin_created is True
    assert report.admin_password is not None
    assert report.users_created == 4
    assert report.team_keys == ["ENG", "DSGN"]
    assert report.issues_created == 40
    assert report.comments_created == 10
    assert report.total_issues == 40
    _assert_people(pg, report.admin_password)
    _assert_issue_coverage(pg)


def _assert_people(pg: pg_connection, admin_password: str | None) -> None:
    """Assert the Admin, Users, Teams and Memberships (ticket 11)."""
    with pg.cursor() as cur:
        cur.execute("SELECT is_admin, hashed_password FROM users WHERE email = %s", (ADMIN_EMAIL,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] is True
        assert admin_password is not None
        assert verify_password(admin_password, row[1])

        cur.execute("SELECT hashed_password FROM users WHERE email != %s", (ADMIN_EMAIL,))
        hashes = [row[0] for row in cur.fetchall()]
        assert len(hashes) == 4
        assert all(verify_password(USER_PASSWORD, hashed) for hashed in hashes)

    counts = (
        ("SELECT count(*) FROM workspace", 1),
        ("SELECT count(*) FROM users", 5),
        ("SELECT count(*) FROM teams", 2),
        ("SELECT count(*) FROM memberships WHERE role = 'member'", 8),
        ("SELECT count(*) FROM memberships WHERE role = 'owner'", 2),
    )
    with pg.cursor() as cur:
        for query, expected in counts:
            cur.execute(query)
            row = cur.fetchone()
            assert row is not None
            assert row[0] == expected
    with pg.cursor() as cur:
        cur.execute("SELECT key FROM teams ORDER BY key")
        assert [row[0] for row in cur.fetchall()] == ["DSGN", "ENG"]


def _assert_issue_coverage(pg: pg_connection) -> None:
    """Assert the 40 seeded Issues exercise the full domain (ticket 11)."""
    checks = (
        ("SELECT count(*) FROM issues", 40),
        (
            "SELECT count(DISTINCT ws.category) "
            "FROM issues i JOIN workflow_states ws ON ws.id = i.state_id",
            5,
        ),
        ("SELECT count(DISTINCT priority) FROM issues", 5),
        ("SELECT count(*) FROM issues WHERE archived_at IS NOT NULL", 2),
        ("SELECT count(*) FROM issue_labels", 33),
        ("SELECT count(DISTINCT label_id) FROM issue_labels", 6),
        ("SELECT count(*) FROM comments", 10),
        ("SELECT count(DISTINCT issue_id) FROM comments", 9),
        ("SELECT count(DISTINCT assignee_id) FROM issues", 4),
        ("SELECT count(DISTINCT issue_id) FROM activity WHERE kind = 'issue.created'", 40),
        ("SELECT count(*) FROM activity WHERE kind = 'issue.state_changed'", 32),
        ("SELECT count(*) FROM issues WHERE parent_id IS NOT NULL", 3),
        ("SELECT count(*) FROM issues WHERE due_date IS NOT NULL", 5),
        ("SELECT count(*) FROM issues WHERE estimate IS NOT NULL", 22),
    )
    with pg.cursor() as cur:
        for query, expected in checks:
            cur.execute(query)
            row = cur.fetchone()
            assert row is not None
            assert row[0] == expected


async def test_seed_second_run_is_a_noop(seed_engine: AsyncEngine, pg: pg_connection) -> None:
    """A second run creates nothing and changes nothing (no updated_at bumps)."""
    async with AsyncSession(seed_engine, expire_on_commit=False) as session:
        first = await seed(session)
    assert first.issues_created == 40

    snapshot = _snapshot(pg)

    async with AsyncSession(seed_engine, expire_on_commit=False) as session:
        second = await seed(session)

    assert _snapshot(pg) == snapshot
    assert second.admin_created is False
    assert second.admin_password is None
    assert second.users_created == 0
    assert second.team_keys == []
    assert second.states_created == 0
    assert second.memberships_created == 0
    assert second.labels_created == 0
    assert second.issues_created == 0
    assert second.issues_archived == 0
    assert second.comments_created == 0
    assert second.issue_labels_created == 0
    assert second.total_issues == 40


async def test_seed_backfills_missing_state_category(
    client: TestClient, seed_engine: AsyncEngine, pg: pg_connection
) -> None:
    """A Team with a deleted State and a renamed State still gets full coverage."""
    register_admin(client)
    team = client.post(
        f"{API}/teams", json={"name": "Engineering", "key": "ENG", "description": None}
    )
    assert team.status_code == 201
    team_id = team.json()["id"]
    with pg.cursor() as cur:
        # Delete the only completed State and rename Backlog (user editor actions).
        cur.execute(
            "DELETE FROM workflow_states "
            "WHERE workflow_id = (SELECT id FROM workflows WHERE team_id = %s) "
            "AND category = 'completed'",
            (team_id,),
        )
        cur.execute(
            "UPDATE workflow_states SET name = 'To Do' "
            "WHERE workflow_id = (SELECT id FROM workflows WHERE team_id = %s) "
            "AND category = 'backlog'",
            (team_id,),
        )

    async with AsyncSession(seed_engine, expire_on_commit=False) as session:
        report = await seed(session)

    assert report.states_created == 1
    with pg.cursor() as cur:
        cur.execute(
            "SELECT name FROM workflow_states "
            "WHERE workflow_id = (SELECT id FROM workflows WHERE team_id = %s) "
            "AND category = 'completed'",
            (team_id,),
        )
        assert [row[0] for row in cur.fetchall()] == ["Done"]
        cur.execute(
            "SELECT ws.name, count(*) "
            "FROM issues i JOIN workflow_states ws ON ws.id = i.state_id "
            "JOIN teams t ON t.id = i.team_id "
            "WHERE t.key = 'ENG' AND ws.category = 'backlog' GROUP BY ws.name"
        )
        assert cur.fetchall() == [("To Do", 3)]


async def test_seed_respects_preexisting_data(
    client: TestClient, seed_engine: AsyncEngine, pg: pg_connection
) -> None:
    """Seeding a database that already has an Admin, ENG and Issues tops it up."""
    register_admin(client)
    team = client.post(
        f"{API}/teams", json={"name": "Engineering", "key": "ENG", "description": None}
    )
    assert team.status_code == 201
    team_id = team.json()["id"]
    issue = client.post(f"{API}/issues", json={"team_id": team_id, "title": "Pre-existing Issue"})
    assert issue.status_code == 201
    pre_existing_id = issue.json()["id"]

    async with AsyncSession(seed_engine, expire_on_commit=False) as session:
        report = await seed(session)

    assert report.admin_created is False
    assert report.team_keys == ["DSGN"]
    assert report.issues_created == 40

    with pg.cursor() as cur:
        cur.execute("SELECT id FROM teams WHERE key = 'ENG'")
        row = cur.fetchone()
        assert row is not None
        assert uuid.UUID(row[0]) == uuid.UUID(team_id)
        cur.execute("SELECT count(*) FROM issues")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 41
        cur.execute("SELECT number FROM issues WHERE id = %s", (pre_existing_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        cur.execute(
            "SELECT count(*) FROM issues i JOIN teams t ON t.id = i.team_id "
            "WHERE t.key = 'ENG' AND i.number BETWEEN 2 AND 21"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 20
        cur.execute("SELECT count(*) FROM issues WHERE archived_at IS NOT NULL")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 2


async def test_seed_adopts_only_its_own_issues(
    client: TestClient, seed_engine: AsyncEngine, pg: pg_connection
) -> None:
    """A colliding user Issue is skipped; a seed-user Issue is completed.

    Simulates an interrupted run: the seed created "Set up the core loop" as
    Ada before crashing, while an Admin-created Issue reuses the seeded title
    "Legacy session token cleanup" (a user Issue the seed must not touch).
    """
    register_admin(client)
    team = client.post(
        f"{API}/teams", json={"name": "Engineering", "key": "ENG", "description": None}
    )
    assert team.status_code == 201
    team_id = team.json()["id"]
    user_issue = client.post(
        f"{API}/issues",
        json={"team_id": team_id, "title": "Legacy session token cleanup"},
    )
    assert user_issue.status_code == 201

    with pg.cursor() as cur:
        # The interrupted seed run's leftovers: Ada (a seed User) and her Issue
        # in the default State, with the counter already advanced.
        cur.execute(
            "INSERT INTO users (email, hashed_password, display_name) "
            "VALUES (%s, %s, %s) RETURNING id",
            ("ada@example.com", "not-a-real-hash", "Ada Lovelace"),
        )
        row = cur.fetchone()
        assert row is not None
        ada_id = row[0]
        cur.execute(
            "INSERT INTO issues (team_id, number, title, state_id, priority, creator_id) "
            "VALUES (%s, 2, 'Set up the core loop', "
            "(SELECT id FROM workflow_states WHERE workflow_id = "
            "(SELECT id FROM workflows WHERE team_id = %s) AND position = 0), 'none', %s)",
            (team_id, team_id, ada_id),
        )
        cur.execute("UPDATE teams SET next_issue_number = 3 WHERE id = %s", (team_id,))

    async with AsyncSession(seed_engine, expire_on_commit=False) as session:
        report = await seed(session)

    assert report.issues_created == 38
    assert report.issues_archived == 1
    with pg.cursor() as cur:
        cur.execute("SELECT count(*) FROM issues")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 40
        cur.execute(
            "SELECT archived_at, (SELECT count(*) FROM comments WHERE issue_id = issues.id), "
            "(SELECT count(*) FROM issue_labels WHERE issue_id = issues.id) "
            "FROM issues WHERE title = 'Legacy session token cleanup'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] == 0
        assert row[2] == 0
        cur.execute(
            "SELECT archived_at, (SELECT count(*) FROM comments WHERE issue_id = issues.id), "
            "(SELECT count(*) FROM issue_labels WHERE issue_id = issues.id) "
            "FROM issues WHERE title = 'Set up the core loop'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] == 1
        assert row[2] == 1
        cur.execute(
            "SELECT ws.name FROM issues i "
            "JOIN workflow_states ws ON ws.id = i.state_id "
            "WHERE i.title = 'Set up the core loop'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Done"
