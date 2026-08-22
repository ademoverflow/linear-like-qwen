# Spec: Linear-style Issue Tracker (v1)

**Status:** ready-for-agent
**Source:** `PROMPT-linear-like.md` (founding brief) + ADRs 0001–0012 + Phase 1 grill decisions.
Vocabulary: `CONTEXT.md` (Issue, Team, Workflow State, … — never ticket/task/card).

## Problem Statement

Software teams need a fast, keyboard-first, self-hosted issue tracker in the spirit of
Linear, organised as Workspace → Teams → Issues. Today the repo is a template: auth
plumbing (Argon2id, JWT, cookie/Bearer middleware), a health endpoint, the users table
and the test infrastructure exist, but there is no product: no teams, no Issues, no
workflow, no screens. A maintainer booting the app cannot create, assign, move or close
a single Issue.

## Solution

A full-stack web application (React 19 SPA + FastAPI + PostgreSQL 17) delivering the core
loop: *create an Issue → assign it → move it through its Workflow → close it*, plus the
surrounding product: bootstrap registration and invited registration, Team/Workspace
administration, Issues with States/Priorities/Assignees/Labels/Parents/Due dates/Estimates,
transitions with audit Activity, Comments, archive/restore/hard-delete, bulk operations,
a grouped Issues list, a Kanban Board, global search, keyboard shortcuts, light/dark
theming and accessibility.

## User Stories

