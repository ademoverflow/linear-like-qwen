# 01: Core loop — bootstrap, login, Team, ENG-1, list

**What to build:** From a fresh database, the first user registers and becomes Admin, logs in
(out, in again), creates a Team which is seeded with the default Workflow, creates the first
Issue (ENG-1) and sees it in the Team Issues list. The whole product standing end-to-end:
auth + rate limit, Teams + Workflow seeding, Issue creation with number allocation, Activity,
the auth screens, the app shell (sidebar + breadcrumbs) and the list screen.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Registration is open only while the user base is empty; the first registrant becomes Admin; afterwards registration without a valid Invitation token is rejected.
- [ ] Login verifies the password, issues the `access_token` HttpOnly cookie (flags per settings, Max-Age from the JWT expiration setting) and returns the `me` payload — never the token body; wrong credentials → 401; login is rate-limited (10/15 min per email and per IP) → 429; logout clears the cookie.
- [ ] `GET /auth/me` returns `is_admin` and memberships with roles; the webapp guards authenticated routes (401 → login).
- [ ] Only an Admin can create a Team (name + unique 2–5 uppercase-letter key); the creating Admin becomes owner; the Team is created with the default Workflow and six Workflow States (Backlog, Todo, In Progress, In Review, Done, Canceled) in the same transaction.
- [ ] A Team member or Admin can create an Issue with a title (1–255, trimmed); the Issue receives the Team's next number (first is ENG-1) via the locked counter, the default state (first backlog, else first unstarted), an immutable creator, and an Activity `issue.created` row.
- [ ] Concurrent Issue creation never yields duplicate numbers (verified by a test creating N Issues in parallel).
- [ ] A New Issue dialog (title + Team) opens with `C`; the Team Issues list renders Issues as a card stack (prototype variant B: identifier, priority glyph, title, labels, assignee, state) with the empty state "No issues yet — press C".
- [ ] Auth screens (bootstrap register / login / logout) and the app shell (collapsible sidebar with Teams, breadcrumb bar) exist and are keyboard-reachable.
- [ ] Tests: pure-domain units (identifier format/parse, default-state selection); HTTP happy-path + one 403 per new endpoint; the concurrency test above.
