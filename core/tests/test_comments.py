"""Tests for the Comment endpoints (ticket 06, brief §2/§9)."""

from core.models.user import User
from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/issues"
COMMENTS = "/api/v1/issues/{issue_id}/comments"
ISSUE_MESSAGE = "Issue not found"
TEAM_ARCHIVED_MESSAGE = "Team is archived"
COMMENT_EMPTY_MESSAGE = "Comment body must not be empty"


def _create_team(client: TestClient, key: str = "ENG") -> dict:
    response = client.post("/api/v1/teams", json={"name": "Engineering", "key": key})
    assert response.status_code == 201
    return response.json()


def _create_issue(client: TestClient, team_id: str, title: str = "First") -> dict:
    response = client.post(API, json={"team_id": team_id, "title": title})
    assert response.status_code == 201
    return response.json()


def _add_member(pg: pg_connection, user: User, team_id: str, role: str = "member") -> None:
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, %s)",
            (user.id, team_id, role),
        )


def _create_comment(client: TestClient, issue_id: str, body: str = "Looks good") -> dict:
    response = client.post(COMMENTS.format(issue_id=issue_id), json={"body": body})
    assert response.status_code == 201
    return response.json()


def _activities(client: TestClient, issue_id: str) -> list[dict]:
    response = client.get(f"{API}/{issue_id}/activity")
    assert response.status_code == 200
    return response.json()