1. As a first Admin (bootstrap), I can register an account while the user base is empty, so that the Workspace gets its first Admin.
2. As a later registrant, I cannot self-register (registration requires a valid Invitation token), so that nobody can create rogue Accounts.
3. As a logged-out user, I can log in with email and password and receive a session (HttpOnly JWT cookie), so that I can use the app.
4. As a logged-in user, I can log out and have the session cookie cleared, so that I can end my session on shared machines.
5. As a logged-in user, I can view and edit my display name and avatar, so that teammates recognise me.
6. As a logged-in user, I can change my password (requiring the current one), so that I can keep my Account secure.
7. As an attacker, my login attempts are rate-limited (10 per 15 min per email and per IP), so that I cannot brute-force credentials.
8. As a deactivated User, every request is rejected (403), so that deactivation stops access immediately.
9. As a reader of a deactivated User's history, their Comments and Activity still display their name, so that history stays legible.
10. As an Admin, I can invite a new User by email, so that they can join the Workspace.
11. As an invited User, I can register using my Invitation token, so that I can join the Workspace.
12. As an invited User, an expired Invitation is rejected with a clear message, so that I know to ask for a new one.
13. As an Admin, re-inviting an email replaces the previous token, so that stale Invitations stop working.
14. As an Admin, I can list all Users (active and deactivated), so that I can manage the Workspace.
15. As an Admin, I can deactivate and reactivate a User, so that I can control access.
16. As an Admin, I can promote and demote Admins, so that Workspace privileges stay distributed.
17. As the last active Admin, I cannot demote or deactivate myself (422), so that the Workspace never loses all Admins.
18. As an Admin, I can create a Team with a name and a unique 2–5 uppercase-letter key, so that work has a unit of ownership.
19. As the creating Admin, I automatically become the Team's owner, so that someone manages the Team.
20. As a User, a new Team is created with the default Workflow (six Workflow States), so that Issues can move immediately.
21. As a Team owner, I can edit the Team's name and description (the key stays immutable), so that the Team stays accurate.
22. As an Admin, I can archive a Team, so that it disappears from all views while its data is kept, and I can restore it.
23. As a non-member, I cannot see a Team or its Issues (404), so that Team data stays private.
24. As a member, I can navigate a Team's Issues, Board and Settings from the sidebar, so that I can reach the Team's work.
25. As a Team member or Admin, I can create an Issue with a title (1–255, trimmed), so that work gets recorded.
26. As a User, a new Issue receives the Team's next number (e.g. ENG-42) and the default state (first Backlog, else first Unstarted), so that identifiers are stable and sequential.
27. As a User, creating Issues concurrently never yields duplicate numbers, so that identifiers are trustworthy.
28. As a Team member or Admin, I can edit any Issue field (title, description, priority, assignee, parent, due date, estimate), so that Issues stay accurate.
29. As a User, editing with a stale `updated_at` returns 409, so that I never silently clobber someone else's change.
30. As a User, every change is recorded as an Activity row with from→to values, so that the team can audit what changed.
31. As a User, an Issue's number, creator and Team are immutable, so that history and identifiers stay consistent.
32. As a User, I can assign an Issue only to a member of its Team, so that assignments are valid.
33. As a User, I can set a parent Issue (same Team, one level deep, no cycles), so that related work groups together.
34. As a Team owner or Admin, I can archive an Issue, so that it hides from all default views and counts but remains restorable.
35. As a User, I can list Issues with `?include_archived=true` and restore archived Issues, so that no work is lost.
36. As a Team owner or Admin, archiving a parent archives its children, and restoring a parent does not auto-restore children, so that archive trees behave predictably.
37. As an Admin, I can hard-delete an Issue by repeating its identifier as confirmation, so that truly unwanted work is permanently removed with its Comments, Activity and label links.
38. As a Team member, I can run a bulk operation (state, assignee, add/remove labels, archive) over a set of Issues from one Team, all-or-nothing with one Activity per Issue, so that I can manage work in batches.
39. As a User, I can move an Issue to any other Workflow State (a Transition), so that work flows as it really does.
40. As a User, moving an Issue into a completed State stamps `completed_at` and clears `canceled_at` (and vice versa for canceled; leaving either clears both), so that completion is tracked correctly.
41. As a Team owner, I can add, rename, recolor and reorder Workflow States, so that the Workflow matches how the Team works.
42. As a Team owner, my Team always keeps at least one State in each of unstarted, started, completed and canceled (violations return 422), so that the Workflow stays usable.
43. As a Team owner, I can delete a State that still has non-archived Issues only by migrating them to a State of the same category in one transaction (Activity per moved Issue), so that no Issue is left stateless.
44. As a Team owner, concurrent Workflow edits do not clobber each other (stale version → 409), so that I can reorder States confidently.
45. As a Team owner, I can create, rename, recolor and delete Team-scoped Labels, so that Issues can be tagged.
46. As a Team member, I can add and remove Labels (same Team) on an Issue, so that Issues are findable.
47. As a User, I can filter the Issue list by State, Assignee, Label and Priority and sort by created/updated/priority, so that I can find my slice of work.
48. As a User, I can write a Markdown Comment on an Issue, so that work gets discussed.
49. As a Comment author, I can edit my Comment, so that I can fix mistakes.
50. As a Comment author, Team owner or Admin, I can delete a Comment, so that unwanted discussion can be removed.
51. As a User, Comments and Activity appear merged chronologically in the Issue detail, so that I can read the full story of an Issue.
52. As a User, the Team Issues list is a card stack (prototype variant B), so that I can see work at a glance.
53. As a User, the Board shows one column per Workflow State and dragging a card performs the Transition, so that I can manage flow visually.
54. As a User, "My Issues" aggregates Issues assigned to me across all my Teams, so that I know what is mine.
55. As a User, global search finds Issues by identifier or title substring across my Teams, navigable with arrow keys and Enter, so that I can jump to anything.
56. As a keyboard user, I can drive the app with shortcuts (C, / or Cmd/Ctrl+K, J/K, Enter, Esc, S, A, P, L, ?) that never fire while focus is in an input, textarea or contenteditable, so that I can work quickly.
57. As a keyboard/assistive-technology user, everything is keyboard-reachable with visible focus rings, the Board carries ARIA roles, and colour is never the only carrier of meaning, so that the app is accessible.
58. As a User, I get light/dark themes (system preference by default, manual override persisted per User), so that the app suits my eyes.
59. As a User, I get skeletons (not spinners) and empty states ("No issues yet — press C"), so that the app feels fast even when empty.
60. As a User, optimistic updates (state/assignee/priority/labels) roll back with a toast on error, so that the UI never lies to me.
61. As a User on a narrow screen (≤768px), the sidebar becomes a drawer and the Issue detail panel becomes a full page, so that the app is usable on small devices.
62. As a maintainer, `make seed` creates a realistic Workspace (Admin, Teams ENG and DSGN, four Users with memberships, ~40 Issues across States with Labels and Comments) idempotently and prints the Admin password once, so that I can demo and develop.

## Implementation Decisions

**Layering and seams (ADR 0004)** — `domain/` is pure Python (no SQLModel/SQLAlchemy/FastAPI/database imports): Transition rules, authorization `can()`, identifier helpers, input invariants, `DomainError` hierarchy. `services/` own the transaction (`async with session.begin()`), call domain functions and are the only layer writing Activity rows. `routers/` are thin: parse → auth dependency → one service call → response schema.

**API shape (ADR 0003)** — all resources under `/api/v1` (health stays unversioned); one exception handler maps `DomainError` subclasses to `{ "error": { code, message, details? } }`; FastAPI tags per resource. The webapp's typed fetch client (already implemented) is the only place `fetch` is called; it prefixes `/api/v1` and sends `credentials: "include"`.

