"""Tests for the Team label management endpoints (ticket 05)."""

from core.models.user import User
from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/issues"
LABELS = "/api/v1/teams/{team_id}/labels"
TEAM_A_MESSAGE = "Team not found"


def _create_team(client: TestClient, key: str = "ENG") -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": key})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str = "First") -> dict:
    response = client.post(API, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _create_label(client: TestClient, team_id: str, name: str, color: str = "#f2c94c") -> dict:
    response = client.post(LABELS.format(team_id=team_id), json={"name": name, "color": color})
    assert response.status_code == 201
    return response.json()


def _add_member(pg: pg_connection, user: User, team_id: str) -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'member')",
            (user.id, team_id),
        )


def test_owner_creates_and_lists_labels(client: TestClient) -> None:
    """An owner creates Labels; members can list them (brief §5.2)."""
    register_admin(client)
    team = _create_team(client)

    created = _create_label(client, team["id"], "bug", "#e5534b")
    assert created["name"] == "bug"
    assert created["color"] == "#e5534b"
    assert created["team_id"] == team["id"]

    listed = client.get(LABELS.format(team_id=team["id"])).json()
    assert [label["name"] for label in listed] == ["bug"]

    # A second Label: the list is case-insensitively by name.
    _create_label(client, team["id"], "Feature", "#4cb371")
    assert [label["name"] for label in client.get(LABELS.format(team_id=team["id"])).json()] == [
        "bug",
        "Feature",
    ]


def test_member_cannot_create_label_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Label management is owner-only: a member gets 403 (the ticket's 403)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user(email="member@example.com")
    _add_member(pg, member, team["id"])
    other = login_as(client, member)

    assert (
        other.post(
            LABELS.format(team_id=team["id"]), json={"name": "bug", "color": "#e5534b"}
        ).status_code
        == 403
    )


def test_member_cannot_edit_or_delete_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A member's PATCH/DELETE on a Label is a 403."""
    register_admin(client)
    team = _create_team(client)
    label = _create_label(client, team["id"], "bug")
    member = make_user(email="member@example.com")
    _add_member(pg, member, team["id"])
    other = login_as(client, member)

    assert (
        other.patch(
            f"{LABELS.format(team_id=team['id'])}/{label['id']}", json={"name": "defect"}
        ).status_code
        == 403
    )
    assert other.delete(f"{LABELS.format(team_id=team['id'])}/{label['id']}").status_code == 403
    # The Label is untouched.
    assert client.get(LABELS.format(team_id=team["id"])).json()[0]["name"] == "bug"


def test_non_member_label_endpoints_are_404(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 on the label endpoints (ticket 03/04 convention)."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)

    assert other.get(LABELS.format(team_id=team["id"])).status_code == 404
    assert (
        other.post(
            LABELS.format(team_id=team["id"]), json={"name": "bug", "color": "#e5534b"}
        ).status_code
        == 404
    )
    assert other.get("/api/v1/teams/00000000-0000-4000-8000-000000000000/labels").status_code == 404


def test_rename_and_recolor(client: TestClient) -> None:
    """An owner can rename and recolor a Label."""
    register_admin(client)
    team = _create_team(client)
    label = _create_label(client, team["id"], "bug")

    updated = client.patch(
        f"{LABELS.format(team_id=team['id'])}/{label['id']}",
        json={"name": "defect", "color": "#4cb371"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "defect"
    assert updated.json()["color"] == "#4cb371"
    assert updated.json()["id"] == label["id"]


def test_duplicate_label_name_is_409(client: TestClient) -> None:
    """Creating or renaming to an existing name in the same Team is a 409."""
    register_admin(client)
    team = _create_team(client)
    _create_label(client, team["id"], "bug")

    duplicate = client.post(
        LABELS.format(team_id=team["id"]), json={"name": "bug", "color": "#111111"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    label = client.get(LABELS.format(team_id=team["id"])).json()[0]
    rename = client.patch(
        f"{LABELS.format(team_id=team['id'])}/{label['id']}", json={"name": "bug"}
    )
    # Renaming to the Label's own name is a no-op, not a conflict.
    assert rename.status_code == 200

    _create_label(client, team["id"], "other")
    other = client.get(LABELS.format(team_id=team["id"])).json()[1]
    conflict = client.patch(
        f"{LABELS.format(team_id=team['id'])}/{other['id']}", json={"name": "bug"}
    )
    assert conflict.status_code == 409


def test_invalid_label_input_is_400(client: TestClient) -> None:
    """Whitespace-only names and non-hex colours are rejected by the domain."""
    register_admin(client)
    team = _create_team(client)

    blank = client.post(LABELS.format(team_id=team["id"]), json={"name": "   ", "color": "#e5534b"})
    assert blank.status_code == 400
    bad_color = client.post(
        LABELS.format(team_id=team["id"]), json={"name": "bug", "color": "#12345g"}
    )
    assert bad_color.status_code == 400


def test_label_of_other_team_is_404(client: TestClient) -> None:
    """A Label of another Team is invisible through this Team's URL."""
    register_admin(client)
    team_a = _create_team(client)
    team_b = _create_team(client, key="DSGN")
    label = _create_label(client, team_a["id"], "bug")

    patch = client.patch(f"{LABELS.format(team_id=team_b['id'])}/{label['id']}", json={"name": "x"})
    assert patch.status_code == 404
    assert client.delete(f"{LABELS.format(team_id=team_b['id'])}/{label['id']}").status_code == 404
    # The Label still exists in its own Team.
    assert len(client.get(LABELS.format(team_id=team_a["id"])).json()) == 1


def test_delete_label_removes_issue_links(client: TestClient) -> None:
    """Deleting a Label detaches it from Issues (no Activity rows)."""
    register_admin(client)
    team = _create_team(client)
    label = _create_label(client, team["id"], "bug")
    issue = _create_issue(client, team["id"])
    patched = client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "label_ids": [label["id"]]},
    )
    assert patched.status_code == 200
    assert [label["name"] for label in patched.json()["labels"]] == ["bug"]

    assert client.delete(f"{LABELS.format(team_id=team['id'])}/{label['id']}").status_code == 204
    detail = client.get(f"{API}/{issue['id']}").json()
    assert detail["labels"] == []
    activity = client.get(f"{API}/{issue['id']}/activity").json()
    assert [row["field"] for row in activity if row["field"] == "label_id"] == ["label_id"]


def test_deactivated_owner_label_create_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A deactivated owner gets 403 from the auth middleware."""
    register_admin(client)
    team = _create_team(client)
    # The bootstrap Admin is the owner; deactivate a separate owner instead.
    owner = make_user(email="owner@example.com", is_active=False)
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'owner')",
            (owner.id, team["id"]),
        )
    other = login_as(client, owner)
    response = other.post(
        LABELS.format(team_id=team["id"]), json={"name": "bug", "color": "#e5534b"}
    )
    assert response.status_code == 403


def test_patch_without_changes_is_400(client: TestClient) -> None:
    """An empty update is a 400."""
    register_admin(client)
    team = _create_team(client)
    label = _create_label(client, team["id"], "bug")
    response = client.patch(f"{LABELS.format(team_id=team['id'])}/{label['id']}", json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
