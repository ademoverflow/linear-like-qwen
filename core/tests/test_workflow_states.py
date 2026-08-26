"""Tests for the Team Workflow editor (ticket 08): states CRUD, reorder, delete-with-migrate."""

import uuid

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1"
STATES = f"{API}/teams/{{team_id}}/states"


def _create_team(client: TestClient, key: str = "ENG", name: str = "Engineering") -> dict:
    response = client.post(f"{API}/teams", json={"name": name, "key": key})
    assert response.status_code == 201
    return response.json()


def _states(client: TestClient, team_id: str) -> list[dict]:
    response = client.get(STATES.format(team_id=team_id))
    assert response.status_code == 200
    return response.json()


def _state_by_name(states: list[dict], name: str) -> dict:
    return next(state for state in states if state["name"] == name)


def _create_issue(client: TestClient, team_id: str, title: str = "First") -> dict:
    response = client.post(f"{API}/issues", json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _move_issue(client: TestClient, issue: dict, state_id: str) -> None:
    response = client.post(
        f"{API}/issues/{issue['id']}/transitions",
        json={"state_id": state_id, "updated_at": issue["updated_at"]},
    )
    assert response.status_code == 200


def _add_member(pg: pg_connection, team_id: str, user_id: uuid.UUID, role: str = "member") -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, %s)",
            (str(user_id), str(team_id), role),
        )


def _archive_team_directly(pg: pg_connection, team_id: str) -> None:
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team_id,))


def _activity_rows(
    pg: pg_connection, issue_id: str
) -> list[tuple[str, str | None, str | None, str | None]]:
    with pg.cursor() as cur:
        cur.execute(
            "SELECT kind, field, from_value, to_value "
            "FROM activity WHERE issue_id = %s ORDER BY seq",
            (issue_id,),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Listing (version added, ADR 0008)
# ---------------------------------------------------------------------------


def test_states_listing_includes_version(client: TestClient) -> None:
    """Every State carries its version (ticket line 3)."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    assert len(states) == 6
    for state in states:
        assert state["version"] == 1
    assert [state["position"] for state in states] == list(range(6))


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


def test_add_state_by_owner_appends_at_end(client: TestClient) -> None:
    """New States are appended (position = max + 1, version 1)."""
    register_admin(client)
    team = _create_team(client)
    response = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Testing", "category": "started", "color": "#336699"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Testing"
    assert body["position"] == 6
    assert body["version"] == 1
    states = _states(client, team["id"])
    assert states[-1]["id"] == body["id"]


def test_add_state_by_admin(client: TestClient) -> None:
    """Admins can add States to any Team (workspace privilege)."""
    register_admin(client)
    team = _create_team(client)
    response = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "QA", "category": "started", "color": "#336699"},
    )
    assert response.status_code == 201


def test_add_state_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A non-owner member cannot add States (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    response = login_as(client, member).post(
        STATES.format(team_id=team["id"]),
        json={"name": "Nope", "category": "started", "color": "#336699"},
    )
    assert response.status_code == 403


def test_add_state_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 on State add."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    response = login_as(client, outsider).post(
        STATES.format(team_id=team["id"]),
        json={"name": "Nope", "category": "started", "color": "#336699"},
    )
    assert response.status_code == 404


def test_add_state_validation(client: TestClient) -> None:
    """Duplicate name 409; bad category/colour/name are 400."""
    register_admin(client)
    team = _create_team(client)
    duplicate = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Done", "category": "completed", "color": "#336699"},
    )
    assert duplicate.status_code == 409
    bad_category = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Weird", "category": "in-progress", "color": "#336699"},
    )
    assert bad_category.status_code == 400
    bad_color = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Weird", "category": "started", "color": "#gggggg"},
    )
    assert bad_color.status_code == 400
    blank_name = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "   ", "category": "started", "color": "#336699"},
    )
    assert blank_name.status_code == 400


def test_add_state_into_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """Adding States into an archived Team is a write and 403s."""
    register_admin(client)
    team = _create_team(client)
    _archive_team_directly(pg, team["id"])
    response = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Nope", "category": "started", "color": "#336699"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Edit (rename / recolor / category)
# ---------------------------------------------------------------------------


def test_rename_state_bumps_version(client: TestClient) -> None:
    """A rename echoes the new, bumped version (ADR 0008)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"name": "To Do", "version": state["version"]},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "To Do"
    assert response.json()["version"] == state["version"] + 1


