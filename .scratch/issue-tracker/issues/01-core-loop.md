# 01: Core loop — bootstrap, login, Team, ENG-1, list

**What to build:** From a fresh database, the first user registers and becomes Admin, logs in
(out, in again), creates a Team which is seeded with the default Workflow, creates the first
Issue (ENG-1) and sees it in the Team Issues list. The whole product standing end-to-end:
auth + rate limit, Teams + Workflow seeding, Issue creation with number allocation, Activity,
the auth screens, the app shell (sidebar + breadcrumbs) and the list screen.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Registration is open only while the user base is empty; the first registrant becomes Admin; afterwards registration without a valid Invitation token is rejected.
- [x] Login verifies the password, issues the `access_token` HttpOnly cookie (flags per settings, Max-Age from the JWT expiration setting) and returns the `me` payload — never the token body; wrong credentials → 401; login is rate-limited (10/15 min per email and per IP) → 429; logout clears the cookie.
- [x] `GET /auth/me` returns `is_admin` and memberships with roles; the webapp guards authenticated routes (401 → login).
- [x] Only an Admin can create a Team (name + unique 2–5 uppercase-letter key); the creating Admin becomes owner; the Team is created with the default Workflow and six Workflow States (Backlog, Todo, In Progress, In Review, Done, Canceled) in the same transaction.
- [x] A Team member or Admin can create an Issue with a title (1–255, trimmed); the Issue receives the Team's next number (first is ENG-1) via the locked counter, the default state (first backlog, else first unstarted), an immutable creator, and an Activity `issue.created` row.
- [x] Concurrent Issue creation never yields duplicate numbers (verified by a test creating N Issues in parallel).
- [x] A New Issue dialog (title + Team) opens with `C`; the Team Issues list renders Issues as a card stack (prototype variant B: identifier, priority glyph, title, labels, assignee, state) with the empty state "No issues yet — press C".
- [x] Auth screens (bootstrap register / login / logout) and the app shell (collapsible sidebar with Teams, breadcrumb bar) exist and are keyboard-reachable.
- [x] Tests: pure-domain units (identifier format/parse, default-state selection); HTTP happy-path + one 403 per new endpoint; the concurrency test above.


## Shipped (Phase 3)

**Backend** (`core/`)
- Domain: `workflow.py` (default states + `select_default_state`), `authz.py` (`can()`), `errors.py` (+401/429).
- Models + migration `d8a5e407b546` (workspace, teams + `next_issue_number`, workflows, workflow_states, memberships, issues, activity; users + display_name/avatar_url/is_admin).
- Services: auth (bootstrap register, login with in-process rate limit 10/15 min per email and per IP, me, status), teams (Admin-only create, seeds default Workflow in one transaction), issues (`SELECT … FOR UPDATE` number allocation, `issue.created` Activity), actors, activity.
- Routers on `/api/v1`: `/auth/register|login|logout|me|status`, `/teams`, `/issues`.

**Webapp** (`webapp/`)
- Screens: bootstrap/invited register, login, Home (no-Teams state), Team Issues list (variant-B card stack).
- App shell: collapsible sidebar (Teams, logout), breadcrumb bar, global `C` shortcut, New Issue dialog, New Team dialog.
- UI primitives (`components/ui`): Button, Input, Select, Dialog (focus trap, Esc, backdrop close, focus restore), Avatar, Skeleton.
- Auth guard: route `beforeLoad` (401 → `/login`, authenticated user away from auth screens) + in-session 401 fallback in the shell.
- Removed the Phase-1 prototype route (variant B folded into `IssueCard`) and the template About screen.

**Tests**
- `core/tests`: 52 passing (domain units; HTTP happy-path + 403 per endpoint; N-parallel Issue create → no duplicate numbers; bootstrap one-shot; rate limit 429).
- `webapp/src/pages/*.test.tsx`: 8 render tests (login 401 alert, register bootstrap/invitation modes, Issues card + empty state, Home admin/non-Admin).

## Deferred (later tickets)

- Invitation token **verification** (ticket 02): `POST /auth/register` accepts a `token` param for forward compatibility but rejects all post-bootstrap registration with a clear message.
- `PATCH /auth/me` (display_name, avatar_url), password change — later auth ticket.
- Labels on Issue cards (label model + M2M land with the labels ticket); cards currently render identifier, title, state dot + name, priority glyph, due date (when set) and assignee.
- Board, Issue detail, search/My Issues, Admin screens, theming override — later tickets per the tracker order.