**Auth (ADR 0002, ADR 0009)** — JWT `sub` = user id UUID (email kept as informational claim); no revocation in v1 (password change does not invalidate tokens; expiry is the only expiry). `POST /auth/login` is guarded by an in-process rate limiter: 10 attempts / 15 min per email and per client IP (two independent budgets), 429 via the error envelope. Cookie flags follow the existing settings (`cookie_secure`, `cookie_samesite`, `cookie_domain`, Max-Age from the JWT expiration setting). Bootstrap register is allowed only while `users` is empty; afterwards register requires a valid, unexpired Invitation token.

**Schema** — new tables: `workspace` (single row, tenant root for FKs), `teams` (name, key unique+immutable, description, archived_at, plus the Issue-number counter column — see below), `workflow` (one per Team, unique `team_id` — ADR 0005), `workflow_state` (workflow_id, name, category, color, position, version integer — ADR 0008), `membership` (user_id, team_id, role ∈ {owner, member}, unique pair), `issue` (team_id, number, title, description, state_id, priority, assignee_id, creator_id, parent_id, due_date, estimate, completed_at, canceled_at, archived_at, timestamps), `label` (team-scoped, name, color), `issue_label` (M2M), `comment` (issue_id, author_id, body Markdown, editable by author), `activity` (append-only: actor_id, kind, field?, from_value?, to_value?, created_at), `invitation` (email, hashed token, invited_by, expires_at, accepted_at). `users` gains `display_name`, `avatar_url?`, `is_admin`, `theme` (system|light|dark, default system). The identifier (`KEY-number`) is computed, never stored. Every table gets the existing `updated_at` trigger convention.

**Issue numbering (ADR 0010)** — `teams.next_issue_number` (default 1); creation locks the Team row `SELECT … FOR UPDATE` in the same transaction as the insert; numbers are never reused. A dedicated test creates N Issues concurrently and asserts no duplicate numbers.

**Concurrency (ADR 0008)** — Issue `PATCH` carries the last-seen `updated_at`; mismatch → 409. Workflow State edits carry the last-seen `version` of each State changed; mismatch → 409. Bulk operations stay unversioned, as specified.

**Workflow (ADR 0005, brief §4)** — Team creation seeds the Workflow and the six default States (Backlog/Todo/In Progress/In Review/Done/Canceled) in one transaction via a service (not a migration). Any state → any state is permitted; entering completed/canceled stamps and clears the timestamps per brief §4.2; leaving them clears both. A State can be deleted only when no non-archived Issues remain, or with `migrate_to_state_id` of the same category in one transaction (one Activity per moved Issue). Invariant: ≥1 State per category (unstarted/started/completed/canceled) enforced on delete and category change → 422.

**Invitations (ADR 0012)** — workspace-level registration tokens (no team scope); 7-day expiry; one active Invitation per email, re-invite replaces the token; token is random and stored hashed. Membership is separate: Team owners add existing Users to their Team and set owner/member roles.

**Authorization (brief §5.2)** — one function `can(actor, action, resource)` over plain dataclasses in the domain layer. Workspace Admin: everything (Teams CRUD/archive, Admin promote/demote, User deactivate, hard delete, Invitations). Team owner: member rights + edit Team, manage Workflow/Labels/members, archive Issues. Team member: Issue CRUD, comment, manage own Comments. Non-members get 404 on Team/Issue resources. Deactivated Users get 403 (already implemented in the auth dependency). The frontend hides controls based on `GET /auth/me` (is_admin, memberships with roles) but never relies on that alone.

**Activity** — written by services only, on every mutation: Issue created/updated (one row per changed field with from→to)/state changed/archived/restored/deleted, Comment created/updated/deleted, label added/removed, bulk moves (one per Issue), state-deletion migrations (one per Issue).

**Issue lifecycle (brief §3)** — archive (soft delete) by Team owner or Admin: sets `archived_at`, hidden from all default views and counts, listable with `?include_archived=true`, restorable; archiving a parent archives children, restoring does not auto-restore. Hard delete: Admin only, body repeats the identifier as confirmation, cascades to Comments, Activity and label links.

**Bulk operations (brief §4.4)** — one endpoint with `issue_ids[]` (same Team) and one of: `state_id`, `assignee_id`, `add_label_ids`, `remove_label_ids`, `archive: true`; all-or-nothing in one transaction; one Activity per Issue.

**Lists and pagination (brief §9)** — Issue list filters (`state_id[]`, `assignee_id[]`, `label_id[]`, `priority[]`), sort (created/updated/priority), cursor pagination (default 50, max 200); every mutation returns the updated resource; all writes in one transaction.

