"""Tests for the auth endpoints: bootstrap register, login, logout, me, status."""

from fastapi.testclient import TestClient
from psycopg2.extensions import connection as pg_connection

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, MakeUser, register_admin

API = "/api/v1/auth"


def test_status_open_when_user_base_empty(client: TestClient) -> None:
    """Bootstrap registration is open before anyone registers."""
    assert client.get(f"{API}/status").json() == {"bootstrap_open": True}


def test_status_closed_after_bootstrap(client: TestClient) -> None:
    """Bootstrap registration closes once the first user exists."""
    register_admin(client)
    assert client.get(f"{API}/status").json() == {"bootstrap_open": False}


def test_bootstrap_register_creates_admin(client: TestClient) -> None:
    """The first registrant becomes the workspace Admin."""
    response = client.post(
        f"{API}/register",
        json={"email": "first@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_admin"] is True
    assert body["email"] == "first@example.com"
    assert "token" not in body
    assert "access_token" not in body
    set_cookie = response.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_bootstrap_creates_workspace_row(client: TestClient, pg: pg_connection) -> None:
    """The single-workspace root row is created during bootstrap."""
    register_admin(client)
    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM workspace")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1


def test_register_after_bootstrap_is_rejected(client: TestClient) -> None:
    """Once the user base is non-empty, registration is closed (no invitations yet)."""
    register_admin(client)
    response = client.post(
        f"{API}/register",
        json={"email": "second@example.com", "password": "password123"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_login_returns_me_and_sets_cookie(client: TestClient, make_user: MakeUser) -> None:
    """Login issues the HttpOnly cookie and returns the me payload only."""
    make_user(email="alice@example.com")
    response = client.post(
        f"{API}/login",
        json={"email": "alice@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "token" not in body
    assert "access_token" not in body
    set_cookie = response.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Max-Age=" in set_cookie
    me = client.get(f"{API}/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_wrong_password_is_401(client: TestClient, make_user: MakeUser) -> None:
    """Wrong credentials are rejected with the error envelope."""
    make_user(email="bob@example.com")
    response = client.post(
        f"{API}/login", json={"email": "bob@example.com", "password": "wrong password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_login_unknown_user_is_401(client: TestClient) -> None:
    """An unknown email is rejected with the same 401."""
    response = client.post(
        f"{API}/login", json={"email": "ghost@example.com", "password": "password123"}
    )
    assert response.status_code == 401


def test_login_deactivated_user_is_403(client: TestClient, make_user: MakeUser) -> None:
    """Deactivated accounts cannot log in (brief §5.2)."""
    make_user(email="off@example.com", is_active=False)
    response = client.post(
        f"{API}/login", json={"email": "off@example.com", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_login_rate_limited_per_email(client: TestClient, make_user: MakeUser) -> None:
    """The 11th attempt for one email within 15 minutes is rejected (ADR 0009)."""
    make_user(email="carol@example.com")
    for _ in range(10):
        response = client.post(
            f"{API}/login",
            json={"email": "carol@example.com", "password": ADMIN_PASSWORD},
        )
        assert response.status_code == 200
    response = client.post(
        f"{API}/login", json={"email": "carol@example.com", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_login_rate_limited_per_ip(client: TestClient, make_user: MakeUser) -> None:
    """The per-IP budget is independent of the per-email budget (ADR 0009)."""
    for i in range(10):
        client.post(
            f"{API}/login",
            json={"email": f"spammer{i}@example.com", "password": "wrong password"},
        )
    make_user(email="legit@example.com")
    response = client.post(
        f"{API}/login", json={"email": "legit@example.com", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 429


def test_logout_clears_cookie(client: TestClient, make_user: MakeUser) -> None:
    """Logout clears the access-token cookie."""
    make_user(email="dave@example.com")
    response = client.post(
        f"{API}/login", json={"email": "dave@example.com", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    response = client.post(f"{API}/logout")
    assert response.status_code == 204
    assert client.get(f"{API}/me").status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    """Without a token, /auth/me is 401."""
    assert client.get(f"{API}/me").status_code == 401


def test_me_includes_admin_flag_and_memberships(client: TestClient) -> None:
    """The me payload carries is_admin and team memberships with roles."""
    register_admin(client)
    team = client.post("/api/v1/teams", json={"name": "Engineering", "key": "ENG"})
    assert team.status_code == 201
    team_body = team.json()
    me = client.get(f"{API}/me").json()
    assert me["is_admin"] is True
    assert me["memberships"] == [
        {
            "team_id": team_body["id"],
            "team_key": "ENG",
            "team_name": "Engineering",
            "role": "owner",
        }
    ]


def test_me_defaults_theme_to_system(client: TestClient) -> None:
    """A user without a stored preference reports theme "system"."""
    register_admin(client)
    me = client.get(f"{API}/me").json()
    assert me["theme"] == "system"


def test_update_me_requires_auth(client: TestClient) -> None:
    """PATCH /auth/me without a token is 401."""
    assert client.patch(f"{API}/me", json={"theme": "dark"}).status_code == 401


def test_update_me_theme_is_persisted_and_returned(client: TestClient) -> None:
    """PATCH returns the updated me; GET /auth/me reflects the new theme."""
    register_admin(client)
    response = client.patch(f"{API}/me", json={"theme": "dark"})
    assert response.status_code == 200
    body = response.json()
    # Every mutation returns the updated resource: the full me payload.
    assert body["theme"] == "dark"
    assert body["email"] == ADMIN_EMAIL
    assert client.get(f"{API}/me").json()["theme"] == "dark"


def test_update_me_invalid_theme_is_400(client: TestClient) -> None:
    """An unknown theme is rejected with the error envelope (ADR 0003)."""
    register_admin(client)
    response = client.patch(f"{API}/me", json={"theme": "blue"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert client.get(f"{API}/me").json()["theme"] == "system"


def test_update_me_display_name_and_avatar_trim_and_clear(client: TestClient) -> None:
    """Values are trimmed; an explicit null clears the field."""
    register_admin(client)
    response = client.patch(
        f"{API}/me",
        json={"display_name": "  Ada  ", "avatar_url": "  https://example.com/a.png  "},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Ada"
    assert body["avatar_url"] == "https://example.com/a.png"
    cleared = client.patch(f"{API}/me", json={"display_name": None, "avatar_url": None}).json()
    assert cleared["display_name"] is None
    assert cleared["avatar_url"] is None


def test_update_me_partial_keeps_other_fields(client: TestClient) -> None:
    """Omitted fields are unchanged (PATCH semantics)."""
    register_admin(client)
    client.patch(f"{API}/me", json={"display_name": "Ada", "theme": "light"})
    updated = client.patch(f"{API}/me", json={"theme": "dark"}).json()
    assert updated["theme"] == "dark"
    assert updated["display_name"] == "Ada"


def test_update_me_null_theme_resets_to_system(client: TestClient) -> None:
    """theme: null clears the preference (back to the system setting)."""
    register_admin(client)
    client.patch(f"{API}/me", json={"theme": "dark"})
    updated = client.patch(f"{API}/me", json={"theme": None})
    assert updated.json()["theme"] == "system"
