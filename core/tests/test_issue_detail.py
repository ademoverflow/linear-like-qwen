"""Tests for Issue detail, editing and Activity endpoints (ticket 03)."""

import uuid

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


def _add_member(pg: pg_connection, team_id: str, user_id: str, role: str = "member") -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, %s)",
            (user_id, team_id, role),
        )


def test_get_issue_detail(client: TestClient) -> None:
    """A member can fetch the Issue detail; the parent fields start empty."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Set up CI")
    response = client.get(f"{API}/{issue['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["identifier"] == "ENG-1"
    assert body["title"] == "Set up CI"
    assert body["description"] is None
    assert body["state_name"] == "Backlog"
    assert body["parent_identifier"] is None
    assert body["parent_title"] is None
    assert body["updated_at"] is not None


def test_get_issue_detail_includes_parent(client: TestClient) -> None:
    """The detail shows the parent's identifier and title once set."""
    register_admin(client)
    team = _create_team(client)
    parent = _create_issue(client, team["id"], "Parent work")
    child = _create_issue(client, team["id"], "Child work")
    patched = client.patch(
        f"{API}/{child['id']}",
        json={"updated_at": child["updated_at"], "parent_id": parent["id"]},
    )
    assert patched.status_code == 200
    body = client.get(f"{API}/{child['id']}").json()
    assert body["parent_identifier"] == "ENG-1"
    assert body["parent_title"] == "Parent work"


def test_get_unknown_issue_is_404(client: TestClient) -> None:
    """An unknown Issue id is a 404, not a 500."""
    register_admin(client)
    assert client.get(f"{API}/{uuid.uuid4()}").status_code == 404


def test_non_member_cannot_view_or_edit_issue(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 (not 403) on detail, edit and Activity (ticket 03)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.get(f"{API}/{issue['id']}").status_code == 404
    assert (
        other.patch(
            f"{API}/{issue['id']}",
            json={"updated_at": issue["updated_at"], "title": "Sneaky"},
        ).status_code
        == 404
    )
    assert other.get(f"{API}/{issue['id']}/activity").status_code == 404


def test_patch_updates_fields_and_writes_activity(client: TestClient, pg: pg_connection) -> None:
    """Each changed field emits exactly one Activity row with from/to values."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Old title")
    response = client.patch(
        f"{API}/{issue['id']}",
        json={
            "updated_at": issue["updated_at"],
            "title": "New title",
            "description": "# Hello",
            "priority": "high",
            "estimate": 3,
            "due_date": "2026-09-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["description"] == "# Hello"
    assert body["priority"] == "high"
    assert body["estimate"] == 3
    assert body["due_date"] == "2026-09-01"
    assert body["updated_at"] != issue["updated_at"]
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.updated' ORDER BY seq",
            (issue["id"],),
        )
        rows = cur.fetchall()
    assert rows == [
        ("title", "Old title", "New title"),
        ("description", None, "# Hello"),
        ("priority", "none", "high"),
        ("due_date", None, "2026-09-01"),
        ("estimate", None, "3"),
    ]


def test_patch_same_value_writes_no_activity(client: TestClient, pg: pg_connection) -> None:
    """Resending the current value changes nothing and writes no Activity."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Stable")
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "title": "Stable"},
    )
    assert response.status_code == 200
    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM activity WHERE issue_id = %s", (issue["id"],))
        count_row = cur.fetchone()
    assert count_row is not None
    count = count_row[0]
    assert count == 1  # only issue.created
    assert client.get(f"{API}/{issue['id']}").json()["updated_at"] == issue["updated_at"]


def test_patch_stale_updated_at_returns_409(client: TestClient) -> None:
    """A stale last-seen updated_at is a 409 and changes nothing (ADR 0008)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Racy")
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": "2000-01-01T00:00:00Z", "title": "Clobbered"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert client.get(f"{API}/{issue['id']}").json()["title"] == "Racy"


def test_patch_assignee_must_be_team_member(client: TestClient, make_user: MakeUser) -> None:
    """Assigning a user who is not a Team member is a 400."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    outsider = make_user(email="outsider@example.com")
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "assignee_id": str(outsider.id)},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Assignee must be a member of the Issue's Team"


def test_patch_assignee_member_succeeds(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A Team member can be assigned; Activity stores their display name."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user(email="alice@example.com")
    with pg.cursor() as cur:
        cur.execute("UPDATE users SET display_name = %s WHERE id = %s", ("Alice", member.id))
    _add_member(pg, team["id"], str(member.id))
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "assignee_id": str(member.id)},
    )
    assert response.status_code == 200
    assert response.json()["assignee_id"] == str(member.id)
    assert response.json()["assignee_display_name"] == "Alice"
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.updated'",
            (issue["id"],),
        )
        row = cur.fetchone()
    assert row == ("assignee_id", None, "Alice")


