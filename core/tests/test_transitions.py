"""Tests for Issue transitions and the Team states endpoint (ticket 04)."""

import uuid

from fastapi.testclient import TestClient
from httpx import Response
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/issues"
STATES = "/api/v1/teams/{team_id}/states"
ARCHIVED_TEAM_MESSAGE = "Team is archived"


def _create_team(client: TestClient) -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str = "First") -> dict:
    response = client.post(API, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _state_id_by_name(states: list[dict], name: str) -> str:
    return next(state["id"] for state in states if state["name"] == name)


def _transition(client: TestClient, issue: dict, state_id: str) -> Response:
    """POST the transition; returns the raw response."""
    return client.post(
        f"{API}/{issue['id']}/transitions",
        json={"state_id": state_id, "updated_at": issue["updated_at"]},
    )


def test_transition_happy_path_stamps_completed_at(client: TestClient, pg: pg_connection) -> None:
    """A member can move an Issue into a completed State; timestamps + Activity."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Ship it")
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")

    response = _transition(client, issue, done_id)
    assert response.status_code == 200
    body = response.json()
    assert body["state_name"] == "Done"
    assert body["state_category"] == "completed"
    assert body["state_color"] != ""
    assert body["completed_at"] is not None
    assert body["canceled_at"] is None
    assert body["updated_at"] != issue["updated_at"]
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.state_changed'",
            (issue["id"],),
        )
        row = cur.fetchone()
    assert row == ("state_id", "Backlog", "Done")


def test_transition_into_canceled_stamps_canceled_at(client: TestClient, pg: pg_connection) -> None:
    """Moving into a canceled State sets canceled_at and clears completed_at."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Drop it")
    states = client.get(STATES.format(team_id=team["id"])).json()
    canceled_id = _state_id_by_name(states, "Canceled")

    response = _transition(client, issue, canceled_id)
    assert response.status_code == 200
    body = response.json()
    assert body["state_name"] == "Canceled"
    assert body["canceled_at"] is not None
    assert body["completed_at"] is None
    with pg.cursor() as cur:
        cur.execute(
            "SELECT from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.state_changed'",
            (issue["id"],),
        )
        row = cur.fetchone()
    assert row == ("Backlog", "Canceled")


def test_transition_out_of_completed_clears_timestamps(client: TestClient) -> None:
    """Leaving a completed State into anything else clears both timestamps."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Reopen it")
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")
    in_progress_id = _state_id_by_name(states, "In Progress")

    first = _transition(client, issue, done_id)
    assert first.status_code == 200
    assert first.json()["completed_at"] is not None

    response = _transition(client, first.json(), in_progress_id)
    assert response.status_code == 200
    assert response.json()["state_name"] == "In Progress"
    assert response.json()["completed_at"] is None
    assert response.json()["canceled_at"] is None


def test_transition_out_of_canceled_clears_timestamps(client: TestClient) -> None:
    """Leaving a canceled State into anything else clears both timestamps."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Rekindle it")
    states = client.get(STATES.format(team_id=team["id"])).json()
    canceled_id = _state_id_by_name(states, "Canceled")
    todo_id = _state_id_by_name(states, "Todo")

    first = _transition(client, issue, canceled_id)
    assert first.status_code == 200
    assert first.json()["canceled_at"] is not None

    response = _transition(client, first.json(), todo_id)
    assert response.status_code == 200
    assert response.json()["completed_at"] is None
    assert response.json()["canceled_at"] is None


def test_transition_same_state_is_a_noop(client: TestClient, pg: pg_connection) -> None:
    """Moving a State to itself changes nothing and writes no Activity."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Stable")
    states = client.get(STATES.format(team_id=team["id"])).json()
    backlog_id = _state_id_by_name(states, "Backlog")

    response = _transition(client, issue, backlog_id)
    assert response.status_code == 200
    assert response.json()["updated_at"] == issue["updated_at"]
    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM activity WHERE issue_id = %s", (issue["id"],))
        count = cur.fetchone()
    assert count is not None
    assert count[0] == 1  # only issue.created


def test_transition_same_completed_state_keeps_timestamp(
    client: TestClient, pg: pg_connection
) -> None:
    """Re-entering the current completed State keeps its completed_at and writes no row."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Kept done")
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")

    first = _transition(client, issue, done_id)
    assert first.status_code == 200
    completed_at = first.json()["completed_at"]
    assert completed_at is not None

    response = _transition(client, first.json(), done_id)
    assert response.status_code == 200
    assert response.json()["completed_at"] == completed_at
    assert response.json()["updated_at"] == first.json()["updated_at"]
    with pg.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM activity WHERE issue_id = %s AND kind = 'issue.state_changed'",
            (issue["id"],),
        )
        count = cur.fetchone()
    assert count is not None
    assert count[0] == 1