def test_recolor_state(client: TestClient) -> None:
    """A recolor updates only the colour (version echo required)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"color": "#112233", "version": state["version"]},
    )
    assert response.status_code == 200
    assert response.json()["color"] == "#112233"


def test_recategory_state(client: TestClient) -> None:
    """A backlog State may leave its category (backlog is not in the minimum)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"category": "unstarted", "version": state["version"]},
    )
    assert response.status_code == 200
    assert response.json()["category"] == "unstarted"


def test_recategory_the_last_of_its_category_is_422(client: TestClient) -> None:
    """Category minimum: the only unstarted State cannot be re-categorised."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"category": "started", "version": state["version"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rule_violation"
    # The State is unchanged (nothing was written).
    assert _state_by_name(_states(client, team["id"]), "Todo")["category"] == "unstarted"


def test_stale_version_is_409(client: TestClient) -> None:
    """A stale version echo is a 409 (ticket line 3)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"name": "Stale", "version": state["version"] + 5},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_rename_to_existing_name_is_409(client: TestClient) -> None:
    """Renaming to an existing State name is a 409."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"name": "Done", "version": state["version"]},
    )
    assert response.status_code == 409


def test_nothing_to_update_is_400(client: TestClient) -> None:
    """Echoing every current value is a no-op (400, the label convention)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={
            "name": "Todo",
            "color": state["color"],
            "category": "unstarted",
            "version": state["version"],
        },
    )
    assert response.status_code == 400


def test_edit_unknown_or_foreign_state_is_404(client: TestClient) -> None:
    """Foreign and unknown State ids are 404s."""
    register_admin(client)
    team = _create_team(client)
    other = _create_team(client, key="DSG", name="Design")
    foreign = _state_by_name(_states(client, other["id"]), "Done")
    unknown = uuid.uuid4()
    for state_id in (str(foreign["id"]), str(unknown)):
        response = client.patch(
            f"{STATES.format(team_id=team['id'])}/{state_id}",
            json={"name": "Nope", "version": 1},
        )
        assert response.status_code == 404