def test_patch_parent_rules(client: TestClient) -> None:
    """Parent must be same Team, one level deep, not self (ticket 03)."""
    register_admin(client)
    team = _create_team(client)
    first = _create_issue(client, team["id"], "One")
    second = _create_issue(client, team["id"], "Two")

    # Self-parent is rejected.
    response = client.patch(
        f"{API}/{first['id']}",
        json={"updated_at": first["updated_at"], "parent_id": first["id"]},
    )
    assert response.status_code == 400

    # Cross-team parent is rejected.
    other_team = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    other_issue = _create_issue(client, other_team["id"], "Elsewhere")
    response = client.patch(
        f"{API}/{first['id']}",
        json={"updated_at": first["updated_at"], "parent_id": other_issue["id"]},
    )
    assert response.status_code == 400

    # One level deep: second has parent first, so first cannot take second as parent.
    ok = client.patch(
        f"{API}/{second['id']}",
        json={"updated_at": second["updated_at"], "parent_id": first["id"]},
    )
    assert ok.status_code == 200
    assert ok.json()["parent_id"] == first["id"]
    response = client.patch(
        f"{API}/{first['id']}",
        json={"updated_at": first["updated_at"], "parent_id": second["id"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == (
        "Parent must be a non-archived Issue of the same Team, one level deep"
    )


def test_patch_parent_activity_value(client: TestClient, pg: pg_connection) -> None:
    """Setting a valid parent writes an Activity row with the parent identifier."""
    register_admin(client)
    team = _create_team(client)
    parent = _create_issue(client, team["id"], "Parent")
    child = _create_issue(client, team["id"], "Child")
    response = client.patch(
        f"{API}/{child['id']}",
        json={"updated_at": child["updated_at"], "parent_id": parent["id"]},
    )
    assert response.status_code == 200
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.updated'",
            (child["id"],),
        )
        row = cur.fetchone()
    assert row == ("parent_id", None, "ENG-1")


def test_patch_clears_assignee_and_parent(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Clearing a field stores the old value and a null to_value."""
    register_admin(client)
    team = _create_team(client)
    parent = _create_issue(client, team["id"], "Parent")
    child = _create_issue(client, team["id"], "Child")
    member = make_user(email="alice@example.com")
    with pg.cursor() as cur:
        cur.execute("UPDATE users SET display_name = %s WHERE id = %s", ("Alice", member.id))
    _add_member(pg, team["id"], str(member.id))
    seeded = client.patch(
        f"{API}/{child['id']}",
        json={
            "updated_at": child["updated_at"],
            "assignee_id": str(member.id),
            "parent_id": parent["id"],
        },
    )
    assert seeded.status_code == 200
    response = client.patch(
        f"{API}/{child['id']}",
        json={
            "updated_at": seeded.json()["updated_at"],
            "assignee_id": None,
            "parent_id": None,
        },
    )
    assert response.status_code == 200
    assert response.json()["assignee_id"] is None
    assert response.json()["parent_id"] is None
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.updated' ORDER BY seq",
            (child["id"],),
        )
        rows = cur.fetchall()
    assert rows[-2:] == [
        ("assignee_id", "Alice", None),
        ("parent_id", "ENG-1", None),
    ]


def test_list_activity_oldest_first(client: TestClient) -> None:
    """The Activity feed lists the Issue's rows chronologically, oldest first."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Tracked")
    client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "priority": "urgent"},
    )
    second = client.get(f"{API}/{issue['id']}").json()
    client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": second["updated_at"], "estimate": 5},
    )
    response = client.get(f"{API}/{issue['id']}/activity")
    assert response.status_code == 200
    rows = response.json()
    assert [row["kind"] for row in rows] == ["issue.created", "issue.updated", "issue.updated"]
    assert rows[0]["actor_display_name"] == "admin"
    assert rows[1]["field"] == "priority"
    assert (rows[1]["from_value"], rows[1]["to_value"]) == ("none", "urgent")
    assert rows[2]["field"] == "estimate"
    assert (rows[2]["from_value"], rows[2]["to_value"]) == (None, "5")


def test_archived_issue_is_hidden(client: TestClient, pg: pg_connection) -> None:
    """Archived Issues are invisible to detail, edit and Activity (404)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    with pg.cursor() as cur:
        cur.execute("UPDATE issues SET archived_at = now() WHERE id = %s", (issue["id"],))
    assert client.get(f"{API}/{issue['id']}").status_code == 404
    assert (
        client.patch(
            f"{API}/{issue['id']}", json={"updated_at": issue["updated_at"], "title": "x"}
        ).status_code
        == 404
    )
    assert client.get(f"{API}/{issue['id']}/activity").status_code == 404


def test_patch_invalid_inputs(client: TestClient) -> None:
    """Invalid field values are rejected (400 domain, 422 schema)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Valid")
    base = {"updated_at": issue["updated_at"]}

    assert client.patch(f"{API}/{issue['id']}", json={**base, "title": "   "}).status_code == 400
    assert client.patch(f"{API}/{issue['id']}", json={**base, "estimate": 22}).status_code == 422
    assert (
        client.patch(f"{API}/{issue['id']}", json={**base, "priority": "critical"}).status_code
        == 422
    )
    assert (
        client.patch(f"{API}/{issue['id']}", json={**base, "description": "x" * 50_001}).status_code
        == 422
    )