def test_member_creates_and_lists_comments(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Any member can write a Comment; it lists oldest first and emits Activity."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user(email="member@example.com")
    with pg.cursor() as cur:
        cur.execute("UPDATE users SET display_name = %s WHERE id = %s", ("Member", member.id))
    _add_member(pg, member, team["id"])
    other = login_as(client, member)

    created = _create_comment(other, issue["id"], "First take")
    assert created["body"] == "First take"
    assert created["author_id"] == str(member.id)
    assert created["author_display_name"] == "Member"
    assert created["issue_id"] == issue["id"]
    assert created["edited_at"] is None
    assert created["created_at"]

    # Second Comment: the list is oldest first.
    _create_comment(other, issue["id"], "Second take")
    listed = other.get(COMMENTS.format(issue_id=issue["id"])).json()
    assert [comment["body"] for comment in listed] == ["First take", "Second take"]

    # One comment.created Activity row per Comment, oldest first.
    kinds = [activity["kind"] for activity in _activities(client, issue["id"])]
    assert kinds.count("comment.created") == 2
    assert kinds == ["issue.created", "comment.created", "comment.created"]


def test_author_edits_comment_repeatedly(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """The author may edit repeatedly; edited_at is stamped; each edit emits Activity."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user(email="member@example.com")
    _add_member(pg, member, team["id"])
    other = login_as(client, member)
    created = _create_comment(other, issue["id"], "v1")

    edited = other.patch(
        f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}", json={"body": "v2"}
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["body"] == "v2"
    assert body["edited_at"] is not None
    first_edited_at = body["edited_at"]

    reedited = other.patch(
        f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}", json={"body": "v3"}
    ).json()
    assert reedited["body"] == "v3"
    assert reedited["edited_at"] >= first_edited_at

    # Re-sending the same body is a no-op: no new Activity, no new edited_at.
    before = _activities(client, issue["id"])
    noop = other.patch(
        f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}", json={"body": "v3"}
    ).json()
    after = _activities(client, issue["id"])
    assert noop["body"] == "v3"
    assert noop["edited_at"] == reedited["edited_at"]
    assert before == after
    assert [a["kind"] for a in after].count("comment.updated") == 2


def test_only_the_author_can_edit(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Genuine 403: a non-author (member, owner, even an Admin) cannot edit."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    author = make_user(email="author@example.com")
    _add_member(pg, author, team["id"])
    as_author = login_as(client, author)
    created = _create_comment(as_author, issue["id"], "mine")
    comment_path = f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}"

    outsider_member = make_user(email="other@example.com")
    _add_member(pg, outsider_member, team["id"])
    response = login_as(client, outsider_member).patch(comment_path, json={"body": "hax"})
    assert response.status_code == 403

    owner = make_user(email="owner@example.com")
    _add_member(pg, owner, team["id"], role="owner")
    assert login_as(client, owner).patch(comment_path, json={"body": "hax"}).status_code == 403
    # No Admin exception either (brief §2: editable by author).
    assert client.patch(comment_path, json={"body": "hax"}).status_code == 403

    assert client.get(COMMENTS.format(issue_id=issue["id"])).json()[0]["body"] == "mine"


def test_author_owner_and_admin_can_delete(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Deletion: author, Team owner, or Admin; a non-author member gets 403."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    author = make_user(email="author@example.com")
    _add_member(pg, author, team["id"])
    as_author = login_as(client, author)

    # The author deletes their own Comment.
    own = _create_comment(as_author, issue["id"], "bye")
    assert (
        as_author.delete(f"{COMMENTS.format(issue_id=issue['id'])}/{own['id']}").status_code == 204
    )

    # A non-author member cannot (the ticket's 403).
    kept = _create_comment(as_author, issue["id"], "kept")
    other = make_user(email="other@example.com")
    _add_member(pg, other, team["id"])
    assert (
        login_as(client, other)
        .delete(f"{COMMENTS.format(issue_id=issue['id'])}/{kept['id']}")
        .status_code
        == 403
    )

    # A (non-Admin) Team owner can.
    owner = make_user(email="owner@example.com")
    _add_member(pg, owner, team["id"], role="owner")
    assert (
        login_as(client, owner)
        .delete(f"{COMMENTS.format(issue_id=issue['id'])}/{kept['id']}")
        .status_code
        == 204
    )

    # A workspace Admin can.
    final = _create_comment(as_author, issue["id"], "final")
    assert (
        client.delete(f"{COMMENTS.format(issue_id=issue['id'])}/{final['id']}").status_code == 204
    )
    assert client.get(COMMENTS.format(issue_id=issue["id"])).json() == []


def test_deleting_removes_old_comment_activity_rows(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Only the comment.deleted row remains (Linear-style trail)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user(email="member@example.com")
    _add_member(pg, member, team["id"])
    other = login_as(client, member)
    created = _create_comment(other, issue["id"], "v1")
    other.patch(f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}", json={"body": "v2"})
    assert (
        other.delete(f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}").status_code == 204
    )

    comment_kinds = [
        activity["kind"]
        for activity in _activities(client, issue["id"])
        if activity["kind"].startswith("comment.")
    ]
    assert comment_kinds == ["comment.deleted"]


def test_non_member_cannot_comment(client: TestClient, make_user: MakeUser) -> None:
    """Outsiders get 404 on every Comment endpoint (ticket 03/04 convention)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    created = _create_comment(client, issue["id"])
    comment_path = f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}"

    outsider = make_user(email="outsider@example.com")
    other = login_as(client, outsider)
    assert other.post(COMMENTS.format(issue_id=issue["id"]), json={"body": "hi"}).status_code == 404
    assert other.get(COMMENTS.format(issue_id=issue["id"])).status_code == 404
    assert other.patch(comment_path, json={"body": "hax"}).status_code == 404
    assert other.delete(comment_path).status_code == 404


def test_unknown_issue_and_comment_are_404(client: TestClient) -> None:
    """A Comment id of another Issue (or an unknown one) is invisible (404)."""
    register_admin(client)
    team = _create_team(client)
    issue_a = _create_issue(client, team["id"], "A")
    issue_b = _create_issue(client, team["id"], "B")
    created = _create_comment(client, issue_a["id"])
    other_id = "00000000-0000-0000-0000-000000000000"

    assert (
        client.patch(
            f"{COMMENTS.format(issue_id=issue_b['id'])}/{created['id']}", json={"body": "x"}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"{COMMENTS.format(issue_id=issue_b['id'])}/{created['id']}").status_code
        == 404
    )
    assert (
        client.patch(
            f"{COMMENTS.format(issue_id=issue_a['id'])}/{other_id}", json={"body": "x"}
        ).status_code
        == 404
    )
    assert client.delete(f"{COMMENTS.format(issue_id=issue_a['id'])}/{other_id}").status_code == 404
    # The Comment itself is untouched.
    assert client.get(COMMENTS.format(issue_id=issue_a["id"])).json()[0]["body"] == "Looks good"


def test_archived_team_rejects_comment_writes(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Writes into an archived Team are 403 (like the other Issue write paths)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    member = make_user(email="member@example.com")
    _add_member(pg, member, team["id"])
    other = login_as(client, member)
    created = _create_comment(other, issue["id"])
    with pg.cursor() as cur:
        cur.execute("UPDATE teams SET archived_at = now() WHERE id = %s", (team["id"],))

    assert other.post(COMMENTS.format(issue_id=issue["id"]), json={"body": "no"}).status_code == 403
    assert (
        other.patch(
            f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}", json={"body": "no"}
        ).status_code
        == 403
    )
    assert (
        other.delete(f"{COMMENTS.format(issue_id=issue['id'])}/{created['id']}").status_code == 403
    )
    # Reads still work (consistent with the other read endpoints).
    assert other.get(COMMENTS.format(issue_id=issue["id"])).status_code == 200


def test_deactivated_user_cannot_comment(
    client: TestClient, pg: pg_connection, make_user: MakeUser
) -> None:
    """Deactivated Users get 403 via the auth middleware (as usual)."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    deactivated = make_user(email="gone@example.com", is_active=False)
    _add_member(pg, deactivated, team["id"])
    other = login_as(client, deactivated)

    assert other.post(COMMENTS.format(issue_id=issue["id"]), json={"body": "hi"}).status_code == 403
    assert other.get(COMMENTS.format(issue_id=issue["id"])).status_code == 403


def test_invalid_bodies_are_rejected(client: TestClient) -> None:
    """Empty/oversized bodies are rejected; whitespace-only is a domain 400."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])

    assert client.post(COMMENTS.format(issue_id=issue["id"]), json={"body": ""}).status_code == 422
    oversized = client.post(COMMENTS.format(issue_id=issue["id"]), json={"body": "x" * 20_001})
    assert oversized.status_code == 400
    assert oversized.json()["error"]["message"] == "Comment body must be at most 20,000 characters"
    response = client.post(COMMENTS.format(issue_id=issue["id"]), json={"body": "   \n\t"})
    assert response.status_code == 400
    assert response.json()["error"]["message"] == COMMENT_EMPTY_MESSAGE
    # The cap is enforced after trimming: 20,000 chars plus padding is valid.
    padded = client.post(COMMENTS.format(issue_id=issue["id"]), json={"body": "x" * 20_000 + "  "})
    assert padded.status_code == 201
    assert len(padded.json()["body"]) == 20_000
    listed = client.get(COMMENTS.format(issue_id=issue["id"])).json()
    assert [comment["body"] for comment in listed] == ["x" * 20_000]
    # A PATCH with an empty body is rejected by the schema before routing.
    assert (
        client.patch(
            f"{COMMENTS.format(issue_id=issue['id'])}/00000000-0000-0000-0000-000000000000",
            json={"body": ""},
        ).status_code
        == 422
    )
    listed = client.get(COMMENTS.format(issue_id=issue["id"])).json()
    assert [comment["body"] for comment in listed] == ["x" * 20_000]


def test_comment_activity_rows_keep_issue_feed_order(client: TestClient) -> None:
    """comment.* rows interleave with issue rows in insertion (seq) order."""
    register_admin(client)
    team = _create_team(client)
    issue = _create_issue(client, team["id"])
    comment = _create_comment(client, issue["id"], "c1")

    client.patch(
        f"{API}/{issue['id']}",
        json={"updated_at": issue["updated_at"], "title": "Renamed"},
    )
    client.patch(
        f"{COMMENTS.format(issue_id=issue['id'])}/{comment['id']}", json={"body": "c1-edited"}
    )

    def _kinds() -> list[str]:
        return [activity["kind"] for activity in _activities(client, issue["id"])]

    assert _kinds() == ["issue.created", "comment.created", "issue.updated", "comment.updated"]

    # Deleting the Comment removes its created/updated rows; only the
    # comment.deleted trail remains (in seq order).
    client.delete(f"{COMMENTS.format(issue_id=issue['id'])}/{comment['id']}")
    assert _kinds() == ["issue.created", "issue.updated", "comment.deleted"]
