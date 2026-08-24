"""Tests for the Issue endpoints: creation, numbering, visibility, concurrency."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/issues"


def _create_team(client: TestClient) -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"})
    assert response.status_code == 201
    return response.json()


def test_member_creates_first_issue(client: TestClient) -> None:
    """The first Issue of a Team is ENG-1 in the default (Backlog) State."""
    register_admin(client)
    team = _create_team(client)
    response = client.post(API, json={"team_id": team["id"], "title": "  Set up CI  "})
    assert response.status_code == 201
    body = response.json()
    assert body["number"] == 1
    assert body["identifier"] == "ENG-1"
    assert body["title"] == "Set up CI"
    assert body["state_name"] == "Backlog"
    assert body["state_category"] == "backlog"
    assert body["priority"] == "none"
    assert body["assignee_id"] is None
    assert body["creator_id"] is not None
    assert body["archived_at"] is None


def test_activity_row_written_on_create(client: TestClient, pg: pg_connection) -> None:
    """Creating an Issue writes an issue.created Activity row by the actor."""
    admin = register_admin(client)
    team = _create_team(client)
    issue = client.post(API, json={"team_id": team["id"], "title": "First"}).json()
    with pg.cursor() as cur:
        cur.execute("SELECT kind, actor_id FROM activity WHERE issue_id = %s", (issue["id"],))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "issue.created"
    assert row[1] == admin["id"]


def test_numbers_increment(client: TestClient) -> None:
    """Each created Issue gets the next per-Team number."""
    register_admin(client)
    team = _create_team(client)
    for n in (1, 2):
        body = client.post(API, json={"team_id": team["id"], "title": f"Issue {n}"}).json()
        assert body["identifier"] == f"ENG-{n}"


def test_non_member_cannot_create_or_list(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 (not 403) on Team-scoped Issue access."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.post(API, json={"team_id": team["id"], "title": "Sneaky"}).status_code == 404
    assert other.get(API, params={"team_id": team["id"]}).status_code == 404


def test_unknown_team_is_404(client: TestClient) -> None:
    """An unknown team id is a 404, not a 500."""
    register_admin(client)
    response = client.post(API, json={"team_id": str(uuid.uuid4()), "title": "Ghost"})
    assert response.status_code == 404


def test_invalid_title_rejected(client: TestClient) -> None:
    """Blank titles are 400 (domain); over-length titles are 422 (schema)."""
    register_admin(client)
    team = _create_team(client)
    assert client.post(API, json={"team_id": team["id"], "title": "   "}).status_code == 400
    assert client.post(API, json={"team_id": team["id"], "title": "x" * 256}).status_code == 422


def test_list_issues_returns_newest_first(client: TestClient) -> None:
    """The list is an envelope, newest first (created:desc, tie-break number desc)."""
    register_admin(client)
    team = _create_team(client)
    for i in (1, 2, 3):
        client.post(API, json={"team_id": team["id"], "title": f"Issue {i}"})
    body = client.get(API, params={"team_id": team["id"]}).json()
    assert body["next_cursor"] is None
    issues = body["issues"]
    assert [i["number"] for i in issues] == [3, 2, 1]
    assert [i["identifier"] for i in issues] == ["ENG-3", "ENG-2", "ENG-1"]


def test_concurrent_creation_no_duplicate_numbers(client: TestClient, pg: pg_connection) -> None:
    """N Issues created in parallel get exactly the numbers 1..N (ADR 0010)."""
    register_admin(client)
    team = _create_team(client)

    def create(_index: int) -> int:
        return client.post(API, json={"team_id": team["id"], "title": "Concurrent"}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(12)))

    assert all(status_code == 201 for status_code in results)
    with pg.cursor() as cur:
        cur.execute(
            "SELECT number FROM issues WHERE team_id = %s ORDER BY number",
            (team["id"],),
        )
        numbers = [row[0] for row in cur.fetchall()]
    assert numbers == list(range(1, 13))
