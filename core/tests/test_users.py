"""Tests for the user management endpoints (brief §5.3)."""

import uuid

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

API = "/api/v1/users"


def test_admin_lists_all_users(client: TestClient, make_user: MakeUser) -> None:
    """Active and deactivated Users are listed, oldest first (brief §5.3)."""
    register_admin(client)
    make_user(email="other@example.com")
    deactivated = make_user(email="left@example.com")
    assert client.post(f"{API}/{deactivated.id}/deactivate").status_code == 200

    body = client.get(API).json()
    assert [u["email"] for u in body] == [
        "admin@example.com",
        "other@example.com",
        "left@example.com",
    ]
    by_email = {u["email"]: u for u in body}
    assert by_email["left@example.com"]["is_active"] is False
    assert by_email["admin@example.com"]["is_active"] is True
    assert by_email["admin@example.com"]["is_admin"] is True
    assert "hashed_password" not in body[0]


def test_non_admin_cannot_manage_users(client: TestClient, make_user: MakeUser) -> None:
    """User management is a workspace-Admin privilege (403 otherwise)."""
    register_admin(client)
    user = make_user(email="plain@example.com")
    assert login_as(client, user).get(API).status_code == 403
    other_id = uuid.uuid4()
    for path in ("/deactivate", "/reactivate", "/promote", "/demote"):
        response = login_as(client, user).post(f"{API}/{other_id}{path}")
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "forbidden", path


def test_deactivate_and_reactivate(
    client: TestClient, make_user: MakeUser, pg: pg_connection
) -> None:
    """A deactivated User gets 403 everywhere but their history stays intact."""
    register_admin(client)
    team = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"}).json()
    other = make_user(email="other@example.com")
    with pg.cursor() as cur:
        cur.execute(
            "INSERT INTO memberships (user_id, team_id, role) VALUES (%s, %s, 'member')",
            (other.id, team["id"]),
        )
    deactivate = client.post(f"{API}/{other.id}/deactivate")
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    me = login_as(client, other).get("/api/v1/auth/me")
    assert me.status_code == 403
    with pg.cursor() as cur:
        cur.execute("SELECT is_active, email FROM users WHERE id = %s", (other.id,))
        row = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM memberships WHERE user_id = %s", (other.id,))
        membership_row = cur.fetchone()
        assert membership_row is not None
        membership_count = membership_row[0]
    assert row == (False, "other@example.com")  # history (row, memberships) intact
    assert membership_count == 1

    # Back to the Admin session: the deactivated User's cookie gets 403.
    client.cookies.clear()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    reactivate = client.post(f"{API}/{other.id}/reactivate")
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200


def test_last_admin_cannot_deactivate_themselves(client: TestClient) -> None:
    """The last active Admin cannot deactivate themselves (422)."""
    admin = register_admin(client)
    response = client.post(f"{API}/{admin['id']}/deactivate")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rule_violation"


def test_last_admin_cannot_demote_themselves(client: TestClient) -> None:
    """The last active Admin cannot demote themselves (422)."""
    admin = register_admin(client)
    response = client.post(f"{API}/{admin['id']}/demote")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "rule_violation"


def test_promote_and_demote(client: TestClient, make_user: MakeUser) -> None:
    """With two active Admins, demoting the first one is allowed."""
    admin = register_admin(client)
    other = make_user(email="other@example.com")
    promote = client.post(f"{API}/{other.id}/promote")
    assert promote.status_code == 200
    assert promote.json()["is_admin"] is True

    demote_admin = client.post(f"{API}/{admin['id']}/demote")
    assert demote_admin.status_code == 200  # ``other`` is still an active Admin
    assert demote_admin.json()["is_admin"] is False

    # The demoted Admin's own session no longer has Admin privileges.
    assert client.post(f"{API}/{other.id}/demote").status_code == 403

    login_as(client, other)
    last = client.post(f"{API}/{other.id}/demote")
    assert last.status_code == 422  # now the last active Admin
    assert last.json()["error"]["code"] == "rule_violation"


def test_deactivated_admin_can_be_demoted(client: TestClient, make_user: MakeUser) -> None:
    """A deactivated Admin holds no active privilege, so never blocks changes."""
    register_admin(client)
    other = make_user(email="other@example.com")
    assert client.post(f"{API}/{other.id}/promote").status_code == 200
    assert client.post(f"{API}/{other.id}/deactivate").status_code == 200
    demote = client.post(f"{API}/{other.id}/demote")
    assert demote.status_code == 200
    assert demote.json()["is_admin"] is False


def test_unknown_user_is_404(client: TestClient) -> None:
    """Unknown user ids are 404 on every management action."""
    register_admin(client)
    for path in ("/deactivate", "/reactivate", "/promote", "/demote"):
        response = client.post(f"{API}/{uuid.uuid4()}{path}")
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "not_found"
