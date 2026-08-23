# 02: Invitations & admin user management

**What to build:** Admins invite new Users by email; invitees register with their token;
Admins manage the user base — list, deactivate/reactivate, promote/demote Admins — with the
last-Admin protection, from a dedicated Admin screen.

**Blocked by:** 01 (Core loop)

**Status:** done

- [x] An Admin can invite a User by email: an Invitation is created (7-day expiry, random token stored hashed, invited_by set); one active Invitation per email; re-inviting replaces the token so the old one stops working.
- [x] Registering with a valid, unexpired, unused token creates the User and marks the Invitation accepted; expired, invalid or already-used tokens are rejected with a clear message.
- [x] The Admin screen lists all Users (active and deactivated); an Admin can deactivate and reactivate a User.
- [x] A deactivated User gets 403 on everything, but their Comments and Activity remain and display their name.
- [x] An Admin can promote and demote Admins; the last active Admin cannot demote or deactivate themselves (422).
- [x] Tests: happy-path + one 403 per new endpoint; token lifecycle (valid / expired / used / replaced); last-Admin 422; deactivated-user 403 with history intact.


## Shipped (Phase 3)

**Backend** (`core/`)
- Domain (pure, DB-free): `invitations.py` (random URL-safe token, SHA-256-hex hash,
  `invitation_state` valid/expired/used), `users.py` (`assert_last_admin_rule` — the last
  active Admin cannot be demoted or deactivated, 422); `authz.py` gains seven Admin-only
  actions (`invitation.create/list`, `user.list/deactivate/reactivate/promote/demote`).
- Model + migration `41122028d5a0`: `invitations` table (email, hashed token, invited_by,
  expires_at, accepted_at; `updated_at` trigger; partial unique index — one active
  Invitation per email; downgrade verified).
- Services: invitations (invite with 7-day expiry, re-invite replaces the token so the old
  one stops working; list; token lookup with `SELECT … FOR UPDATE` so a concurrent register
  race resolves cleanly), users (list all, deactivate/reactivate, promote/demote with the
  last-Admin rule), auth (`register` now validates the token: invalid / used / expired /
  different-email each rejected with a clear 400; taken email → 409; valid → creates the
  non-Admin User and marks the Invitation accepted in one transaction).
- Routers on `/api/v1`: `/invitations` (POST returns the raw token once; GET never reveals
  it), `/users` (list + `deactivate`/`reactivate`/`promote`/`demote`, all Admin-only 403).

**Webapp** (`webapp/`)
- Admin screen (`/admin`, `is_admin` route guard + Admin-only sidebar entry): Users tab
  (role/status badges, Promote/Demote, Deactivate/Reactivate with 422/403 surfaced as
  alerts) and Invitations tab (invite form; the raw token shown once with Copy; list with
  Pending/Expired/Accepted status and expiry date).
- API modules `api/users.ts` + `api/invitations.ts` (Zod schemas mirroring the API),
  `queryKeys.admin.{users,invitations}`; the Register token field now works end-to-end.

**Tests**
- `core/tests`: 83 passing total — domain units (token gen/hash, state matrix, last-Admin
  rule, authz actions); HTTP happy-path + 403 per new endpoint (incl. reactivate/demote),
  token lifecycle (valid/expired/used/replaced/different-email/taken-email), last-Admin 422
  (self demote + deactivate), deactivated User 403 with row + memberships intact, 404s, and
  4-parallel register with one token → exactly one 201.
- `webapp/src/pages/Admin.test.tsx`: 3 render tests (user list with roles/actions,
  invitations tab + one-time token reveal, non-Admin redirect).

## Deferred (later tickets / later work)

- The API does not expose a computed Invitation status; the Admin screen derives
  Pending/Expired/Accepted client-side from `expires_at`/`accepted_at` (3 lines of display
  logic; revisit if the rule ever grows).
- Email delivery for Invitations is out of scope (no email sending in v1, brief §1): the
  Admin copies the one-time token to the invitee.
- Comments/Activity of deactivated Users stay intact (row + memberships asserted); their
  display-name rendering is covered when Comments land (ticket 06).
- `PATCH /auth/me` (display_name, avatar_url) and `POST /auth/change-password` — later
  auth ticket (still listed under the users scope of the brief).
