"""Tests for Team settings: edit, archive/restore and member management (ticket 08)."""

import uuid

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1"
TEAMS = f"{API}/teams"


def _create_team(client: TestClient, key: str = "ENG", name: str = "Engineering") -> dict:
    response = client.post(TEAMS, json={"name": name, "key": key})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str = "First") -> dict:
    response = client.post(f"{API}/issues", json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _add_member(pg: pg_connection, team_id: str, user_id: uuid.UUID, role: str = "member") -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, %s)",
            (str(user_id), str(team_id), role),
        )


def _archive_team_directly(pg: pg_connection, team_id: str) -> None:
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team_id,))


# ---------------------------------------------------------------------------
# Team detail (ticket line 1)
# ---------------------------------------------------------------------------


def test_team_detail_for_member(client: TestClient) -> None:
    """A member (or Admin) can fetch the Team detail."""
    register_admin(client)
    team = _create_team(client)
    response = client.get(f"{TEAMS}/{team['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Engineering"
    assert body["key"] == "ENG"
    assert body["description"] is None


def test_team_detail_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 on the Team detail (not 403)."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    assert login_as(client, outsider).get(f"{TEAMS}/{team['id']}").status_code == 404


def test_team_detail_archived_visible_to_admin_only(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Archived Teams stay visible to Admins (restore is reachable); others get 404."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    _archive_team_directly(pg, team["id"])

    assert client.get(f"{TEAMS}/{team['id']}").status_code == 200
    assert login_as(client, member).get(f"{TEAMS}/{team['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Team edit (ticket line 1)
# ---------------------------------------------------------------------------


def test_team_update_by_owner(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """The owner can rename the Team and set its description; the key is untouched."""
    register_admin(client)
    team = _create_team(client)
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)

    response = other.patch(
        f"{TEAMS}/{team['id']}",
        json={"name": "  Platform  ", "description": "Shipping things"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Platform"
    assert body["description"] == "Shipping things"
    assert body["key"] == "ENG"


def test_team_update_by_admin(client: TestClient) -> None:
    """Admins can edit any Team (workspace privilege)."""
    register_admin(client)
    team = _create_team(client)
    response = client.patch(f"{TEAMS}/{team['id']}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_team_update_clears_description(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """An explicit null clears the description."""
    register_admin(client)
    team = _create_team(client)
    client.patch(f"{TEAMS}/{team['id']}", json={"description": "hello"})
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)
    response = other.patch(f"{TEAMS}/{team['id']}", json={"description": None})
    assert response.status_code == 200
    assert response.json()["description"] is None


def test_team_update_member_forbidden(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A non-owner member is the genuine 403 (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    assert (
        login_as(client, member).patch(f"{TEAMS}/{team['id']}", json={"name": "Nope"}).status_code
        == 403
    )


def test_team_update_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 on Team edits."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    assert (
        login_as(client, outsider).patch(f"{TEAMS}/{team['id']}", json={"name": "Nope"}).status_code
        == 404
    )


def test_team_update_archived_is_403(client: TestClient, pg: pg_connection) -> None:
    """Editing an archived Team is a write and 403s."""
    register_admin(client)
    team = _create_team(client)
    _archive_team_directly(pg, team["id"])
    assert client.patch(f"{TEAMS}/{team['id']}", json={"name": "Nope"}).status_code == 403


def test_team_update_invalid_name_is_400(client: TestClient) -> None:
    """Overlong names 422 at the schema, blank names 400 in the service."""
    register_admin(client)
    team = _create_team(client)
    assert client.patch(f"{TEAMS}/{team['id']}", json={"name": "x" * 101}).status_code == 422
    assert client.patch(f"{TEAMS}/{team['id']}", json={"name": "   "}).status_code == 400


def test_team_update_nothing_sent_is_400(client: TestClient) -> None:
    """An empty payload is a no-op (400, the label convention)."""
    register_admin(client)
    team = _create_team(client)
    assert client.patch(f"{TEAMS}/{team['id']}", json={}).status_code == 400


def test_team_update_description_over_cap_is_422(client: TestClient) -> None:
    """Descriptions over the 5,000-character cap are 422."""
    register_admin(client)
    team = _create_team(client)
    response = client.patch(f"{TEAMS}/{team['id']}", json={"description": "x" * 5001})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Archive / restore (ticket lines 1 and 5)
# ---------------------------------------------------------------------------


def test_archive_by_admin_hides_the_team(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Archiving sets archived_at, hides the Team from members but not Admins."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)

    response = client.post(f"{TEAMS}/{team['id']}/archive")
    assert response.status_code == 200
    assert response.json()["archived_at"] is not None

    assert team["id"] in [t["id"] for t in client.get(TEAMS).json()]  # Admin still sees it
    other = login_as(client, member)
    assert team["id"] not in [t["id"] for t in other.get(TEAMS).json()]


def test_archive_by_owner_and_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Owners and members cannot archive a Team (Admin only)."""
    register_admin(client)
    team = _create_team(client)
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    member = make_user()
    _add_member(pg, team["id"], member.id)
    assert login_as(client, owner).post(f"{TEAMS}/{team['id']}/archive").status_code == 403
    assert login_as(client, member).post(f"{TEAMS}/{team['id']}/archive").status_code == 403


def test_archive_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 on archive."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    assert login_as(client, outsider).post(f"{TEAMS}/{team['id']}/archive").status_code == 404


def test_double_archive_is_404(client: TestClient) -> None:
    """Archiving an already-archived Team is a 404."""
    register_admin(client)
    team = _create_team(client)
    assert client.post(f"{TEAMS}/{team['id']}/archive").status_code == 200
    assert client.post(f"{TEAMS}/{team['id']}/archive").status_code == 404


def test_restore_by_admin(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """Restore is the Admin's counterpart of archive."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    client.post(f"{TEAMS}/{team['id']}/archive")

    response = client.post(f"{TEAMS}/{team['id']}/restore")
    assert response.status_code == 200
    assert response.json()["archived_at"] is None
    other = login_as(client, member)
    assert team["id"] in [t["id"] for t in other.get(TEAMS).json()]


def test_restore_non_archived_is_400(client: TestClient) -> None:
    """Restoring a non-archived Team is a 400."""
    register_admin(client)
    team = _create_team(client)
    response = client.post(f"{TEAMS}/{team['id']}/restore")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_restore_by_non_admin_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Owners cannot restore an archived Team (Admin only)."""
    register_admin(client)
    team = _create_team(client)
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    _archive_team_directly(pg, team["id"])
    assert login_as(client, owner).post(f"{TEAMS}/{team['id']}/restore").status_code == 403


def test_archived_team_rejects_issue_creation(client: TestClient, pg: pg_connection) -> None:
    """Ticket line 5: no Issues can be created in an archived Team."""
    register_admin(client)
    team = _create_team(client)
    _archive_team_directly(pg, team["id"])
    response = client.post(f"{API}/issues", json={"team_id": team["id"], "title": "Nope"})
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Team is archived"


def test_archived_team_hides_issue_views(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Hidden everywhere: Issue list/detail, Board States and members are 404."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user()
    _add_member(pg, team["id"], member.id)
    _archive_team_directly(pg, team["id"])

    assert client.get(f"{API}/issues", params={"team_id": team["id"]}).status_code == 404
    assert client.get(f"{API}/issues/{issue['id']}").status_code == 404
    assert client.get(f"{API}/issues/{issue['id']}/activity").status_code == 404
    assert client.get(f"{TEAMS}/{team['id']}/states").status_code == 404
    assert client.get(f"{TEAMS}/{team['id']}/members").status_code == 404
    assert client.get(f"{TEAMS}/{team['id']}/labels").status_code == 404
    other = login_as(client, member)
    assert other.get(f"{API}/issues", params={"team_id": team["id"]}).status_code == 404


# ---------------------------------------------------------------------------
# Members (ticket lines 2 and 5)
# ---------------------------------------------------------------------------


def test_add_member_by_owner_and_admin(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Existing Users join as members (201 + the Membership)."""
    register_admin(client)
    team = _create_team(client)
    new_member = make_user()
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)

    response = other.post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(new_member.id)})
    assert response.status_code == 201
    assert response.json()["id"] == str(new_member.id)
    assert response.json()["role"] == "member"

    admin_add = client.post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(owner.id)})
    # The owner is already a member: the Admin hit is a 409, so use a fresh User.
    assert admin_add.status_code == 409
    fresh = make_user()
    assert (
        client.post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(fresh.id)}).status_code
        == 201
    )


def test_add_member_by_plain_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A non-owner member cannot add members (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    candidate = make_user()
    assert (
        login_as(client, member)
        .post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(candidate.id)})
        .status_code
        == 403
    )


def test_add_member_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 on member add."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    candidate = make_user()
    assert (
        login_as(client, outsider)
        .post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(candidate.id)})
        .status_code
        == 404
    )


def test_add_member_validation(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """Already a member → 409, deactivated → 400, unknown → 404."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    deactivated = make_user(is_active=False)
    unknown = uuid.uuid4()

    assert (
        client.post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(member.id)}).status_code
        == 409
    )
    assert (
        client.post(
            f"{TEAMS}/{team['id']}/members", json={"user_id": str(deactivated.id)}
        ).status_code
        == 400
    )
    assert (
        client.post(f"{TEAMS}/{team['id']}/members", json={"user_id": str(unknown)}).status_code
        == 404
    )


def test_add_member_into_archived_team_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Adding members into an archived Team is a write and 403s."""
    register_admin(client)
    team = _create_team(client)
    candidate = make_user()
    _archive_team_directly(pg, team["id"])
    assert (
        client.post(
            f"{TEAMS}/{team['id']}/members", json={"user_id": str(candidate.id)}
        ).status_code
        == 403
    )


def test_change_role_to_owner(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """The owner can promote a member; the Membership echoes the role."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    other = login_as(client, owner)

    response = other.patch(f"{TEAMS}/{team['id']}/members/{member.id!s}", json={"role": "owner"})
    assert response.status_code == 200
    assert response.json()["role"] == "owner"


def test_change_role_to_same_is_400(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Re-sending the current role is a no-op (400, the label convention)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    assert (
        client.patch(
            f"{TEAMS}/{team['id']}/members/{member.id!s}", json={"role": "member"}
        ).status_code
        == 400
    )


def test_change_role_last_owner_is_422(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Demoting the last owner is a rule violation — even for the owner (self)."""
    register_admin(client)
    team = _create_team(client)
    admin_id = client.get(f"{API}/auth/me").json()["id"]
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    # The creator Admin is the default owner: step down first so the new
    # owner becomes the last one.
    assert (
        client.patch(
            f"{TEAMS}/{team['id']}/members/{admin_id}", json={"role": "member"}
        ).status_code
        == 200
    )
    other = login_as(client, owner)

    self_demotion = other.patch(
        f"{TEAMS}/{team['id']}/members/{owner.id!s}", json={"role": "member"}
    )
    assert self_demotion.status_code == 422
    assert self_demotion.json()["error"]["code"] == "rule_violation"

    # The Admin (a plain member now, but still an Admin) is blocked by the
    # invariant, not by the role check.
    admin_demotion = client.patch(
        f"{TEAMS}/{team['id']}/members/{owner.id!s}", json={"role": "member"}
    )
    assert admin_demotion.status_code == 422


def test_change_role_allowed_while_another_owner_remains(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """An owner may demote themselves while another owner remains."""
    register_admin(client)
    team = _create_team(client)
    owner_a = make_user()
    _add_member(pg, team["id"], owner_a.id, role="owner")
    owner_b = make_user()
    _add_member(pg, team["id"], owner_b.id, role="owner")
    other = login_as(client, owner_a)

    assert (
        other.patch(
            f"{TEAMS}/{team['id']}/members/{owner_a.id!s}", json={"role": "member"}
        ).status_code
        == 200
    )


def test_change_role_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A non-owner member cannot change roles (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    assert (
        login_as(client, member)
        .patch(f"{TEAMS}/{team['id']}/members/{member.id!s}", json={"role": "owner"})
        .status_code
        == 403
    )


def test_change_role_unknown_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Changing a non-member's role is a 404."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    assert (
        client.patch(
            f"{TEAMS}/{team['id']}/members/{outsider.id!s}", json={"role": "owner"}
        ).status_code
        == 404
    )


def test_remove_member(client: TestClient, pg: pg_connection, make_user: MakeUser) -> None:
    """Removal is a 204; the member is gone from the list (ADR 0013)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)

    response = client.delete(f"{TEAMS}/{team['id']}/members/{member.id!s}")
    assert response.status_code == 204
    ids = [m["id"] for m in client.get(f"{TEAMS}/{team['id']}/members").json()]
    assert str(member.id) not in ids


def test_remove_last_owner_is_422(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Removing the last owner is a 422 and the owner survives."""
    register_admin(client)
    team = _create_team(client)
    admin_id = client.get(f"{API}/auth/me").json()["id"]
    owner = make_user()
    _add_member(pg, team["id"], owner.id, role="owner")
    client.patch(f"{TEAMS}/{team['id']}/members/{admin_id}", json={"role": "member"})
    assert client.delete(f"{TEAMS}/{team['id']}/members/{owner.id!s}").status_code == 422
    # The owner survived: the removal was refused.
    roles = {m["id"]: m["role"] for m in client.get(f"{TEAMS}/{team['id']}/members").json()}
    assert roles[str(owner.id)] == "owner"


def test_remove_self_with_another_owner_is_204(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Self-removal is allowed while another owner remains."""
    register_admin(client)
    team = _create_team(client)
    owner_a = make_user()
    _add_member(pg, team["id"], owner_a.id, role="owner")
    owner_b = make_user()
    _add_member(pg, team["id"], owner_b.id, role="owner")
    other = login_as(client, owner_a)
    assert other.delete(f"{TEAMS}/{team['id']}/members/{owner_a.id!s}").status_code == 204


def test_remove_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A non-owner member cannot remove members (ticket line 5)."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    assert (
        login_as(client, member).delete(f"{TEAMS}/{team['id']}/members/{member.id!s}").status_code
        == 403
    )


def test_remove_unknown_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Removing a non-member is a 404."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    assert client.delete(f"{TEAMS}/{team['id']}/members/{outsider.id!s}").status_code == 404


# ---------------------------------------------------------------------------
# Member candidates (the add picker)
# ---------------------------------------------------------------------------


def test_member_candidates_lists_active_non_members(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Candidates are the active Users who are not yet members."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    active = make_user()
    deactivated = make_user(is_active=False)

    candidates = client.get(f"{TEAMS}/{team['id']}/member-candidates").json()
    ids = [c["id"] for c in candidates]
    # The Admin (team creator), the member and deactivated Users are excluded.
    assert ids == [str(active.id)]
    assert str(deactivated.id) not in ids
    assert str(member.id) not in ids
    candidate = next(c for c in candidates if c["id"] == str(active.id))
    assert candidate["email"] == active.email
    assert candidate["display_name"] != ""


def test_member_candidates_by_member_is_403(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """A non-owner member cannot list candidates."""
    register_admin(client)
    team = _create_team(client)
    member = make_user()
    _add_member(pg, team["id"], member.id)
    assert (
        login_as(client, member).get(f"{TEAMS}/{team['id']}/member-candidates").status_code == 403
    )


def test_member_candidates_non_member_is_404(client: TestClient, make_user: MakeUser) -> None:
    """Non-members get 404 on candidates."""
    register_admin(client)
    team = _create_team(client)
    outsider = make_user()
    assert (
        login_as(client, outsider).get(f"{TEAMS}/{team['id']}/member-candidates").status_code == 404
    )
