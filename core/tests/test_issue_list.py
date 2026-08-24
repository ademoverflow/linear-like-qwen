"""Tests for Issue list filters, sort and cursor pagination (ticket 05)."""

import uuid

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

ISSUES = "/api/v1/issues"


def _create_team(client: TestClient) -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str) -> dict:
    response = client.post(ISSUES, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _patch_issue(client: TestClient, issue: dict, **fields: object) -> dict:
    response = client.patch(
        f"{ISSUES}/{issue['id']}",
        json={"updated_at": issue["updated_at"], **fields},
    )
    assert response.status_code == 200
    return response.json()


def _transition_issue(client: TestClient, issue: dict, state_id: str) -> dict:
    response = client.post(
        f"{ISSUES}/{issue['id']}/transitions",
        json={"state_id": state_id, "updated_at": issue["updated_at"]},
    )
    assert response.status_code == 200
    return response.json()


def _state_id_by_name(client: TestClient, team_id: str, name: str) -> str:
    states = client.get(f"/api/v1/teams/{team_id}/states").json()
    return next(state["id"] for state in states if state["name"] == name)


def test_list_returns_envelope_with_labels(client: TestClient) -> None:
    """The list is an envelope {issues, next_cursor}; Issues carry labels."""
    register_admin(client)
    team = _create_team(client)
    _create_issue(client, team["id"], "First")

    body = client.get(ISSUES, params={"team_id": team["id"]}).json()
    assert set(body) == {"issues", "next_cursor"}
    assert body["next_cursor"] is None
    assert len(body["issues"]) == 1
    assert body["issues"][0]["labels"] == []
    assert body["issues"][0]["identifier"] == "ENG-1"


def test_filter_by_state(client: TestClient) -> None:
    """state_id[] keeps only the Issues in those States (OR within the field)."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    _ = _create_issue(client, team["id"], "Third")
    todo_id = _state_id_by_name(client, team["id"], "Todo")
    in_progress_id = _state_id_by_name(client, team["id"], "In Progress")
    _transition_issue(client, first, todo_id)
    _transition_issue(client, second, in_progress_id)

    body = client.get(
        ISSUES,
        params=[("team_id", team["id"]), ("state_id", todo_id), ("state_id", in_progress_id)],
    ).json()
    assert {issue["id"] for issue in body["issues"]} == {first["id"], second["id"]}

    body = client.get(ISSUES, params={"team_id": team["id"], "state_id": todo_id}).json()
    assert [issue["id"] for issue in body["issues"]] == [first["id"]]


def test_filter_by_priority_and_combinable(client: TestClient) -> None:
    """priority[] filters; filters combine with AND across fields."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    third = _create_issue(client, team["id"], "Third")
    _patch_issue(client, first, priority="urgent")
    _patch_issue(client, second, priority="urgent")
    third = _transition_issue(client, third, _state_id_by_name(client, team["id"], "Todo"))
    _patch_issue(client, third, priority="low")

    body = client.get(ISSUES, params={"team_id": team["id"], "priority": "urgent"}).json()
    assert {issue["id"] for issue in body["issues"]} == {first["id"], second["id"]}

    body = client.get(
        ISSUES,
        params={
            "team_id": team["id"],
            "priority": "urgent",
            "state_id": _state_id_by_name(client, team["id"], "Todo"),
        },
    ).json()
    assert body["issues"] == []


def test_filter_by_assignee(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """assignee_id[] keeps only Issues assigned to those Users."""
    register_admin(client)
    team = _create_team(client)
    alice = make_user(email="alice@example.com")
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'member')",
            (alice.id, team["id"]),
        )
    first = _create_issue(client, team["id"], "First")
    _ = _create_issue(client, team["id"], "Second")
    _patch_issue(client, first, assignee_id=alice.id)

    body = client.get(ISSUES, params={"team_id": team["id"], "assignee_id": str(alice.id)}).json()
    assert [issue["id"] for issue in body["issues"]] == [first["id"]]


