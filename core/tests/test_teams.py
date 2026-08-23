"""Tests for the Team endpoints: creation (with Workflow seeding), visibility."""

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/teams"


def test_admin_creates_team_with_default_workflow(client: TestClient, pg: pg_connection) -> None:
    """A new Team gets its Workflow, six default States and the owner row."""
    register_admin(client)
    response = client.post(
        API,
        json={"name": "Engineering", "key": "ENG", "description": "Build stuff"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "ENG"
    assert body["name"] == "Engineering"
    assert body["description"] == "Build stuff"
    assert body["archived_at"] is None

    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM workflows WHERE team_id = %s", (body["id"],))
        count_row = cur.fetchone()
        assert count_row is not None
        assert count_row[0] == 1
        cur.execute(
            """
            SELECT s.name, s.category, s.position, s.version
            FROM workflow_states s
            JOIN workflows w ON w.id = s.workflow_id
            WHERE w.team_id = %s
            ORDER BY s.position
            """,
            (body["id"],),
        )
        states = cur.fetchall()
        cur.execute(
            """
            SELECT m.role, t.next_issue_number
            FROM teams t
            JOIN memberships m ON m.team_id = t.id
            WHERE t.id = %s
            """,
            (body["id"],),
        )
        membership_row = cur.fetchone()
        assert membership_row is not None
        role, counter = membership_row

    assert [(s[0], s[1], s[2]) for s in states] == [
        ("Backlog", "backlog", 0),
        ("Todo", "unstarted", 1),
        ("In Progress", "started", 2),
        ("In Review", "started", 3),
        ("Done", "completed", 4),
        ("Canceled", "canceled", 5),
    ]
    assert all(s[3] == 1 for s in states)
    assert role == "owner"
    assert counter == 1


def test_non_admin_cannot_create_team(client: TestClient, make_user: MakeUser) -> None:
    """Team creation is Admin-only (403 for everyone else)."""
    user = make_user(email="plain@example.com")
    response = login_as(client, user).post(API, json={"name": "X", "key": "ENG"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_invalid_team_key_rejected(client: TestClient) -> None:
    """Malformed keys are 400 (domain); out-of-range keys are 422 (schema)."""
    register_admin(client)
    for key in ("en", "EN1", "EN-G"):
        response = client.post(API, json={"name": "X", "key": key})
        assert response.status_code == 400, key
    response = client.post(API, json={"name": "X", "key": "TOOLONG"})
    assert response.status_code == 422


def test_duplicate_team_key_conflict(client: TestClient) -> None:
    """A taken key is a conflict, not a duplicate row."""
    register_admin(client)
    assert client.post(API, json={"name": "A", "key": "ENG"}).status_code == 201
    response = client.post(API, json={"name": "B", "key": "ENG"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_list_teams_visibility(client: TestClient, make_user: MakeUser, pg: pg_connection) -> None:
    """Members see only their Teams; Admins see all; outsiders see none."""
    register_admin(client)
    team = client.post(API, json={"name": "Engineering", "key": "ENG"}).json()
    outsider = make_user(email="outsider@example.com")
    member = make_user(email="member@example.com")
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'member')",
            (member.id, team["id"]),
        )

    # The client holds one cookie at a time: assert the Admin view first.
    assert [t["key"] for t in client.get(API).json()] == ["ENG"]
    assert login_as(client, outsider).get(API).json() == []
    assert [t["key"] for t in login_as(client, member).get(API).json()] == ["ENG"]
