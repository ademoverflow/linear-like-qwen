# Project brief: "Linear Like Qwen" — a Linear-style issue tracker on this template

You are the engineering agent on this repository (`ademoverflow/linear-like-qwen`). This document is the **founding brief**. Read it fully, then follow the **Working protocol** (§11). Do not write application code until Phase 0 and Phase 1 are complete and confirmed by the maintainer.

---

## 1. What we are building

A self-hosted web application in the spirit of **Linear** (linear.app): a fast, keyboard-driven issue tracker for software teams, organised as **Workspace → Teams → Issues**, with **Users** who hold team memberships and roles.

**Non-goals for v1** (do not build, do not scaffold): cycles/sprints, roadmaps/projects, GitHub/Slack integrations, email sending, realtime presence, mobile apps, billing, SSO/OAuth, file attachments, AI features, the "mobile app bearer-token" client mentioned in `core/src/core/middlewares/user.py` (keep the code path; don't build a client for it).

If a requirement below is ambiguous, prefer the simplest interpretation that keeps the core loop working: *create an issue → assign it → move it through its workflow → close it*.

---

## 2. Domain model (ubiquitous language)

Use **these exact terms** in Python, TypeScript, SQL, docs, tests, commits and UI copy. Do not invent synonyms (no "ticket", "task", "card", "story" — always **Issue**; no "group"/"squad" — always **Team**). This table seeds `CONTEXT.md`.

| Term | Definition |
|---|---|
| **Workspace** | The single tenant root. v1 is single-workspace; model the table anyway so FKs exist. |
| **User** | Extends the existing `users` table (`core/src/core/models/user.py`). Add `display_name`, `avatar_url?`, `is_admin`. Keep `is_active` as the deactivation flag. |
| **Admin** | A User with `is_admin = true`. Workspace-level privilege (§5). |
| **Team** | Unit of ownership. `name`, `key` (2–5 uppercase ASCII letters, unique, immutable — e.g. `ENG`), `description?`, `archived_at?`. Every Issue belongs to exactly one Team. |
| **Membership** | Join between User and Team. `role ∈ {owner, member}`. Unique on `(user_id, team_id)`. |
| **Issue** | The core record (§3). Human identifier is `<TeamKey>-<number>`, e.g. `ENG-42`; `number` is a per-Team monotonic counter, **never reused**, allocated inside the creating transaction. |
| **Workflow** | The ordered set of **Workflow States** a Team's Issues move through. Each Team owns exactly one Workflow (so in practice states hang off the Team; a separate `workflows` table is optional — decide in Phase 1). |
| **Workflow State** | `name`, `category ∈ {backlog, unstarted, started, completed, canceled}`, `color`, `position`. Every Team gets the default set at creation (§4.1). |
| **Label** | `name`, `color`, scoped to a Team. Many-to-many with Issues. |
| **Comment** | Markdown body on an Issue by a User. Editable by author; deletable by author, Team owner or Admin. |
| **Activity** | Append-only audit row on an Issue: `actor_id`, `kind`, `field?`, `from_value?`, `to_value?`, `created_at`. Written automatically by the service layer on every mutation, never by routers directly. |
| **Invitation** | `email`, `token` (random, hashed at rest), `invited_by`, `expires_at`, `accepted_at?`. |

---

## 3. Issues — definition, modification, deletion

### 3.1 Fields
`id` (UUID, `gen_random_uuid()` like existing models), `team_id`, `number`, `identifier` (computed, not stored), `title` (1–255, trimmed, required), `description` (Markdown, ≤ 50 000 chars, nullable), `state_id`, `priority ∈ {none, urgent, high, medium, low}` (default `none`), `assignee_id?` (must be a Member of the Team), `creator_id` (immutable), labels (M2M, same Team), `parent_id?` (same Team, one level deep only, no cycles), `due_date?` (date), `estimate?` (int 0–21), `created_at`, `updated_at`, `completed_at?`, `canceled_at?`, `archived_at?`.

### 3.2 Create
- Any Member of the Team, or any Admin. Title required; defaults above.
- `number` allocation: a `team_issue_counters` row (or a column on `teams`) locked with `SELECT … FOR UPDATE` in the same transaction as the insert. Write a test that creates N issues concurrently and asserts no duplicate `number`.
- Emits Activity `issue.created`.

### 3.3 Modify
- Any Member (or Admin) may edit any field except `number`, `creator_id`, `team_id`.
- Changing `state_id` is a **transition** and goes through exactly one code path in the domain layer (§4.2). No generic `PUT` may bypass it.
- Each changed field emits one Activity with `from_value`/`to_value`.
- Optimistic concurrency: `PATCH` bodies carry the `updated_at` the client last saw; reply `409` when stale.

### 3.4 Delete
- **Archive (soft delete) by default**: sets `archived_at`. Hidden from all default views and counts; listable with `?include_archived=true`; restorable. Team `owner` or Admin only.
- **Hard delete**: Admin only. Body must repeat the `identifier` as confirmation. Cascades to Comments, Activity, label links.
- Archiving a parent archives its children; restoring a parent does **not** auto-restore children.

---

## 4. Workflow and state management

### 4.1 Default Workflow (seeded for every new Team, in a service, not a migration)
| position | name | category |
|---|---|---|
| 0 | Backlog | backlog |
| 1 | Todo | unstarted |
| 2 | In Progress | started |
| 3 | In Review | started |
| 4 | Done | completed |
| 5 | Canceled | canceled |

Default state for new Issues = the first state with category `backlog`, else first `unstarted`.

### 4.2 Transition rules (pure functions in `core/src/core/domain/workflow.py`, unit-tested without a DB)
- Any state → any state is permitted.
- Into `completed`: set `completed_at = now()`, clear `canceled_at`.
- Into `canceled`: set `canceled_at = now()`, clear `completed_at`.
- Out of `completed`/`canceled` into anything else: clear both.
- Emits Activity `issue.state_changed`.

### 4.3 Editing a Workflow (Team owner / Admin)
- Add, rename, recolor, reorder (`position`) states.
- **Invariant**: a Team must always have ≥ 1 state in each of `unstarted`, `started`, `completed`, `canceled`. Enforce on delete and on category change; violations return `422`.
- **Delete a state** that still has non-archived Issues: only with `migrate_to_state_id` of the same category, in one transaction, with an Activity per moved Issue.

### 4.4 Bulk operations
`POST /issues/bulk` with `issue_ids[]` (same Team) and one of: `state_id`, `assignee_id`, `add_label_ids`, `remove_label_ids`, `archive: true`. All-or-nothing. One Activity per Issue.

---

## 5. Users, authentication, admins

### 5.1 Authentication — **keep the template's mechanism**
The template already has: Argon2id hashing (`core/src/core/security/password.py`), JWT creation (`core/src/core/security/token.py`), and a `get_current_user` dependency that reads the `access_token` cookie or a Bearer header (`core/src/core/middlewares/user.py`), with cookie security driven by `Settings.cookie_secure` / `cookie_samesite` / `cookie_domain`. **Build on it; do not replace it with server-side sessions.**

What is missing and must be added:
- `POST /auth/register` — **bootstrap**: allowed only while `users` is empty; that User becomes Admin. Afterwards `register` requires a valid Invitation token (`POST /auth/register?token=…`).
- `POST /auth/login` — verifies password, issues JWT, sets the `access_token` cookie (`HttpOnly`, `Secure` per settings, `SameSite` per settings, `Domain=cookie_domain`, `Max-Age` from `core_jwt_expiration_timedelta_minutes`). Returns the `me` payload, never the token body.
- `POST /auth/logout` — clears the cookie.
- `GET /auth/me`, `PATCH /auth/me` (display_name, avatar_url), `POST /auth/change-password` (requires current password).
- The JWT payload currently keys on `email`; switch to `sub = user.id` (UUID string) and keep `email` as a claim. Update `get_current_user` accordingly and add a test.
- Rate-limit `login`: simple in-process limiter, 10 attempts / 15 min per email and per IP. Note in an ADR that it is not distributed.
- Token revocation ("sessions list/revoke") is **out of scope** for v1; changing a password does not invalidate existing JWTs. Record this as an accepted limitation in an ADR.

### 5.2 Authorization — two tiers, one function
1. **Workspace Admin** (`User.is_admin`): everything, including Teams CRUD/archive, promote/demote Admins, deactivate Users, hard-delete Issues, Invitations.
2. **Team role** via Membership: `owner` = member rights + edit Team, manage Workflow/Labels/members, archive Issues; `member` = Issue CRUD, comment, manage own Comments.

Non-members cannot see a Team or its Issues. Deactivated Users (`is_active = false`) get `403` on everything (already implemented in `get_current_user`); their Comments/Activity remain and display their name.

Centralise this in `core/src/core/domain/authz.py` as `can(actor: Actor, action: Action, resource: Resource) -> bool` over plain dataclasses (no SQLModel, no session). Routers call a thin FastAPI dependency that loads the Actor/Resource and raises `403`. The frontend hides controls based on the same information exposed in `GET /auth/me` (`is_admin`, memberships with roles) but **never** relies on that alone.

### 5.3 User management (Admin screens)
List users (active/deactivated), invite, deactivate/reactivate, toggle admin. The last active Admin cannot demote or deactivate themselves (`422`).

---

## 6. Teams and their relation to Issues

- Admins create Teams; the creating Admin becomes `owner` automatically; default Workflow States are seeded in the same transaction.
- `key` is immutable (it's baked into every identifier).
- Archiving a Team (Admin) hides it and its Issues everywhere, keeps data, is reversible. No Issue creation in an archived Team.
- **Issues never move between Teams in v1.**
- Team page tabs: Issues (list), Board, Settings (members, labels, workflow — owners only).
- "My Issues" aggregates Issues assigned to the current User across all their Teams.

---

## 7. UI / UX design

Reference feel: Linear — **dense, fast, keyboard-first, calm**. The stack is fixed: React 19, Vite, **TanStack Router (code-based, as in `webapp/src/main.tsx` — do not switch to file-based routing)**, TanStack Query for all server state, TanStack Form for forms, Tailwind CSS 4, `lucide-react` icons, Zod for validation, T3 Env via `webapp/src/env.ts`. No component library is installed; build a small set of primitives in `webapp/src/components/ui/` (Button, Input, Select/Combobox, Popover, Dialog, Tooltip, Avatar, Badge). Ask before adding any dependency beyond those listed (e.g. a DnD library, a Markdown renderer, a sanitiser — these are expected and should be proposed in Phase 1).

### 7.1 Layout
- Left sidebar (collapsible, ~240px): workspace name, search trigger, `My Issues`, then a `Teams` section listing each Team with `Issues` / `Board` / `Settings`. Admin-only `Admin` entry at the bottom.
- Main area: breadcrumb bar (`ENG › Issues`), view toolbar (filter, group by, sort), content.
- Right-hand **Issue detail panel** (full page on narrow screens) with a properties column: State, Priority, Assignee, Labels, Parent, Due date, Estimate.

### 7.2 Screens, in build order
1. Auth: bootstrap register, invited register, login, logout; authenticated layout guard (redirect to `/login` on 401 from `GET /auth/me`).
2. Team Issues **list**: identifier, priority glyph, title, labels, assignee avatar, state; grouped by State; filters by state/assignee/label/priority; sort by created/updated/priority.
3. Issue **detail**: inline-editable title, Markdown description (edit/preview), properties, Comments thread merged chronologically with Activity.
4. **Board** (Kanban by Workflow State); drag between columns = transition.
5. New Issue dialog (`C` from anywhere).
6. Team settings: members, labels, workflow editor (reorder by drag; add/rename/recolor; delete with migrate-to dialog).
7. Admin: users, invitations.
8. Global search (`/` or `Cmd/Ctrl+K`): identifier or title substring across the User's Teams; arrow keys + Enter.

### 7.3 Keyboard shortcuts (minimum)
`C` new issue · `/` or `Cmd/Ctrl+K` search · `J`/`K` or arrows move selection · `Enter` open · `Esc` close · `S` state · `A` assignee · `P` priority · `L` labels · `?` cheat-sheet. Never fire while focus is in an input, textarea or contenteditable.

### 7.4 Visual rules
- Light/dark via one CSS-variable token layer in `webapp/src/styles.css` (Tailwind 4 `@theme`); respect `prefers-color-scheme`; manual override persisted per User (`PATCH /auth/me`).
- One accent colour. State **categories** have fixed semantic colours (backlog grey, unstarted neutral, started amber, completed green, canceled muted red); the state's own `color` is used for the dot only.
- Priority glyphs from `lucide-react`, consistent across list/board/detail.
- Optimistic updates for state/assignee/priority/label changes via TanStack Query mutations with rollback; toast on error.
- Empty states everywhere ("No issues yet — press C"). Skeletons, not spinners.
- Accessibility: full keyboard reachability, visible focus rings, ARIA roles on board columns/cards, colour never the only carrier of meaning.
- Responsive to 768px (sidebar → drawer; detail panel → page).

---

## 8. Monorepo structure (as it exists today) and where new code goes

```
/
├── AGENTS.md                   # always-on agent instructions (single source; CLAUDE.md imports it)
├── CLAUDE.md                   # one line: @AGENTS.md
├── CONTEXT.md                  # domain glossary (seed from §2)
├── docs/
│   ├── adr/                    # 0001-….md, written by grill-with-docs / domain-modeling
│   └── agents/                 # issue-tracker.md, domain.md (written by setup-matt-pocock-skills)
├── .agents/skills/             # ALL skills: the template's 10 project skills + the engineering skills
├── .claude/skills -> ../.agents/skills
├── .scratch/                   # local-markdown issue tracker, one folder per feature
├── Makefile                    # THE command runner — always prefer `make <target>`
├── compose.yaml                # db (postgres:17), adminer :11007, core :11009, webapp :11008
├── env.example → .env          # DATABASE_URL, CORE_JWT_*, WEBAPP_URL, COOKIE_DOMAIN, DEV_MODE
├── pyproject.toml              # root: ruff (select ALL, line 100) + mypy + poe tasks; uv workspace root
├── package.json / pnpm-workspace.yaml   # pnpm 10, workspaces: webapp/**
├── biome.json                  # TS lint/format: tabs, double quotes
├── .commitlintrc.json          # conventional commits; types incl. wip
├── .github/workflows/          # check.yml, commitlint.yml, semantic-release.yml
│
├── core/                       # Python 3.13 FastAPI backend (package `core`)
│   ├── pyproject.toml          # fastapi, sqlmodel, alembic, asyncpg, pyjwt, passlib[argon2], orjson…
│   ├── src/core/
│   │   ├── __main__.py, main.py      # app factory; lifespan runs `alembic upgrade head`; CORS from WEBAPP_URL
│   │   ├── settings.py               # pydantic-settings; cookie_secure / cookie_samesite props
│   │   ├── database.py               # async engine (asyncpg) + get_session dependency
│   │   ├── models/                   # SQLModel tables. Existing: user.py (users). ADD: workspace.py, team.py,
│   │   │                             #   membership.py, workflow_state.py, issue.py, label.py, issue_label.py,
│   │   │                             #   comment.py, activity.py, invitation.py. Import all in models/__init__.py
│   │   │                             #   (alembic env.py relies on `import core.models`).
│   │   ├── domain/                   # NEW. Pure Python, no SQLModel/session imports:
│   │   │   ├── workflow.py           #   transition(), default_states(), validate_state_deletion()
│   │   │   ├── authz.py              #   Actor/Resource dataclasses, can()
│   │   │   ├── identifiers.py        #   TEAM_KEY regex, format_identifier()
│   │   │   └── errors.py             #   DomainError hierarchy → mapped to 4xx in one exception handler
│   │   ├── services/                 # EXISTS (empty). Transactional use-cases: issues.py, teams.py,
│   │   │                             #   workflows.py, auth.py, activity.py. Routers call services, services
│   │   │                             #   call domain + session. Activity rows are written here only.
│   │   ├── routers/                  # Existing: health.py. ADD one router per resource, registered in
│   │   │                             #   routers/__init__.py and main.py. Pydantic schemas live next to routers
│   │   │                             #   (or in schemas/ if it grows).
│   │   ├── security/                 # password.py (Argon2id), token.py (JWT) — extend, don't replace
│   │   ├── middlewares/user.py       # get_current_user — switch claim to sub=user.id
│   │   ├── logger/, misc/            # keep
│   │   └── alembic/versions/         # migrations via `make db-migrate MSG="…"`; review every autogen diff
│   └── tests/                        # pytest, runs in Docker (`make test-core`). ADD conftest.py with an
│                                     #   async test DB fixture (transaction-rollback per test) and an
│                                     #   authenticated-client helper. Pure domain tests need no DB.
│
└── webapp/                     # React 19 + Vite SPA
    ├── package.json            # dev/build/test(vitest)/lint/check(biome)
    ├── src/
    │   ├── main.tsx            # router assembled here (code-based). Grow into routes/ when > ~8 routes.
    │   ├── env.ts              # T3 Env; add VITE_API_URL
    │   ├── styles.css          # Tailwind 4 entry + @theme tokens
    │   ├── integrations/tanstack-query/root-provider.tsx
    │   ├── pages/              # existing convention (About.tsx). One file per screen in §7.2.
    │   ├── components/         # NEW: ui/ primitives, issues/, teams/, layout/ (Sidebar, Shell)
    │   ├── api/                # NEW: typed fetch client (credentials: "include"), one module per resource,
    │   │                       #   Zod schemas mirroring API responses, query-key factory
    │   ├── hooks/              # NEW: useShortcut, useCurrentUser, useTeam…
    │   └── lib/                # NEW: priority/state glyph maps, markdown render
    └── src/**/*.test.tsx       # vitest + Testing Library (jsdom)
```

Rules that follow from the structure:
- **`core/src/core/domain/` imports nothing from `sqlmodel`, `sqlalchemy`, `fastapi` or `core.database`.** It is the primary test seam and must stay DB-free.
- **Routers are thin.** No business logic, no direct Activity writes, no raw transitions in a router.
- **All dev commands go through `make`** (`make up`, `make check`, `make fix`, `make test-core`, `make test-webapp`, `make db-migrate MSG=…`, `make db-upgrade`, `make logs-core`). Read `make help` in Phase 0. Python checks are ruff with `select = ["ALL"]` plus mypy: expect docstring and typing rules to bite; fix, don't ignore.
- **Frontend tests run on the host, backend tests in Docker.** The stack must be `make up` before `make test-core`.
- **No new top-level packages.** The monorepo has two deployable units (`core`, `webapp`); keep it that way. Shared types are mirrored as Zod schemas on the frontend (generated later from OpenAPI if that becomes painful — propose it, don't do it unasked).
- The template's project skills (`new-endpoint`, `new-route`, `new-component`, `migrate`, `test`, `check`, `fix-lint`, `db`, `docker`, `logs`) encode its conventions. **Use `new-endpoint` / `new-route` when scaffolding**, and follow their naming rules (snake_case files, PascalCase classes, kebab-case URL prefixes).

---

## 9. Data and API expectations

- PostgreSQL 17 (compose). Alembic migrations, one per ticket, hand-reviewed; `make db-downgrade` must work for each.
- A `make seed` target (add it, plus `core/src/core/seed.py`) creating: Admin `admin@example.com` with a password printed once, Teams `ENG` and `DSGN`, 4 Users with memberships, ~40 Issues across states with labels and comments. Idempotent.
- REST JSON. Prefix everything under `/api/v1` (health stays at `/health`). Resource paths: `/auth/*`, `/users`, `/invitations`, `/teams`, `/teams/{id}/members|labels|states`, `/issues` (with `?team_id=`), `/issues/{id}/comments`, `/issues/{id}/activity`, `/issues/bulk`, `/search`. Use FastAPI tags per resource so `/docs` stays usable.
- Errors: `{ "error": { "code": str, "message": str, "details": {...}? } }` via one exception handler mapping `DomainError` subclasses to `400/403/404/409/422`. Don't leak SQLAlchemy messages.
- Lists: filters (`state_id[]`, `assignee_id[]`, `label_id[]`, `priority[]`), sort, cursor pagination (default 50, max 200).
- Every mutation returns the updated resource. All writes happen inside one `async with session.begin()`.

---

## 10. Quality bar (definition of done, every ticket)

- `make check` passes (ruff format + lint + isort, mypy, biome).
- `make test-core` and `make test-webapp` pass.
- New domain rules → unit tests in `core/tests/domain/` (no DB). New endpoints → at least one happy-path and one `403` integration test. New screens → at least one render test.
- No `# type: ignore` / `# noqa` / `biome-ignore` without a one-line justification.
- `env.example` updated for any new variable; never commit `.env`.
- One conventional commit per ticket (`feat(issues): archive and restore`), allowed types per `.commitlintrc.json`; body references the `.scratch/` ticket path. Use `wip(...)` only for handoff commits.
- `CONTEXT.md` updated for new terms; ADR for any deviation from §8/§9 or any non-obvious technical choice.

---

## 11. Working protocol

Skills are installed in `.agents/skills/`. Invoke them explicitly: `$skill-name` in Codex, `/skill-name` in Claude Code and OpenCode.

### Phase 0 — Orient (no code)
1. Read `AGENTS.md`, `CONTEXT.md`, `docs/agents/*`, `docs/adr/*`, `core/README.md`, `webapp/README.md`, `Makefile` (`make help`).
2. Inspect the real tree, `core/src/core/models/user.py`, `middlewares/user.py`, `security/*`, `main.py`, `webapp/src/main.tsx`, `env.ts`, `compose.yaml`.
3. Write a short **Discrepancy report**: anything in §8 that doesn't match reality, tooling gaps (e.g. no `conftest.py`, no test-DB strategy, no `VITE_API_URL`), and a proposal per item. **Stop and wait for confirmation.**

### Phase 1 — Align and decide
4. Run **`grill-with-docs`** on this brief. Ask every question whose answer changes code. Record decisions as ADRs in `docs/adr/` and terms in `CONTEXT.md`. Expected ADRs at minimum: JWT claim change + no-revocation limitation; workflow table vs states-on-team; test-database strategy for pytest-in-Docker; frontend DnD library; Markdown render + sanitise; optimistic concurrency field; `/api/v1` prefix.
5. For UI questions words can't settle (list row density, detail panel vs page, board card anatomy) run **`prototype`** (UI branch) on a throwaway route under `webapp/src/pages/__prototype/` and let the maintainer pick.

### Phase 2 — Plan
6. **`to-spec`** → spec in `.scratch/`.
7. **`to-tickets`** → tracer-bullet vertical slices with blockers. **Ticket 1 must be end-to-end**: bootstrap register → login → create Team (with default states) → create Issue `ENG-1` → see it in the list, touching models + migration + domain + service + router + API client + page. Suggested order afterwards: invitations & admin users → issue detail/edit/activity → transitions & board DnD → labels/assignee/priority/bulk → comments → archive/restore/hard-delete → team settings & workflow editor → search & shortcuts → theming & a11y polish → seed.

### Phase 3 — Build, one ticket at a time
8. Per ticket: **`implement`** (drives **`tdd`** at the seams fixed in the spec — domain functions and HTTP endpoints; runs `make check` continuously; finishes with **`code-review`** against the ticket, then commits).
9. Update the ticket file with what shipped and what was deferred. Never start a ticket with open blockers.
10. Unexplained failure after two minutes → **`diagnosing-bugs`**, not guessing. Lint noise → **`fix-lint`** / **`check`** (project skills).
11. Context getting full → **`handoff`** and stop; the maintainer restarts from the handoff doc.

### Always
- Ask before adding any dependency to `core/pyproject.toml` or `webapp/package.json`.
- Never `git reset --hard`, `push --force`, delete branches, or drop the `db` volume.
- Use `make`. Use the §2 vocabulary. Prefer editing existing files to creating new ones. Small diffs.