def test_filter_by_label(client: TestClient) -> None:
    """label_id[] keeps only Issues carrying any of the Labels."""
    register_admin(client)
    team = _create_team(client)
    label_a = client.post(
        f"/api/v1/teams/{team['id']}/labels", json={"name": "a", "color": "#111111"}
    ).json()
    label_b = client.post(
        f"/api/v1/teams/{team['id']}/labels", json={"name": "b", "color": "#222222"}
    ).json()
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    _patch_issue(client, first, label_ids=[label_a["id"], label_b["id"]])
    _patch_issue(client, second, label_ids=[label_a["id"]])

    body = client.get(ISSUES, params={"team_id": team["id"], "label_id": label_b["id"]}).json()
    assert [issue["id"] for issue in body["issues"]] == [first["id"]]

    body = client.get(
        ISSUES,
        params=[
            ("team_id", team["id"]),
            ("label_id", label_a["id"]),
            ("label_id", label_b["id"]),
        ],
    ).json()
    assert {issue["id"] for issue in body["issues"]} == {first["id"], second["id"]}


def test_other_team_label_filter_matches_nothing(client: TestClient) -> None:
    """A Label from another Team simply matches no Issue."""
    register_admin(client)
    team_a = _create_team(client)
    team_b = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    label = client.post(
        f"/api/v1/teams/{team_b['id']}/labels", json={"name": "x", "color": "#111111"}
    ).json()
    _create_issue(client, team_a["id"], "First")

    body = client.get(ISSUES, params={"team_id": team_a["id"], "label_id": label["id"]}).json()
    assert body["issues"] == []


def test_sort_created_default_and_asc(client: TestClient) -> None:
    """Default sort is created, newest first; created:asc is the reverse."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")

    body = client.get(ISSUES, params={"team_id": team["id"]}).json()
    assert [issue["id"] for issue in body["issues"]] == [second["id"], first["id"]]

    body = client.get(ISSUES, params={"team_id": team["id"], "sort": "created:asc"}).json()
    assert [issue["id"] for issue in body["issues"]] == [first["id"], second["id"]]


def test_sort_updated(client: TestClient) -> None:
    """updated:desc puts the most recently edited Issue first."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    _patch_issue(client, first, title="First edited")

    body = client.get(ISSUES, params={"team_id": team["id"], "sort": "updated:desc"}).json()
    assert [issue["id"] for issue in body["issues"]] == [first["id"], second["id"]]


def test_sort_priority(client: TestClient) -> None:
    """priority:desc orders urgent > high > medium > low > none."""
    register_admin(client)
    team = _create_team(client)
    issues = {}
    for name, priority in (("a", "low"), ("b", "urgent"), ("c", "none"), ("d", "high")):
        issues[name] = _create_issue(client, team["id"], f"Issue {name}")
        _patch_issue(client, issues[name], priority=priority)

    body = client.get(ISSUES, params={"team_id": team["id"], "sort": "priority:desc"}).json()
    assert [issue["id"] for issue in body["issues"]] == [
        issues["b"]["id"],
        issues["d"]["id"],
        issues["a"]["id"],
        issues["c"]["id"],
    ]
    body = client.get(ISSUES, params={"team_id": team["id"], "sort": "priority:asc"}).json()
    assert [issue["id"] for issue in body["issues"]] == [
        issues["c"]["id"],
        issues["a"]["id"],
        issues["d"]["id"],
        issues["b"]["id"],
    ]


def test_pagination_page_boundaries(client: TestClient) -> None:
    """Default page is 50; the cursor walks to the end exactly once."""
    register_admin(client)
    team = _create_team(client)
    for index in range(52):
        _create_issue(client, team["id"], f"Issue {index}")

    first_page = client.get(ISSUES, params={"team_id": team["id"]}).json()
    assert len(first_page["issues"]) == 50
    assert first_page["next_cursor"] is not None

    second_page = client.get(
        ISSUES, params={"team_id": team["id"], "cursor": first_page["next_cursor"]}
    ).json()
    assert len(second_page["issues"]) == 2
    assert second_page["next_cursor"] is None

    seen = [issue["id"] for page in (first_page, second_page) for issue in page["issues"]]
    assert len(seen) == 52
    assert len(set(seen)) == 52


