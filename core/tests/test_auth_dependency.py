"""Tests for ``get_current_user`` (cookie JWT with ``sub`` = user id)."""

import uuid
from datetime import timedelta
from typing import Annotated

from core.main import app
from core.middlewares.user import get_current_user
from core.models.user import User
from core.security.token import create_access_token
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from tests.conftest import MakeUser, login_as

_probe = APIRouter()


@_probe.get("/__test/whoami")
async def whoami(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
    """Return the authenticated user's id and email."""
    return {"id": str(user.id), "email": user.email}


app.include_router(_probe)


def test_cookie_token_resolves_user(client: TestClient, make_user: MakeUser) -> None:
    """A token whose ``sub`` is the user id authenticates that user."""
    user = make_user(email="alice@example.com")
    response = login_as(client, user).get("/__test/whoami")
    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": "alice@example.com"}


def test_missing_token_is_401(client: TestClient) -> None:
    """No cookie, no bearer → 401."""
    client.cookies.clear()
    assert client.get("/__test/whoami").status_code == 401


def test_email_only_token_is_rejected(client: TestClient, make_user: MakeUser) -> None:
    """Legacy tokens keyed on ``email`` without ``sub`` are no longer accepted."""
    user = make_user()
    client.cookies.set(
        "access_token", create_access_token({"email": user.email}, timedelta(minutes=5))
    )
    assert client.get("/__test/whoami").status_code == 401


def test_unknown_subject_is_401(client: TestClient) -> None:
    """A well-formed token for a user that does not exist → 401."""
    token = create_access_token({"sub": str(uuid.uuid4())}, timedelta(minutes=5))
    client.cookies.set("access_token", token)
    assert client.get("/__test/whoami").status_code == 401


def test_deactivated_user_is_403(client: TestClient, make_user: MakeUser) -> None:
    """Deactivated users authenticate but are forbidden."""
    user = make_user(is_active=False)
    assert login_as(client, user).get("/__test/whoami").status_code == 403
