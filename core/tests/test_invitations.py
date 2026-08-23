"""Tests for the Invitations endpoints and the invited register flow (ADR 0012)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import MakeUser, login_as, register_admin

INVITATIONS_API = "/api/v1/invitations"
AUTH_API = "/api/v1/auth"
EMAIL = "invitee@example.com"


def _invite(client: TestClient, email: str = EMAIL) -> dict:
    response = client.post(INVITATIONS_API, json={"email": email})
    assert response.status_code == 201
    return response.json()


def test_admin_invites_by_email(client: TestClient, pg: pg_connection) -> None:
    """An Invitation gets a 7-day expiry, a token (hashed at rest) and invited_by."""
    admin = register_admin(client)
    body = _invite(client)
    assert body["email"] == EMAIL
    assert body["accepted_at"] is None
    assert body["token"]  # raw token is shown once, at creation

    with pg.cursor() as cur:
        cur.execute("SELECT token, invited_by, expires_at FROM invitations")
        row = cur.fetchone()
        assert row is not None
        stored_token, invited_by, expires_at = row
        cur.execute("SELECT now()")
        now_row = cur.fetchone()
        assert now_row is not None
        db_now = now_row[0]
    assert stored_token != body["token"]  # stored form is not the raw token
    assert len(stored_token) == 64  # SHA-256 hex
    assert invited_by == admin["id"]
    age = expires_at - db_now
    assert timedelta(days=6, hours=23) < age < timedelta(days=7, hours=1)


def test_reinvite_replaces_the_token(client: TestClient, pg: pg_connection) -> None:
    """Re-inviting the same email replaces the token; the old one stops working."""
    register_admin(client)
    first = _invite(client)
    second = _invite(client)
    assert second["token"] != first["token"]

    with pg.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM invitations WHERE email = %s AND accepted_at IS NULL",
            (EMAIL,),
        )
        count_row = cur.fetchone()
        assert count_row is not None
        count = count_row[0]
    assert count == 1  # one active Invitation per email

    old = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": first["token"]},
    )
    assert old.status_code == 400
    fresh = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": second["token"]},
    )
    assert fresh.status_code == 201


def test_register_with_valid_token_creates_user_and_marks_accepted(
    client: TestClient, pg: pg_connection
) -> None:
    """A valid token creates a non-Admin User and marks the Invitation accepted."""
    register_admin(client)
    body = _invite(client)
    response = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": body["token"]},
    )
    assert response.status_code == 201
    me = response.json()
    assert me["email"] == EMAIL
    assert me["is_admin"] is False
    set_cookie = response.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie

    with pg.cursor() as cur:
        cur.execute("SELECT accepted_at IS NOT NULL FROM invitations WHERE email = %s", (EMAIL,))
        accepted_row = cur.fetchone()
        assert accepted_row is not None
        assert accepted_row[0] is True
    login = client.post(f"{AUTH_API}/login", json={"email": EMAIL, "password": "password123"})
    assert login.status_code == 200


def test_register_with_invalid_token_rejected(client: TestClient) -> None:
    """An unknown token is rejected with a clear message."""
    register_admin(client)
    response = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": "not-a-token"},
    )
    assert response.status_code == 400
    assert "invitation" in response.json()["error"]["message"].lower()


def test_register_with_used_token_rejected(client: TestClient) -> None:
    """An already-accepted Invitation is rejected with a clear message."""
    register_admin(client)
    body = _invite(client)
    first = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": body["token"]},
    )
    assert first.status_code == 201
    second = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": body["token"]},
    )
    assert second.status_code == 400
    assert "used" in second.json()["error"]["message"].lower()


def test_register_with_expired_token_rejected(client: TestClient, pg: pg_connection) -> None:
    """An expired Invitation is rejected with a clear message."""
    register_admin(client)
    body = _invite(client)
    with pg.cursor() as cur:
        cur.execute("UPDATE invitations SET expires_at = now() - interval '1 day'")
    response = client.post(
        f"{AUTH_API}/register",
        json={"email": EMAIL, "password": "password123", "token": body["token"]},
    )
    assert response.status_code == 400
    assert "expired" in response.json()["error"]["message"].lower()


def test_register_with_token_for_other_email_rejected(client: TestClient) -> None:
    """The registrant must use the invited email address."""
    register_admin(client)
    body = _invite(client)
    response = client.post(
        f"{AUTH_API}/register",
        json={
            "email": "someone-else@example.com",
            "password": "password123",
            "token": body["token"],
        },
    )
    assert response.status_code == 400
    assert "different email" in response.json()["error"]["message"].lower()


def test_register_with_taken_email_is_conflict(client: TestClient) -> None:
    """A taken email is a conflict even with a valid token."""
    register_admin(client)
    body = _invite(client, email="admin@example.com")
    response = client.post(
        f"{AUTH_API}/register",
        json={
            "email": "admin@example.com",
            "password": "password123",
            "token": body["token"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_list_invitations_shows_all_without_tokens(client: TestClient) -> None:
    """Admins list every Invitation; the raw token is never revealed in lists."""
    register_admin(client)
    _invite(client, email="a@example.com")
    _invite(client, email="b@example.com")
    body = client.get(INVITATIONS_API).json()
    assert [i["email"] for i in body] == ["b@example.com", "a@example.com"]
    assert all("token" not in i for i in body)


def test_concurrent_register_same_token_one_wins(client: TestClient) -> None:
    """Parallel registers with one token: exactly one succeeds, the rest rejected."""
    register_admin(client)
    body = _invite(client)
    token = body["token"]

    def register(_index: int) -> int:
        return client.post(
            f"{AUTH_API}/register",
            json={"email": EMAIL, "password": "password123", "token": token},
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(register, range(4)))

    assert results.count(201) == 1
    assert all(code == 400 for code in results if code != 201)


def test_non_admin_cannot_invite_or_list(client: TestClient, make_user: MakeUser) -> None:
    """Invitations are a workspace-Admin privilege (403 otherwise)."""
    register_admin(client)
    user = make_user(email="plain@example.com")
    create = login_as(client, user).post(INVITATIONS_API, json={"email": "x@example.com"})
    assert create.status_code == 403
    assert create.json()["error"]["code"] == "forbidden"
    assert login_as(client, user).get(INVITATIONS_API).status_code == 403