def test_edit_by_member_is_403_and_non_member_404(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Members get 403 on State edits, non-members 404 (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    member = make_user()
    _add_member(pg, team["id"], member.id)
    outsider = make_user()
    payload = {"name": "Nope", "version": state["version"]}
    assert (
        login_as(client, member)
        .patch(f"{STATES.format(team_id=team['id'])}/{state['id']}", json=payload)
        .status_code
        == 403
    )
    assert (
        login_as(client, outsider)
        .patch(f"{STATES.format(team_id=team['id'])}/{state['id']}", json=payload)
        .status_code
        == 404
    )


def test_edit_into_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """Editing States of an archived Team is a write and 403s."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")
    _archive_team_directly(pg, team["id"])
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"name": "Nope", "version": state["version"]},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


def test_reorder_states(client: TestClient) -> None:
    """The full ordered list rewrites positions (offset-then-settle)."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    reversed_order = list(reversed(states))
    payload = {"states": [{"id": s["id"], "version": s["version"]} for s in reversed_order]}
    response = client.patch(f"{STATES.format(team_id=team['id'])}/reorder", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert [s["name"] for s in body] == [s["name"] for s in reversed_order]
    assert [s["position"] for s in body] == list(range(6))
    for state in body:
        assert state["version"] == 2  # every position changed


def test_reorder_partial_change_bumps_only_moved_states(client: TestClient) -> None:
    """Only the States whose position changed get their version bumped."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    reordered = [states[1], states[0], *states[2:]]  # swap the first two only
    payload = {"states": [{"id": s["id"], "version": s["version"]} for s in reordered]}
    response = client.patch(f"{STATES.format(team_id=team['id'])}/reorder", json=payload)
    assert response.status_code == 200
    body = {s["id"]: s for s in response.json()}
    assert body[states[0]["id"]]["version"] == 2
    assert body[states[1]["id"]]["version"] == 2
    assert body[states[2]["id"]]["version"] == 1  # untouched


def test_reorder_requires_the_full_list(client: TestClient) -> None:
    """Missing / extra / duplicate ids are 400."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    refs = [{"id": s["id"], "version": s["version"]} for s in states]

    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/reorder", json={"states": refs[:-1]}
    )
    assert response.status_code == 400

    unknown = uuid.uuid4()
    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/reorder",
        json={"states": [*refs, {"id": str(unknown), "version": 1}]},
    )
    assert response.status_code == 400

    response = client.patch(
        f"{STATES.format(team_id=team['id'])}/reorder",
        json={"states": [*refs, refs[0]]},
    )
    assert response.status_code == 400


def test_reorder_stale_version_is_409(client: TestClient) -> None:
    """Any stale version in the ordered list is a 409."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    refs = [{"id": s["id"], "version": s["version"]} for s in states]
    refs[0]["version"] += 1  # stale
    response = client.patch(f"{STATES.format(team_id=team['id'])}/reorder", json={"states": refs})
    assert response.status_code == 409


def test_reorder_unchanged_order_is_400(client: TestClient) -> None:
    """Re-sending the current order is a no-op (400)."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    payload = {"states": [{"id": s["id"], "version": s["version"]} for s in states]}
    response = client.patch(f"{STATES.format(team_id=team['id'])}/reorder", json=payload)
    assert response.status_code == 400


def test_reorder_by_member_is_403_and_non_member_404(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Members get 403 on reorder, non-members 404 (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    states = _states(client, team["id"])
    payload = {"states": [{"id": s["id"], "version": s["version"]} for s in states]}
    member = make_user()
    _add_member(pg, team["id"], member.id)
    outsider = make_user()
    assert (
        login_as(client, member)
        .patch(f"{STATES.format(team_id=team['id'])}/reorder", json=payload)
        .status_code
        == 403
    )
    assert (
        login_as(client, outsider)
        .patch(f"{STATES.format(team_id=team['id'])}/reorder", json=payload)
        .status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Delete + delete-with-migrate
# ---------------------------------------------------------------------------


def test_delete_state_without_issues(client: TestClient) -> None:
    """A State with no Issues deletes outright (204, ADR 0013)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"]},
    )
    assert response.status_code == 204
    names = [s["name"] for s in _states(client, team["id"])]
    assert "Backlog" not in names


def test_delete_state_with_issues_requires_a_target(client: TestClient) -> None:
    """Non-archived Issues → migrate_to_state_id is required (400)."""
    register_admin(client)
    team = _create_team(client)
    _create_issue(client, team["id"])  # lands in Backlog
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"]},
    )
    assert response.status_code == 400
    assert "migrate" in response.json()["error"]["message"].lower()


def test_delete_state_with_wrong_category_target_is_400(client: TestClient) -> None:
    """A wrong-category migration target is invalid input (400)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _move_issue(client, issue, _state_by_name(_states(client, team["id"]), "In Progress")["id"])
    state = _state_by_name(_states(client, team["id"]), "In Progress")
    done_id = _state_by_name(_states(client, team["id"]), "Done")["id"]
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"], "migrate_to_state_id": done_id},
    )
    assert response.status_code == 400
    assert "same category" in response.json()["error"]["message"].lower()


def test_delete_state_target_must_be_in_the_team(client: TestClient) -> None:
    """A migration target from another Team is a 400."""
    register_admin(client)
    team = _create_team(client)
    other = _create_team(client, key="DSG", name="Design")
    _create_issue(client, team["id"])
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    foreign = _state_by_name(_states(client, other["id"]), "Todo")["id"]
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"], "migrate_to_state_id": foreign},
    )
    assert response.status_code == 400


def test_delete_state_with_only_archived_issues_requires_a_target(
    client: TestClient, pg: pg_connection
) -> None:
    """The state_id FK is not cascading: even archived-only States need a target."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])  # Backlog
    client.post(f"{API}/issues/{issue['id']}/archive")
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"]},
    )
    assert response.status_code == 400
    # With a same-category target, the archived Issue moves but emits no Activity.
    cold = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Cold", "category": "backlog", "color": "#336699"},
    ).json()
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"], "migrate_to_state_id": cold["id"]},
    )
    assert response.status_code == 204
    with pg.cursor() as cur:
        cur.execute("SELECT state_id FROM issues WHERE id = %s", (issue["id"],))
        row = cur.fetchone()
    assert row is not None
    assert row[0] == cold["id"]
    rows = _activity_rows(pg, issue["id"])
    # The archive stamp (ticket 07) is there, but no issue.state_changed.
    assert [r[0] for r in rows] == ["issue.created", "issue.updated"]
    assert not any(r[0] == "issue.state_changed" for r in rows)


def test_delete_state_migrate_to_unneeded_is_400(client: TestClient) -> None:
    """A migration target on a State without Issues is a 400."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    todo_id = _state_by_name(_states(client, team["id"]), "Todo")["id"]
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"], "migrate_to_state_id": todo_id},
    )
    assert response.status_code == 400


def test_delete_only_required_state_is_422(client: TestClient) -> None:
    """Category minimum on delete (ticket line 4)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Todo")  # only unstarted
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rule_violation"


def test_delete_with_migrate_moves_issues_and_writes_activity(
    client: TestClient, pg: pg_connection
) -> None:
    """One transaction; one issue.state_changed per moved Issue (ticket line 4)."""
    register_admin(client)
    team = _create_team(client)
    # The migration target must share the deleted State's category: add a
    # second backlog and a second completed State.
    cold = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Cold", "category": "backlog", "color": "#336699"},
    ).json()
    shipped = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Shipped", "category": "completed", "color": "#2f9e44"},
    ).json()
    first = _create_issue(client, team["id"], "One")  # Backlog
    second = _create_issue(client, team["id"], "Two")  # Backlog
    backlog = _state_by_name(_states(client, team["id"]), "Backlog")

    url = f"{STATES.format(team_id=team['id'])}/{backlog['id']}"
    response = client.request(
        "DELETE", url, json={"version": backlog["version"], "migrate_to_state_id": cold["id"]}
    )
    assert response.status_code == 204
    for issue in (first, second):
        moved = client.get(f"{API}/issues/{issue['id']}").json()
        assert moved["state_id"] == cold["id"]
    assert ("issue.state_changed", "state_id", "Backlog", "Cold") in _activity_rows(pg, first["id"])
    assert ("issue.state_changed", "state_id", "Backlog", "Cold") in _activity_rows(
        pg, second["id"]
    )

    # A migration into `completed` stamps completed_at (transition bookkeeping).
    # The migration above moved `first`: re-read it for a fresh updated_at.
    first = client.get(f"{API}/issues/{first['id']}").json()
    _move_issue(client, first, _state_by_name(_states(client, team["id"]), "Done")["id"])
    done = _state_by_name(_states(client, team["id"]), "Done")
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{done['id']}",
        json={"version": done["version"], "migrate_to_state_id": shipped["id"]},
    )
    assert response.status_code == 204
    moved_first = client.get(f"{API}/issues/{first['id']}").json()
    assert moved_first["state_id"] == shipped["id"]
    assert moved_first["completed_at"] is not None
    # created + (Backlog to Cold) + (move to Done) + (Done to Shipped)
    kinds = [r[0] for r in _activity_rows(pg, first["id"])]
    assert kinds == [
        "issue.created",
        "issue.state_changed",
        "issue.state_changed",
        "issue.state_changed",
    ]


def test_delete_stale_version_is_409(client: TestClient) -> None:
    """A stale version on delete is a 409."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"] + 3},
    )
    assert response.status_code == 409


