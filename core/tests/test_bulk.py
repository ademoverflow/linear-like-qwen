"""Tests for the bulk Issue operation endpoint (ticket 05, brief §4.4)."""

import uuid

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/issues"
BULK = "/api/v1/issues/bulk"


def _create_team(client: TestClient) -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str) -> dict:
    response = client.post(API, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _create_label(client: TestClient, team_id: str, name: str) -> dict:
    response = client.post(
        f"/api/v1/teams/{team_id}/labels", json={"name": name, "color": "#111111"}
    )
    assert response.status_code == 201
    return response.json()


def _state_id_by_name(client: TestClient, team_id: str, name: str) -> str:
    states = client.get(f"/api/v1/teams/{team_id}/states").json()
    return next(state["id"] for state in states if state["name"] == name)


def _bulk(client: TestClient, issue_ids: list[str], **action: object) -> dict:
    response = client.post(BULK, json={"issue_ids": issue_ids, **action})
    return response.json()


def _activities(client: TestClient, issue_id: str) -> list[dict]:
    return client.get(f"{API}/{issue_id}/activity").json()


def test_bulk_transition_stamps_and_writes_activity(client: TestClient) -> None:
    """state_id goes through the domain transition (skipping same-State Issues)."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    done_id = _state_id_by_name(client, team["id"], "Done")
    moved = _bulk(client, [second["id"]], state_id=done_id)
    assert moved["issues"][0]["state_name"] == "Done"
    second = moved["issues"][0]
    # Bulk the pair into Done again: the one already there is skipped.
    result = client.post(BULK, json={"issue_ids": [first["id"], second["id"]], "state_id": done_id})
    assert result.status_code == 200
    bodies = {issue["id"]: issue for issue in result.json()["issues"]}
    assert bodies[first["id"]]["completed_at"] is not None
    assert bodies[second["id"]]["completed_at"] is not None
    # One state_changed row per Issue that actually moved.
    assert [
        row["kind"]
        for row in _activities(client, first["id"])
        if row["kind"] == "issue.state_changed"
    ] == ["issue.state_changed"]
    assert [
        row["kind"]
        for row in _activities(client, second["id"])
        if row["kind"] == "issue.state_changed"
    ] == ["issue.state_changed"]


def test_bulk_assignee(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """assignee_id sets the assignee and writes one issue.updated per Issue."""
    register_admin(client)
    team = _create_team(client)
    alice = make_user(email="alice@example.com")
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'member')",
            (alice.id, team["id"]),
        )
    with pg.cursor() as cur:
        cur.execute("UPDATE users SET display_name = %s WHERE id = %s", ("Alice", alice.id))
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")

    result = client.post(
        BULK, json={"issue_ids": [first["id"], second["id"]], "assignee_id": alice.id}
    )
    assert result.status_code == 200
    for issue in result.json()["issues"]:
        assert issue["assignee_id"] == alice.id
        assert issue["assignee_display_name"] == "Alice"
    for issue_id in (first["id"], second["id"]):
        rows = [row for row in _activities(client, issue_id) if row["field"] == "assignee_id"]
        assert len(rows) == 1
        assert rows[0]["to_value"] == "Alice"


def test_bulk_assign_to_non_member_is_400(client: TestClient, make_user: MakeUser) -> None:
    """A User without a Membership of the Team is rejected (400, nothing changes)."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user(email="outsider@example.com")
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")

    response = client.post(
        BULK, json={"issue_ids": [first["id"], second["id"]], "assignee_id": str(outsider.id)}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert client.get(f"{API}/{first['id']}").json()["assignee_id"] is None
    assert client.get(f"{API}/{second['id']}").json()["assignee_id"] is None


def test_bulk_add_and_remove_labels(client: TestClient) -> None:
    """add_label_ids / remove_label_ids write one Activity per label per Issue."""
    register_admin(client)
    team = _create_team(client)
    label_a = _create_label(client, team["id"], "a")
    label_b = _create_label(client, team["id"], "b")
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")

    result = client.post(
        BULK,
        json={
            "issue_ids": [first["id"], second["id"]],
            "add_label_ids": [label_a["id"], label_b["id"]],
        },
    )
    assert result.status_code == 200
    for issue in result.json()["issues"]:
        assert sorted(label["name"] for label in issue["labels"]) == ["a", "b"]
    for issue_id in (first["id"], second["id"]):
        rows = [row for row in _activities(client, issue_id) if row["field"] == "label_id"]
        assert sorted(row["to_value"] for row in rows) == ["a", "b"]

    result = client.post(
        BULK, json={"issue_ids": [first["id"]], "remove_label_ids": [label_a["id"]]}
    )
    assert result.status_code == 200
    body = result.json()["issues"][0]
    assert [label["name"] for label in body["labels"]] == ["b"]
    removed = [row for row in _activities(client, first["id"]) if row["from_value"] == "a"]
    assert len(removed) == 1


def test_bulk_archive_by_owner(client: TestClient, pg: pg_connection) -> None:
    """archive: true sets archived_at with one issue.updated per Issue."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")

    result = client.post(BULK, json={"issue_ids": [first["id"], second["id"]], "archive": True})
    assert result.status_code == 200
    for issue in result.json()["issues"]:
        assert issue["archived_at"] is not None
    # Archived Issues are invisible via the API, so read the Activity rows directly.
    for issue_id in (first["id"], second["id"]):
        with pg.cursor() as cur:
            cur.execute(
                "SELECT kind, from_value, to_value FROM activity "
                "WHERE issue_id = %s AND field = %s",
                (issue_id, "archived_at"),
            )
            rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "issue.updated"
    # Archived Issues vanish from the list.
    body = client.get(API, params={"team_id": team["id"]}).json()
    assert body["issues"] == []


def test_bulk_archive_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Archiving is owner-only: a member gets 403 and nothing changes."""
    register_admin(client)
    team = _create_team(client)
    member = make_user(email="member@example.com")
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'member')",
            (member.id, team["id"]),
        )
    other = login_as(client, member)
    first = _create_issue(client, team["id"], "First")

    response = other.post(BULK, json={"issue_ids": [first["id"]], "archive": True})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get(f"{API}/{first['id']}").json()["archived_at"] is None


