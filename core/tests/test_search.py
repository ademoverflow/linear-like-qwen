"""Tests for the global Issue search (ticket 09, brief §7.2.8, §9)."""

from fastapi.testclient import TestClient
from httpx import Response

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    MakeUser,
    login_as,
    register_admin,
)

SEARCH = "/api/v1/search"
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


def _search(client: TestClient, q: str | None) -> Response:
    params = {} if q is None else {"q": q}
    return client.get(SEARCH, params=params)


def test_search_returns_hits_with_team_fields(client: TestClient) -> None:
    """A hit is the Issue response plus the Team's key and name."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Set up the core loop")

    body = _search(client, "core loop").json()
    assert set(body) == {"issues"}
    assert len(body["issues"]) == 1
    hit = body["issues"][0]
    assert hit["identifier"] == "ENG-1"
    assert hit["team_key"] == "ENG"
    assert hit["team_name"] == "Engineering"
    assert hit["team_id"] == team["id"]


def test_search_matches_identifier_full_and_partial(client: TestClient) -> None:
    """Identifier matches: the full form, a substring, and a bare number."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    first = _create_issue(client, team["id"], "Alpha")
    _create_issue(client, team["id"], "Beta")
    _create_issue(client, team["id"], "Gamma")

    for query in ("ENG-1", "NG-1", "1"):
        body = _search(client, query).json()
        assert [issue["id"] for issue in body["issues"]] == [first["id"]], query


def test_search_bare_number_matches_all_numbers_containing_it(client: TestClient) -> None:
    """A bare number matches every identifier whose number contains it."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    titles = [
        "Alpha",
        "Beta",
        "Gamma",
        "Delta",
        "Epsilon",
        "Zeta",
        "Eta",
        "Theta",
        "Iota",
        "Kappa",
        "Lambda",
    ]
    ids = [_create_issue(client, team["id"], title)["id"] for title in titles]

    # Numbers 1..11: the character "1" occurs in ENG-1, ENG-10 and ENG-11.
    body = _search(client, "1").json()
    assert {issue["id"] for issue in body["issues"]} == {ids[0], ids[9], ids[10]}


def test_search_title_match_is_case_insensitive(client: TestClient) -> None:
    """Title matching is case-insensitive (ILIKE)."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Ship the SEARCH feature")

    for query in ("search", "SEARCH", "SeaRch"):
        body = _search(client, query).json()
        assert len(body["issues"]) == 1, query


def test_search_identifier_match_comes_before_title_match(client: TestClient) -> None:
    """Identifier matches are ordered before title matches."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    by_title = _create_issue(client, team["id"], "Fix ENG-2 flakiness")
    by_identifier = _create_issue(client, team["id"], "Something else")

    body = _search(client, "ENG-2").json()
    assert [issue["id"] for issue in body["issues"]] == [by_identifier["id"], by_title["id"]]


def test_search_excludes_archived_issues(client: TestClient) -> None:
    """Archived Issues never appear in search results."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    archived = _create_issue(client, team["id"], "Ghost in the archive")
    _archive_issue(client, archived)

    assert _search(client, "ghost").json()["issues"] == []


def test_search_excludes_archived_team_issues(client: TestClient) -> None:
    """Issues of an archived Team are out of scope for search."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Hidden in the archive")
    response = client.post(f"/api/v1/teams/{team['id']}/archive")
    assert response.status_code == 200

    assert _search(client, "hidden").json()["issues"] == []


def test_search_is_scoped_to_the_users_own_teams(client: TestClient, make_user: MakeUser) -> None:
    """An Admin does NOT search Teams they are not a member of.

    Team X: alice owns it, the Admin removed themselves. Issues of X are
    invisible to the Admin (even as workspace Admin) and visible to alice.
    """
    me = register_admin(client)
    team_x = _create_team(client, "Alpha", "ALP")
    alice = make_user(email="alice@example.com")
    _add_member(client, team_x["id"], str(alice.id))
    _set_member_role(client, team_x["id"], str(alice.id), "owner")
    _remove_member(client, team_x["id"], str(me["id"]))

    secret = _create_issue(client, team_x["id"], "Secret project")
    assert secret["creator_id"] == me["id"]  # the Admin created it before leaving

    login_as(client, alice)
    assert [issue["id"] for issue in _search(client, "secret").json()["issues"]] == [secret["id"]]

    client.cookies.clear()
    _login_admin(client)
    assert _search(client, "secret").json()["issues"] == []


def test_search_returns_all_teams_of_the_user(client: TestClient) -> None:
    """Search spans every Team the user belongs to, grouped fields per hit."""
    register_admin(client)
    team_a = _create_team(client, "Engineering", "ENG")
    team_b = _create_team(client, "Design", "DSGN")
    in_a = _create_issue(client, team_a["id"], "Shared word")
    in_b = _create_issue(client, team_b["id"], "Shared word")

    body = _search(client, "shared").json()
    assert {issue["id"] for issue in body["issues"]} == {in_a["id"], in_b["id"]}
    by_key = {issue["team_key"]: issue for issue in body["issues"]}
    assert set(by_key) == {"ENG", "DSGN"}
    assert by_key["ENG"]["team_name"] == "Engineering"
    assert by_key["DSGN"]["team_name"] == "Design"


def test_search_caps_results_at_fifty(client: TestClient) -> None:
    """The fixed cap is 50 hits (no cursor, no limit param)."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    for index in range(55):
        _create_issue(client, team["id"], f"Searchcap {index}")

    body = _search(client, "searchcap").json()
    assert len(body["issues"]) == 50
    assert set(body) == {"issues"}


def test_search_requires_a_query(client: TestClient) -> None:
    """Missing / empty / blank q is a 400 (envelope)."""
    register_admin(client)
    for params in (None, {"q": ""}, {"q": "   "}):
        response = client.get(SEARCH, params=params)
        assert response.status_code == 400, params
        assert response.json()["error"]["message"] == "Search query is required"


def test_search_user_without_memberships_gets_empty(
    client: TestClient, make_user: MakeUser
) -> None:
    """A user with no Teams searches nothing (200 empty, no 404)."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Visible only to members")
    stranger = make_user(email="stranger@example.com")
    login_as(client, stranger)

    assert _search(client, "visible").json() == {"issues": []}


def test_search_deactivated_user_gets_403(client: TestClient, make_user: MakeUser) -> None:
    """The deactivated-User middleware 403 applies to search (as usual)."""
    register_admin(client)
    team = _create_team(client, "Engineering", "ENG")
    _create_issue(client, team["id"], "Anything at all")
    deactivated = make_user(email="gone@example.com", is_active=False)
    login_as(client, deactivated)

    assert _search(client, "anything").status_code == 403