**Frontend (brief §7)** — TanStack Router (code-based, in the existing entry file), TanStack Query for all server state with optimistic mutations + rollback + toasts, TanStack Form, Tailwind 4 with a CSS-variable token layer (`@theme`), one accent colour, fixed semantic category colours (backlog grey, unstarted neutral, started amber, completed green, canceled muted red; a State's own colour is used for the dot only), `lucide-react` priority glyphs consistent across list/board/detail, Zod schemas mirroring API responses. New small component set in `components/ui` (Button, Input, Select/Combobox, Popover, Dialog, Tooltip, Avatar, Badge). Layout: collapsible ~240px sidebar (workspace name, search trigger, My Issues, Teams section with Issues/Board/Settings per Team, Admin-only Admin entry), breadcrumb bar, view toolbar, right-hand Issue detail panel (full page on narrow screens). Screens in build order: auth, Team Issues list (card stack — prototype variant B), Issue detail (inline title, Markdown description with edit/preview, properties, Comments merged with Activity chronologically), Board (Kanban, one column per State — ADR 0011), New Issue dialog (C), Team settings (members, Labels, Workflow editor with drag reorder and delete-with-migrate dialog), Admin (Users, Invitations), global search overlay (`/` or Cmd/Ctrl+K, arrow keys + Enter). Keyboard shortcuts per the list in story 56; `?` cheat-sheet. Empty states everywhere; skeletons not spinners; responsive to 768px (sidebar → drawer, detail panel → page).

**DnD and Markdown (ADR 0006, ADR 0007)** — Board and Workflow-editor reordering use `@dnd-kit/core` + `@dnd-kit/sortable`. Descriptions and Comments render with `react-markdown` + `remark-gfm` (full GFM) + `rehype-sanitize` (explicit allowlist; no raw HTML).

**Visual prototype (Phase 1, commit on main)** — three throwaway variants of list density + board card anatomy exist on a prototype route with mock data. The maintainer picked **variant B: card-stack list + rich board cards** (title, description snippet, labels, due date, assignee avatar). The prototype route is deleted from main once variant B is folded into the real screens and the full variant set is captured on a throwaway branch.

**Seed (brief §9)** — a `make seed` target plus a seed script: Admin `admin@example.com` (password printed once), Teams ENG and DSGN, four Users with memberships, ~40 Issues across States with Labels and Comments; idempotent.

## Testing Decisions

Good tests assert external behaviour only: domain function outputs (inputs → outputs/errors), HTTP status codes and JSON envelopes, and rendered UI — never internal implementation details.

- **Seam 1 (highest, existing): pure domain functions** — unit tests in `core/tests/domain/` with no database. Prior art: identifier tests. Covers: Transition rules (timestamp stamping/clearing, any→any), default-state selection, State-deletion validation incl. category minimums, `can()` authorization matrix, identifier format/parse, input invariants (title trimming/length, Team key, parent rules).
- **Seam 2 (existing): HTTP endpoints** — FastAPI TestClient against the dedicated `<db>_test` database (ADR 0001: migrated via lifespan, truncated per test, synchronous psycopg2 fixtures). Prior art: auth-dependency tests. Every new endpoint gets at least one happy-path and one 403 test (brief §10). Key scenario tests: bootstrap register is one-shot; register with valid/expired/absent token; last-Admin demotion → 422; stale `updated_at` → 409; stale State `version` → 409; N concurrent Issue creates → no duplicate numbers; hard delete requires the exact identifier; non-member sees 404; archive hides from default list and counts; state-deletion without migration target → 422.
- **Seam 3 (existing): webapp render tests** — vitest + Testing Library (jsdom). Prior art: API client tests, App render test. At least one render test per new screen (brief §10); the API client is covered by its existing suite.
- No tests for prototype code; the prototype route is deleted before Phase 3 starts on the list/board screens.

## Out of Scope

Cycles/sprints, roadmaps/projects, GitHub/Slack integrations, email sending (Invitations are token-based, no mail), realtime presence, mobile apps, the mobile bearer-token client (code path stays, no client), billing, SSO/OAuth, file attachments, AI features (brief §1). Token revocation / sessions list (ADR 0002). Distributed rate limiting (ADR 0009 — single core container in v1). OpenAPI-driven frontend codegen (mirrored Zod schemas instead; revisit if painful). Multi-workspace. Moving Issues between Teams.

## Further Notes

- ADRs 0001–0012 in `docs/adr/` are binding for this spec; any deviation needs a new ADR.
- The `domain/` seam already contains `errors.py` and `identifiers.py` (implemented and tested); `workflow.py` and `authz.py` land with their tickets.
- `.scratch/README.md` references `docs/agents/issue-tracker.md`, which does not exist yet (the setup skill never ran). The tracker convention in use is the brief's: local markdown under `.scratch/`, one folder per feature, `ready-for-agent` status.
- The prototype (variant switcher on the prototype route) is throwaway; its winning parts are rewritten properly when folded into the real screens — never promoted as-is.