def test_bulk_all_or_nothing_unknown_id(client: TestClient) -> None:
    """One unknown id -> 400 and nothing changes."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    label = _create_label(client, team["id"], "a")
    before = client.get(f"{API}/{first['id']}").json()

    response = client.post(
        BULK,
        json={"issue_ids": [first["id"], str(uuid.uuid4())], "add_label_ids": [label["id"]]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    after = client.get(f"{API}/{first['id']}").json()
    assert after["labels"] == []
    assert after["updated_at"] == before["updated_at"]
    assert client.get(f"{API}/{second['id']}").json()["labels"] == []


def test_bulk_archived_issue_is_400_and_nothing_changes(
    client: TestClient, pg: pg_connection
) -> None:
    """An already-archived Issue in the set -> 400, no changes."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    with pg.cursor() as cur:
        cur.execute("UPDATE issues SET archived_at = now() WHERE id = %s", (first["id"],))

    response = client.post(BULK, json={"issue_ids": [first["id"], second["id"]], "archive": True})
    assert response.status_code == 400
    assert client.get(f"{API}/{second['id']}").json()["archived_at"] is None


def test_bulk_mixed_teams_is_400(client: TestClient) -> None:
    """Issues from different Teams -> 400, nothing changes."""
    register_admin(client)
    team_a = _create_team(client)
    team_b = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    issue_a = _create_issue(client, team_a["id"], "A")
    issue_b = _create_issue(client, team_b["id"], "B")
    label = _create_label(client, team_a["id"], "a")

    response = client.post(
        BULK, json={"issue_ids": [issue_a["id"], issue_b["id"]], "add_label_ids": [label["id"]]}
    )
    assert response.status_code == 400
    assert client.get(f"{API}/{issue_a['id']}").json()["labels"] == []
    assert client.get(f"{API}/{issue_b['id']}").json()["labels"] == []


def test_bulk_state_of_other_team_is_400(client: TestClient) -> None:
    """A State of another Team's Workflow is a 400, nothing changes."""
    register_admin(client)
    team_a = _create_team(client)
    team_b = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    issue = _create_issue(client, team_a["id"], "First")
    other_done = _state_id_by_name(client, team_b["id"], "Done")

    response = client.post(BULK, json={"issue_ids": [issue["id"]], "state_id": other_done})
    assert response.status_code == 400
    assert client.get(f"{API}/{issue['id']}").json()["state_name"] == "Backlog"


def test_bulk_labels_of_other_team_is_400(client: TestClient) -> None:
    """Labels of another Team are rejected (400), nothing changes."""
    register_admin(client)
    team_a = _create_team(client)
    team_b = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    issue = _create_issue(client, team_a["id"], "First")
    other_label = _create_label(client, team_b["id"], "x")

    response = client.post(
        BULK, json={"issue_ids": [issue["id"]], "add_label_ids": [other_label["id"]]}
    )
    assert response.status_code == 400
    assert client.get(f"{API}/{issue['id']}").json()["labels"] == []


def test_bulk_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 on the bulk endpoint (ticket 03/04 convention)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "First")
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)

    assert other.post(BULK, json={"issue_ids": [issue["id"]], "archive": True}).status_code == 404


def test_bulk_no_action_or_multi_action_is_400(client: TestClient) -> None:
    """Zero or several actions at once are rejected (400)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "First")
    done_id = _state_id_by_name(client, team["id"], "Done")

    assert client.post(BULK, json={"issue_ids": [issue["id"]]}).status_code == 400
    assert client.post(BULK, json={"issue_ids": [issue["id"]], "archive": False}).status_code == 400
    response = client.post(
        BULK, json={"issue_ids": [issue["id"]], "state_id": done_id, "archive": True}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    # Nothing changed.
    body = client.get(f"{API}/{issue['id']}").json()
    assert body["state_name"] == "Backlog"
    assert body["archived_at"] is None


def test_bulk_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """A bulk action on an archived Team's Issues is a 403."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "First")
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team["id"],))

    response = client.post(BULK, json={"issue_ids": [issue["id"]], "archive": True})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
