"""Tests for archive, restore and hard delete (ticket 07)."""

import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/issues"
MEMBERS = "/api/v1/teams/{team_id}/members"


def _create_team(client: TestClient) -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str = "First") -> dict:
    response = client.post(API, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _add_member(pg: pg_connection, team_id: str, user_id: uuid.UUID, role: str = "member") -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, %s)",
            (str(user_id), str(team_id), role),
        )


def _archive(client: TestClient, issue_id: str) -> None:
    response = client.post(f"{API}/{issue_id}/archive")
    assert response.status_code == 200


def _restore(client: TestClient, issue_id: str) -> None:
    response = client.post(f"{API}/{issue_id}/restore")
    assert response.status_code == 200


def _set_parent(client: TestClient, child: dict, parent_id: str) -> None:
    response = client.patch(
        f"{API}/{child['id']}",
        json={"updated_at": child["updated_at"], "parent_id": parent_id},
    )
    assert response.status_code == 200


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
# include_archived listing (ticket line 1)
# ---------------------------------------------------------------------------


def test_include_archived_lists_archived_issues(client: TestClient) -> None:
    """Archived Issues are hidden by default, listed with ?include_archived=true."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "First")
    second = _create_issue(client, team["id"], "Second")
    _archive(client, first["id"])

    default = client.get(API, params={"team_id": team["id"]}).json()
    assert [issue["id"] for issue in default["issues"]] == [second["id"]]

    included = client.get(API, params={"team_id": team["id"], "include_archived": "true"}).json()
    assert {issue["id"] for issue in included["issues"]} == {first["id"], second["id"]}
    archived_included = next(issue for issue in included["issues"] if issue["id"] == first["id"])
    assert archived_included["archived_at"] is not None


def test_include_archived_combines_with_filters(client: TestClient) -> None:
    """The flag adds archived Issues to the existing filters, not a separate view."""
    register_admin(client)
    team = _create_team(client)
    kept = _create_issue(client, team["id"], "Kept")
    hidden = _create_issue(client, team["id"], "Hidden")
    other_state = _create_issue(client, team["id"], "Other state")
    states = client.get(f"/api/v1/teams/{team['id']}/states").json()
    done = next(state for state in states if state["category"] == "completed")
    client.post(
        f"{API}/{other_state['id']}/transitions",
        json={"state_id": done["id"], "updated_at": other_state["updated_at"]},
    )
    _archive(client, hidden["id"])

    body = client.get(
        API,
        params={"team_id": team["id"], "state_id": kept["state_id"], "include_archived": "true"},
    ).json()
    assert {issue["id"] for issue in body["issues"]} == {kept["id"], hidden["id"]}


# ---------------------------------------------------------------------------
# Archive (ticket line 1)
# ---------------------------------------------------------------------------


def test_archive_by_admin_and_owner(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A Team owner (or Admin) can archive; the Issue carries archived_at."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])

    body = client.post(f"{API}/{issue['id']}/archive").json()
    assert body["archived_at"] is not None

    # A non-Admin owner can archive too.
    owner = make_user(email="owner@example.com")
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)
    second = _create_issue(client, team["id"], "Second")
    assert other.post(f"{API}/{second['id']}/archive").status_code == 200


def test_archive_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """The genuine 403: a plain member cannot archive."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user(email="member@example.com")
    _add_member(pg, team["id"], member.id)
    other = login_as(client, member)

    response = other.post(f"{API}/{issue['id']}/archive")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get(f"{API}/{issue['id']}").json()["archived_at"] is None


def test_archive_by_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 (not 403), as on the other Issue endpoints."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.post(f"{API}/{issue['id']}/archive").status_code == 404


def test_archive_in_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """Writes into an archived Team are 403 (like the other Issue write paths)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team["id"],))
    assert client.post(f"{API}/{issue['id']}/archive").status_code == 403


def test_archive_emits_one_activity_row(client: TestClient, pg: pg_connection) -> None:
    """Archive emits one issue.updated row with field=archived_at."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    client.post(f"{API}/{issue['id']}/archive")

    rows = [row for row in _activity_rows(pg, issue["id"]) if row[1] == "archived_at"]
    assert len(rows) == 1
    assert rows[0][0] == "issue.updated"
    assert rows[0][2] is None
    assert rows[0][3] is not None


