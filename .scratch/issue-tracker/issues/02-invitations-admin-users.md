# 02: Invitations & admin user management

**What to build:** Admins invite new Users by email; invitees register with their token;
Admins manage the user base — list, deactivate/reactivate, promote/demote Admins — with the
last-Admin protection, from a dedicated Admin screen.

**Blocked by:** 01 (Core loop)

**Status:** ready-for-agent

- [ ] An Admin can invite a User by email: an Invitation is created (7-day expiry, random token stored hashed, invited_by set); one active Invitation per email; re-inviting replaces the token so the old one stops working.
- [ ] Registering with a valid, unexpired, unused token creates the User and marks the Invitation accepted; expired, invalid or already-used tokens are rejected with a clear message.
- [ ] The Admin screen lists all Users (active and deactivated); an Admin can deactivate and reactivate a User.
- [ ] A deactivated User gets 403 on everything, but their Comments and Activity remain and display their name.
- [ ] An Admin can promote and demote Admins; the last active Admin cannot demote or deactivate themselves (422).
- [ ] Tests: happy-path + one 403 per new endpoint; token lifecycle (valid / expired / used / replaced); last-Admin 422; deactivated-user 403 with history intact.