def test_pagination_with_tied_values_across_pages(client: TestClient) -> None:
    """Tied sort values (same priority) page correctly in both directions."""
    register_admin(client)
    team = _create_team(client)
    for index in range(52):
        issue = _create_issue(client, team["id"], f"Issue {index}")
        _patch_issue(client, issue, priority="low")

    for direction in ("asc", "desc"):
        seen: list[str] = []
        cursor = None
        pages = 0
        while True:
            params: dict[str, str] = {"team_id": team["id"], "sort": f"priority:{direction}"}
            if cursor is not None:
                params["cursor"] = cursor
            page = client.get(ISSUES, params=params).json()
            seen.extend(issue["id"] for issue in page["issues"])
            pages += 1
            cursor = page["next_cursor"]
            if cursor is None:
                break
            assert pages <= 5
        assert pages == 2
        assert len(seen) == 52
        assert len(set(seen)) == 52


def test_limit_bounds(client: TestClient) -> None:
    """limit=1 works; limits outside 1-200 are rejected (400)."""
    register_admin(client)
    team = _create_team(client)
    for index in range(3):
        _create_issue(client, team["id"], f"Issue {index}")

    small = client.get(ISSUES, params={"team_id": team["id"], "limit": 1}).json()
    assert len(small["issues"]) == 1
    assert small["next_cursor"] is not None

    for limit in (0, -1, 201, 1000):
        response = client.get(ISSUES, params={"team_id": team["id"], "limit": limit})
        assert response.status_code == 400, limit

    big = client.get(ISSUES, params={"team_id": team["id"], "limit": 200}).json()
    assert len(big["issues"]) == 3
    assert big["next_cursor"] is None


def test_invalid_sort_and_cursor_are_400(client: TestClient) -> None:
    """Bad sort strings and malformed cursors are rejected (400)."""
    register_admin(client)
    team = _create_team(client)
    _create_issue(client, team["id"], "First")

    assert (
        client.get(ISSUES, params={"team_id": team["id"], "sort": "number:desc"}).status_code == 400
    )
    assert (
        client.get(ISSUES, params={"team_id": team["id"], "sort": "created:up"}).status_code == 400
    )
    assert client.get(ISSUES, params={"team_id": team["id"], "cursor": "!!!"}).status_code == 400
    # An invalid priority filter value is a 400 too.
    assert (
        client.get(ISSUES, params={"team_id": team["id"], "priority": "blocker"}).status_code == 400
    )


def test_cursor_from_other_sort_is_400(client: TestClient) -> None:
    """Reusing a cursor with a different sort is a 400 (not a 500)."""
    register_admin(client)
    team = _create_team(client)
    for index in range(3):
        issue = _create_issue(client, team["id"], f"Issue {index}")
        _patch_issue(client, issue, priority="low")

    created_page = client.get(ISSUES, params={"team_id": team["id"], "limit": 2}).json()
    assert created_page["next_cursor"] is not None
    assert (
        client.get(
            ISSUES,
            params={
                "team_id": team["id"],
                "sort": "priority:desc",
                "cursor": created_page["next_cursor"],
            },
        ).status_code
        == 400
    )
    priority_page = client.get(
        ISSUES, params={"team_id": team["id"], "sort": "priority:desc", "limit": 2}
    ).json()
    assert priority_page["next_cursor"] is not None
    assert (
        client.get(
            ISSUES, params={"team_id": team["id"], "cursor": priority_page["next_cursor"]}
        ).status_code
        == 400
    )


def test_archived_issues_are_hidden(client: TestClient, pg: pg_connection) -> None:
    """Archived Issues stay out of the default list (restoration is ticket 07)."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    with pg.cursor() as cur:
        cur.execute("UPDATE issues SET archived_at = now() WHERE id = %s", (first["id"],))

    body = client.get(ISSUES, params={"team_id": team["id"]}).json()
    assert [issue["id"] for issue in body["issues"]] == [second["id"]]


def test_non_member_list_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 on the list (ticket 03/04 convention)."""
    register_admin(client)
    team = _create_team(client)
    _create_issue(client, team["id"], "First")
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)

    assert other.get(ISSUES, params={"team_id": team["id"]}).status_code == 404


def test_unknown_team_list_is_404(client: TestClient) -> None:
    """An unknown Team id is a 404."""
    register_admin(client)
    assert client.get(ISSUES, params={"team_id": str(uuid.uuid4())}).status_code == 404