def test_double_archive_is_404(client: TestClient) -> None:
    """An already-archived Issue is no longer visible: a second archive is 404."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _archive(client, issue["id"])
    assert client.post(f"{API}/{issue['id']}/archive").status_code == 404


def test_archive_parent_archives_children(client: TestClient, pg: pg_connection) -> None:
    """Archiving a parent archives its children (brief §3.4); one Activity per Issue."""
    register_admin(client)
    team = _create_team(client)
    parent = _create_issue(client, team["id"], "Parent")
    child = _create_issue(client, team["id"], "Child")
    _set_parent(client, child, parent["id"])
    prearchived = _create_issue(client, team["id"], "Pre-archived child")
    _set_parent(client, prearchived, parent["id"])
    _archive(client, prearchived["id"])

    client.post(f"{API}/{parent['id']}/archive")

    assert client.get(f"{API}/{prearchived['id']}").status_code == 404
    included = client.get(API, params={"team_id": team["id"], "include_archived": "true"}).json()
    by_id = {issue["id"]: issue for issue in included["issues"]}
    assert by_id[parent["id"]]["archived_at"] is not None
    assert by_id[child["id"]]["archived_at"] is not None

    # One archived_at row per Issue (the pre-archived child's row dates
    # from its own archive).
    for issue_id in (parent["id"], child["id"], prearchived["id"]):
        rows = [row for row in _activity_rows(pg, issue_id) if row[1] == "archived_at"]
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Restore (ticket line 1 + 2)
# ---------------------------------------------------------------------------


def test_restore_by_owner_and_admin(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A Team owner (or Admin) can restore; the Issue reappears in the list."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _archive(client, issue["id"])

    owner = make_user(email="owner@example.com")
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)
    assert other.post(f"{API}/{issue['id']}/restore").status_code == 200

    restored = client.post(f"{API}/{issue['id']}/archive")
    assert restored.status_code == 200
    assert client.post(f"{API}/{issue['id']}/restore").json()["archived_at"] is None
    body = client.get(API, params={"team_id": team["id"]}).json()
    assert [item["id"] for item in body["issues"]] == [issue["id"]]


def test_restore_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A plain member cannot restore."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _archive(client, issue["id"])
    member = make_user(email="member@example.com")
    _add_member(pg, team["id"], member.id)
    other = login_as(client, member)
    assert other.post(f"{API}/{issue['id']}/restore").status_code == 403


def test_restore_by_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 on restore (the archived Issue is not visible to them)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _archive(client, issue["id"])
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.post(f"{API}/{issue['id']}/restore").status_code == 404


def test_restore_in_archived_team_is_403(client: TestClient, pg: pg_connection) -> None:
    """A write into an archived Team is 403, including restore."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _archive(client, issue["id"])
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team["id"],))
    assert client.post(f"{API}/{issue['id']}/restore").status_code == 403


def test_restore_non_archived_is_400(client: TestClient) -> None:
    """Restoring an Issue that is not archived is a 400 (no-op request)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    assert client.post(f"{API}/{issue['id']}/restore").status_code == 400


def test_restore_does_not_restore_children(client: TestClient) -> None:
    """Restoring a parent leaves archived children archived (brief §3.4)."""
    register_admin(client)
    team = _create_team(client)
    parent = _create_issue(client, team["id"], "Parent")
    child = _create_issue(client, team["id"], "Child")
    _set_parent(client, child, parent["id"])

    _archive(client, parent["id"])
    _restore(client, parent["id"])

    assert client.get(f"{API}/{parent['id']}").status_code == 200
    assert client.get(f"{API}/{child['id']}").status_code == 404
    included = client.get(API, params={"team_id": team["id"], "include_archived": "true"}).json()
    by_id = {item["id"]: item for item in included["issues"]}
    assert by_id[child["id"]]["archived_at"] is not None


def test_restore_emits_activity_row(client: TestClient, pg: pg_connection) -> None:
    """Restore emits one issue.updated row with the old timestamp as from_value."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    archived_at = client.post(f"{API}/{issue['id']}/archive").json()["archived_at"]
    client.post(f"{API}/{issue['id']}/restore")

    rows = [row for row in _activity_rows(pg, issue["id"]) if row[1] == "archived_at"]
    assert len(rows) == 2
    created_row, restored_row = rows
    assert created_row[2] is None
    assert created_row[3] is not None
    assert restored_row[2] == datetime.fromisoformat(archived_at).isoformat()
    assert restored_row[3] is None