def test_patch_null_title_is_400(client: TestClient) -> None:
    """An explicit null title is a 400 (Title is required), not a 500."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"], "Keep me")
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "title": None},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Title is required"
    assert client.get(f"{API}/{issue['id']}").json()["title"] == "Keep me"


def test_team_members_endpoint(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """Members see the Team's members with roles; non-members get 404."""
    register_admin(client)
    team = _create_team(client)
    member = make_user(email="alice@example.com")
    with pg.cursor() as cur:
        cur.execute("UPDATE users SET display_name = %s WHERE id = %s", ("Alice", member.id))
    _add_member(pg, team["id"], str(member.id))

    response = client.get(MEMBERS.format(team_id=team["id"]))
    assert response.status_code == 200
    rows = response.json()
    assert [(row["display_name"], row["role"]) for row in rows] == [
        ("Alice", "member"),
        ("admin", "owner"),
    ]

    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.get(MEMBERS.format(team_id=team["id"])).status_code == 404


def _create_label(client: TestClient, team_id: str, name: str) -> dict:
    response = client.post(
        f"/api/v1/teams/{team_id}/labels", json={"name": name, "color": "#111111"}
    )
    assert response.status_code == 201
    return response.json()


def test_patch_label_ids_adds_and_removes_with_activity(
    client: TestClient, pg: pg_connection
) -> None:
    """label_ids is a full-set replace; one Activity row per added/removed label."""
    register_admin(client)
    team = _create_team(client)
    label_a = _create_label(client, team["id"], "beta")
    label_b = _create_label(client, team["id"], "alpha")
    issue = _create_issue(client, team["id"])

    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": [label_a["id"], label_b["id"]]},
    )
    assert response.status_code == 200
    assert sorted(label["name"] for label in response.json()["labels"]) == ["alpha", "beta"]
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, from_value, to_value FROM activity "
            "WHERE issue_id = %s AND kind = 'issue.updated' ORDER BY seq",
            (issue["id"],),
        )
        rows = cur.fetchall()
    # Added rows first, name-ordered.
    assert rows == [("label_id", None, "alpha"), ("label_id", None, "beta")]

    issue = response.json()
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": [label_b["id"]]},
    )
    assert [label["name"] for label in response.json()["labels"]] == ["alpha"]
    with pg.cursor() as cur:
        cur.execute(
            "SELECT from_value, to_value FROM activity "
            "WHERE issue_id = %s AND field = 'label_id' AND from_value IS NOT NULL "
            "ORDER BY seq",
            (issue["id"],),
        )
        rows = cur.fetchall()
    assert rows == [("beta", None)]

    # An empty list clears all Labels (with one removal row).
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": []},
    )
    assert response.json()["labels"] == []

    # Re-sending the same set is a no-op (no new Activity rows).
    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": response.json()["updated_at"], "label_ids": []},
    )
    assert response.status_code == 200
    with pg.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM activity WHERE issue_id = %s AND field = 'label_id'",
            (issue["id"],),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == 4


def test_patch_label_of_other_team_is_400(client: TestClient) -> None:
    """A Label from another Team is rejected (400) and nothing changes."""
    register_admin(client)
    team_a = _create_team(client)
    team_b = client.post("/api/v1/teams", json={"name": "Design", "key": "DSGN"}).json()
    other_label = _create_label(client, team_b["id"], "x")
    issue = _create_issue(client, team_a["id"])

    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": [other_label["id"]]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert client.get(f"{API}/{issue['id']}").json()["labels"] == []


def test_patch_unknown_label_is_400(client: TestClient) -> None:
    """An unknown Label id is rejected (400)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])

    response = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": [str(uuid.uuid4())]},
    )
    assert response.status_code == 400
    assert client.get(f"{API}/{issue['id']}").json()["labels"] == []


def test_member_can_set_label_ids(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A plain Team member (non-Admin) can add and remove Labels on an Issue."""
    register_admin(client)
    team = _create_team(client)
    member = make_user(email="member@example.com")
    _add_member(pg, team["id"], str(member.id))
    label = _create_label(client, team["id"], "bug")
    issue = _create_issue(client, team["id"])
    other = login_as(client, member)

    response = other.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": [label["id"]]},
    )
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["labels"]] == ["bug"]
    with pg.cursor() as cur:
        cur.execute(
            "SELECT field, to_value FROM activity WHERE issue_id = %s AND field = %s",
            (issue["id"], "label_id"),
        )
        rows = cur.fetchall()
    assert rows == [("label_id", "bug")]