def test_delete_by_member_is_403_and_non_member_404(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Members get 403 on delete, non-members 404 (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    payload = {"version": state["version"]}
    member = make_user()
    _add_member(pg, team["id"], member.id)
    outsider = make_user()
    assert (
        login_as(client, member)
        .request("DELETE", f"{STATES.format(team_id=team['id'])}/{state['id']}", json=payload)
        .status_code
        == 403
    )
    assert (
        login_as(client, outsider)
        .request("DELETE", f"{STATES.format(team_id=team['id'])}/{state['id']}", json=payload)
        .status_code
        == 404
    )


def test_delete_into_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """Deleting States of an archived Team is a write and 403s."""
    register_admin(client)
    team = _create_team(client)
    state = _state_by_name(_states(client, team["id"]), "Backlog")
    _archive_team_directly(pg, team["id"])
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{state['id']}",
        json={"version": state["version"]},
    )
    assert response.status_code == 403


def test_delete_migrate_keeps_archived_issue_timestamps(
    client: TestClient, pg: pg_connection
) -> None:
    """Archived Issues keep their bookkeeping timestamps when migrated."""
    register_admin(client)
    team = _create_team(client)
    shipped = client.post(
        STATES.format(team_id=team["id"]),
        json={"name": "Shipped", "category": "completed", "color": "#2f9e44"},
    ).json()
    issue = _create_issue(client, team["id"])  # Backlog
    done = _state_by_name(_states(client, team["id"]), "Done")
    _move_issue(client, issue, done["id"])

    def row() -> tuple[object, object, object]:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT state_id, completed_at, canceled_at FROM issues WHERE id = %s",
                (issue["id"],),
            )
            fetched = cur.fetchone()
        assert fetched is not None
        return fetched

    before = row()
    assert before[1] is not None  # completed_at stamped by the transition
    client.post(f"{API}/issues/{issue['id']}/archive")
    response = client.request(
        "DELETE",
        f"{STATES.format(team_id=team['id'])}/{done['id']}",
        json={"version": done["version"], "migrate_to_state_id": shipped["id"]},
    )
    assert response.status_code == 204
    after = row()
    assert after[0] == shipped["id"]
    # The archived Issue moved, but its bookkeeping is untouched.
    assert after[1] == before[1]
    assert after[2] == before[2]
