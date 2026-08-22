# 0002 — JWT `sub` is the user id; tokens are not revocable in v1

**Status**: accepted

## Context

The template issues JWTs stored in an `HttpOnly` `access_token` cookie (and accepts a Bearer
header). The original claim keyed on `email`, which changes if a user updates their address
and is not the primary key.

## Decision

- `sub` = `str(user.id)`; `email` stays as an informational claim.
  `core.security.token.create_access_token_for_user()` is the single constructor.
- `get_current_user` looks up by id and rejects tokens without a UUID `sub` (legacy
  email-only tokens are invalid).
- No server-side session table, no revocation list. Logout clears the cookie; changing a
  password does **not** invalidate tokens already issued. Expiry is
  `CORE_JWT_EXPIRATION_TIMEDELTA_MINUTES`.

## Consequences

- "List/revoke sessions" is out of scope for v1 (brief §5.1).
- If revocation is needed later: add a `token_version` column on `users`, put it in the claims,
  compare on every request. Cheap to add, no schema for sessions.