def test_transition_stale_updated_at_is_409(client: TestClient) -> None:
    """A stale last-seen updated_at is a 409 and changes nothing (ADR 0008)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Racy")
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")

    response = client.post(
        f"{API}/{issue['id']}/transitions",
        json={"state_id": done_id, "updated_at": "2000-01-01T00:00:00Z"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert client.get(f"{API}/{issue['id']}").json()["state_name"] == "Backlog"


def test_non_member_transition_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 (not the ticket's 403) on transitions (ticket 03 convention)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert (
        other.post(
            f"{API}/{issue['id']}/transitions",
            json={"state_id": done_id, "updated_at": issue["updated_at"]},
        ).status_code
        == 404
    )


def test_transition_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """The genuine 403: a write (transition) into an archived Team is forbidden."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team["id"],))

    response = _transition(client, issue, done_id)
    assert response.status_code == 403
    assert response.json()["error"]["message"] == ARCHIVED_TEAM_MESSAGE
    assert client.get(f"{API}/{issue['id']}").json()["state_name"] == "Backlog"


def test_deactivated_member_transition_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A deactivated User gets 403 on everything, including transitions."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    states = client.get(STATES.format(team_id=team["id"])).json()
    done_id = _state_id_by_name(states, "Done")
    member = make_user(email="alice@example.com", is_active=False)
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, %s)",
            (member.id, team["id"], "member"),
        )
    other = login_as(client, member)
    assert (
        other.post(
            f"{API}/{issue['id']}/transitions",
            json={"state_id": done_id, "updated_at": issue["updated_at"]},
        ).status_code
        == 403
    )


def test_transition_state_of_other_team_is_400(client: TestClient) -> None:
    """A State that belongs to another Team's Workflow is a 400."""
    register_admin(client)
    team = _create_team(client)
    other_team = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    issue = _create_issue(client, team["id"])
    other_states = client.get(STATES.format(team_id=other_team["id"])).json()
    done_id = _state_id_by_name(other_states, "Done")

    response = _transition(client, issue, done_id)
    assert response.status_code == 400
    assert client.get(f"{API}/{issue['id']}").json()["state_name"] == "Backlog"


def test_transition_unknown_state_is_400(client: TestClient) -> None:
    """An unknown State id is a 400, not a 500."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    response = _transition(client, issue, str(uuid.uuid4()))
    assert response.status_code == 400


def test_team_states_endpoint_lists_states_in_position_order(client: TestClient) -> None:
    """Members see the Team's Workflow States in position order (board columns)."""
    register_admin(client)
    team = _create_team(client)
    response = client.get(STATES.format(team_id=team["id"]))
    assert response.status_code == 200
    rows = response.json()
    assert [(row["name"], row["category"], row["position"]) for row in rows] == [
        ("Backlog", "backlog", 0),
        ("Todo", "unstarted", 1),
        ("In Progress", "started", 2),
        ("In Review", "started", 3),
        ("Done", "completed", 4),
        ("Canceled", "canceled", 5),
    ]
    assert all(row["color"] for row in rows)
    assert all(row["id"] for row in rows)


def test_team_states_non_member_and_unknown_team_are_404(
    client: TestClient, make_user: MakeUser
) -> None:
    """Non-members and unknown Teams get 404 on the states endpoint."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.get(STATES.format(team_id=team["id"])).status_code == 404
    assert client.get(STATES.format(team_id=str(uuid.uuid4()))).status_code == 404


def test_team_states_deactivated_member_is_403(client: TestClient, make_user: MakeUser) -> None:
    """A deactivated User gets 403 (middleware) even on the read-only states endpoint."""
    register_admin(client)
    team = _create_team(client)
    member = make_user(email="bob@example.com", is_active=False)
    other = login_as(client, member)
    assert other.get(STATES.format(team_id=team["id"])).status_code == 403