# ---------------------------------------------------------------------------
# Hard delete (ticket line 3)
# ---------------------------------------------------------------------------


def test_hard_delete_by_admin(client: TestClient, pg: pg_connection) -> None:
    """Admin-only: the identifier must match; the Issue and its children are gone."""
    register_admin(client)
    team = _create_team(client)
    parent = _create_issue(client, team["id"], "Parent")
    child = _create_issue(client, team["id"], "Child")
    _set_parent(client, child, parent["id"])
    # Give the parent a Comment, a Label and an Activity trail to cascade.
    assert client.post(f"{API}/{parent['id']}/comments", json={"body": "Hello"}).status_code == 201
    label = client.post(
        f"/api/v1/teams/{team['id']}/labels", json={"name": "Bug", "color": "#ff0000"}
    ).json()
    client.patch(
        f"{API}/{parent['id']}",
        json={"updated_at": parent["updated_at"], "label_ids": [label["id"]]},
    )

    response = client.request("DELETE", f"{API}/{parent['id']}", json={"identifier": " ENG-1 "})
    assert response.status_code == 204

    assert client.get(f"{API}/{parent['id']}").status_code == 404
    assert client.get(f"{API}/{child['id']}").status_code == 404
    included = client.get(API, params={"team_id": team["id"], "include_archived": "true"}).json()
    # Parent and child are both gone from every view.
    assert included["issues"] == []
    with pg.cursor() as cur:
        for sql, params in (
            ("SELECT count(*) FROM comments WHERE issue_id = %s", (parent["id"],)),
            ("SELECT count(*) FROM issue_labels WHERE issue_id = %s", (parent["id"],)),
            (
                "SELECT count(*) FROM activity WHERE issue_id IN (%s, %s)",
                (parent["id"], child["id"]),
            ),
        ):
            cur.execute(sql, params)
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0


def test_hard_delete_works_for_archived_issue_in_archived_team(
    client: TestClient, pg: pg_connection
) -> None:
    """Admins can hard delete an archived Issue, even in an archived Team."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    _archive(client, issue["id"])
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team["id"],))

    assert (
        client.request("DELETE", f"{API}/{issue['id']}", json={"identifier": "ENG-1"}).status_code
        == 204
    )
    included = client.get(API, params={"team_id": team["id"], "include_archived": "true"}).json()
    assert included["issues"] == []


def test_hard_delete_with_wrong_identifier_is_400(client: TestClient) -> None:
    """A mismatched identifier is rejected before anything is deleted."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    child = _create_issue(client, team["id"], "Child")
    _set_parent(client, child, issue["id"])

    response = client.request("DELETE", f"{API}/{issue['id']}", json={"identifier": "ENG-999"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert client.get(f"{API}/{issue['id']}").status_code == 200
    assert client.get(f"{API}/{child['id']}").status_code == 200


def test_hard_delete_by_non_admin_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """The genuine 403: a Team owner (non-Admin) cannot hard delete."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    owner = make_user(email="owner@example.com")
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)

    response = other.request("DELETE", f"{API}/{issue['id']}", json={"identifier": "ENG-1"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get(f"{API}/{issue['id']}").status_code == 200


def test_hard_delete_by_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 (the Issue is not visible to them)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert (
        other.request("DELETE", f"{API}/{issue['id']}", json={"identifier": "ENG-1"}).status_code
        == 404
    )
