"""Tests for My Issues: the cross-Team view without ``team_id`` (ticket 09, brief §6)."""

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    MakeUser,
    login_as,
    register_admin,
)

ISSUES = "/api/v1/issues"


def _login_admin(client: TestClient) -> None:
    """Log the bootstrap Admin back in (registration is closed after bootstrap)."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200


def _create_team(client: TestClient, name: str, key: str) -> dict:
    response = client.post("/api/v1/teams", json={"name": name, "key": key})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str) -> dict:
    response = client.post(ISSUES, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _patch_issue(client: TestClient, issue: dict, **fields: object) -> dict:
    response = client.patch(
        f"{ISSUES}/{issue['id']}", json={"updated_at": issue["updated_at"], **fields}
    )
    assert response.status_code == 200
    return response.json()


def _archive_issue(client: TestClient, issue: dict) -> dict:
    response = client.post(f"{ISSUES}/{issue['id']}/archive")
    assert response.status_code == 200
    return response.json()


def _add_member(client: TestClient, team_id: str, user_id: str) -> dict:
    response = client.post(f"/api/v1/teams/{team_id}/members", json={"user_id": user_id})
    assert response.status_code == 201
    return response.json()


def _set_member_role(client: TestClient, team_id: str, user_id: str, role: str) -> dict:
    response = client.patch(f"/api/v1/teams/{team_id}/members/{user_id}", json={"role": role})
    assert response.status_code == 200
    return response.json()


def _remove_member(client: TestClient, team_id: str, user_id: str) -> None:
    response = client.delete(f"/api/v1/teams/{team_id}/members/{user_id}")
    assert response.status_code == 204


def test_my_issues_aggregates_across_the_users_teams(client: TestClient) -> None:
    """Without team_id, the list spans every Team the user belongs to."""
    me = register_admin(client)
    team_a = _create_team(client, "Engineering", "ENG")
    team_b = _create_team(client, "Design", "DSGN")
    in_a = _create_issue(client, team_a["id"], "Alpha")
    in_b = _create_issue(client, team_b["id"], "Beta")
    _patch_issue(client, in_a, assignee_id=me["id"])
    _patch_issue(client, in_b, assignee_id=me["id"])
    unassigned = _create_issue(client, team_a["id"], "Gamma")

    body = client.get(ISSUES, params={"assignee_id": me["id"]}).json()
    assert {issue["id"] for issue in body["issues"]} == {in_a["id"], in_b["id"]}
    assert unassigned["id"] not in {issue["id"] for issue in body["issues"]}
    identifiers = {issue["identifier"] for issue in body["issues"]}
    assert identifiers == {"ENG-1", "DSGN-1"}


def test_my_issues_without_team_and_without_assignee_lists_all(client: TestClient) -> None:
    """The assignee is not forced: a bare cross-Team list shows every Issue."""
    register_admin(client)
    team_a = _create_team(client, "Engineering", "ENG")
    team_b = _create_team(client, "Design", "DSGN")
    for _ in range(2):
        _create_issue(client, team_a["id"], "Alpha")
        _create_issue(client, team_b["id"], "Beta")

    body = client.get(ISSUES).json()
    assert len(body["issues"]) == 4


def test_my_issues_only_lists_the_users_own_teams(client: TestClient, make_user: MakeUser) -> None:
    """Issues of a Team the user does not belong to are out of scope.

    Team ALP: alice owns it, the Admin removed themselves. An Issue of ALP
    assigned to alice appears for alice and is invisible to the Admin —
    even though the Admin is a workspace Admin (404-free personal view).
    """
    me = register_admin(client)
    team_alp = _create_team(client, "Alpha", "ALP")
    alice = make_user(email="alice@example.com")
    _add_member(client, team_alp["id"], str(alice.id))
    _set_member_role(client, team_alp["id"], str(alice.id), "owner")
    _remove_member(client, team_alp["id"], str(me["id"]))

    secret = _create_issue(client, team_alp["id"], "Secret project")
    _patch_issue(client, secret, assignee_id=str(alice.id))

    login_as(client, alice)
    body = client.get(ISSUES, params={"assignee_id": str(alice.id)}).json()
    assert [issue["id"] for issue in body["issues"]] == [secret["id"]]

    client.cookies.clear()
    _login_admin(client)
    body = client.get(ISSUES, params={"assignee_id": str(alice.id)}).json()
    assert body["issues"] == []


def test_my_issues_paginates_across_teams(client: TestClient) -> None:
    """Keyset pagination works on the cross-Team scope (page boundaries)."""
    me = register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    for index in range(12):
        issue = _create_issue(client, team["id"], f"Issue {index}")
        _patch_issue(client, issue, assignee_id=me["id"])

    first = client.get(ISSUES, params={"assignee_id": me["id"], "limit": 5}).json()
    assert len(first["issues"]) == 5
    assert first["next_cursor"] is not None

    second = client.get(
        ISSUES, params={"assignee_id": me["id"], "limit": 5, "cursor": first["next_cursor"]}
    ).json()
    assert len(second["issues"]) == 5
    assert second["next_cursor"] is not None

    third = client.get(
        ISSUES,
        params={"assignee_id": me["id"], "limit": 5, "cursor": second["next_cursor"]},
    ).json()
    assert len(third["issues"]) == 2
    assert third["next_cursor"] is None

    seen = {issue["id"] for page in (first, second, third) for issue in page["issues"]}
    assert len(seen) == 12


def test_my_issues_hides_archived_by_default(client: TestClient) -> None:
    """Archived Issues are hidden; include_archived lists them (cross-Team)."""
    me = register_admin(client)
    team_a = _create_team(client, "Engineering", "ENG")
    team_b = _create_team(client, "Design", "DSGN")
    archived = _create_issue(client, team_a["id"], "Archived one")
    active = _create_issue(client, team_b["id"], "Active one")
    _patch_issue(client, archived, assignee_id=me["id"])
    _patch_issue(client, active, assignee_id=me["id"])
    _archive_issue(client, archived)

    body = client.get(ISSUES, params={"assignee_id": me["id"]}).json()
    assert [issue["id"] for issue in body["issues"]] == [active["id"]]

    body = client.get(ISSUES, params={"assignee_id": me["id"], "include_archived": "true"}).json()
    assert {issue["id"] for issue in body["issues"]} == {archived["id"], active["id"]}


def test_my_issues_excludes_archived_teams(client: TestClient) -> None:
    """Issues of archived Teams are out of the cross-Team scope entirely."""
    me = register_admin(client)
    team_a = _create_team(client, "Engineering", "ENG")
    team_b = _create_team(client, "Design", "DSGN")
    in_archived_team = _create_issue(client, team_b["id"], "Gone team issue")
    _patch_issue(client, in_archived_team, assignee_id=me["id"])
    _create_issue(client, team_a["id"], "Kept issue")
    response = client.post(f"/api/v1/teams/{team_b['id']}/archive")
    assert response.status_code == 200

    # The only assigned Issue lived in the archived Team: the view is empty.
    body = client.get(ISSUES, params={"assignee_id": me["id"]}).json()
    assert body["issues"] == []


def test_my_issues_user_without_teams_gets_empty_page(
    client: TestClient, make_user: MakeUser
) -> None:
    """A user with zero Teams gets a 200 empty page (no 404)."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Something")
    stranger = make_user(email="stranger@example.com")
    login_as(client, stranger)

    response = client.get(ISSUES)
    assert response.status_code == 200
    assert response.json() == {"issues": [], "next_cursor": None}


def test_my_issues_deactivated_user_gets_403(client: TestClient, make_user: MakeUser) -> None:
    """The deactivated-User middleware 403 applies to My Issues (as usual)."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Anything at all")
    deactivated = make_user(email="gone@example.com", is_active=False)
    login_as(client, deactivated)

    assert client.get(ISSUES).status_code == 403
