# 11: Seed

**What to build:** `make seed` — a one-command realistic Workspace for demos and development:
an Admin, two Teams, four Users with memberships, and ~40 Issues spread across the States
with Labels and Comments. Idempotent.

**Blocked by:** 06 (Comments), 07 (Archive/restore & hard delete)

**Status:** done

- [x] `make seed` creates: Admin `admin@example.com` (password printed once), Teams `ENG` and `DSGN`, four Users with Team memberships, and ~40 Issues across Workflow States with Labels and Comments.
- [x] The seed is idempotent: running it twice creates nothing new and changes nothing.
- [x] The seeded data exercises the full domain (every State category, every priority, labels, comments, at least one archived Issue).
- [x] Test: seed runs against the test database and the expected counts/assertions hold; a second run is a no-op.

## Decisions (recorded during Phase 3)

- **No ADR**: the seed is a dev utility (a CLI inside `core/`), not an architecture
  decision — recorded here instead (handoff: "Decide whether the seed needs an ADR
  (probably not)").
- **Location (ADR 0004, brief §9)**: `core/src/core/seed.py`, entry point
  `python -m core.seed`, invoked by a new `make seed` target
  (`$(COMPOSE) exec $(CORE_CONTAINER) bash -c 'uv run python -m core.seed'`). No new
  top-level package, no API endpoints, no migration, no new dependencies (stdlib
  `secrets` only), zero webapp changes.
- **Services vs direct model writes**: the Issue lifecycle goes through the services —
  `create_issue` (number allocation under the ADR 0010 row lock + creation Activity),
  `transition_issue` (the single transition code path, transition Activities,
  `completed_at`/`canceled_at`), `archive_issue` and `create_comment` (comment
  Activity) — so every seeded Issue has a correct number and a creation Activity (the
  IssueFeed depends on it). Direct model writes are used for the structural rows:
  Workspace, the Admin (required — bootstrap registration is closed once any User
  exists, so the handoff mandates a direct model write with the Argon2id hash), the
  four Users, Memberships, Labels, IssueLabel links, and the missing-State backfill.
- **No Activity rows for the seed's field setup**: after creation the seed sets
  description/priority/assignee/due_date/estimate/parent in one transaction without
  per-field Activity rows — the seed's field setup is not user activity; a seeded
  Issue's feed shows creation + state transitions (+ archive), like a normal Issue's.
- **Natural keys (lookup-or-create)**: `User.email`, `Team.key`, `Membership (user,
  team)`, `Label (team, name)`, `Comment (issue, author, body)`, and **Issue by
  `(team, title)`** — not `(team, number)` as the handoff suggested: on a non-empty
  database the numbers are allocated by the ADR 0010 counter, so the seed cannot know
  in advance which numbers it will receive; the dataset's titles are unique per Team
  and stable across runs.
- **Adoption rule (code-review fix)**: a found Issue is treated as "seeded" only if
  its creator is one of the four seeded Users; a colliding-title Issue created by
  anyone else (e.g. the Admin) is a user Issue and is left entirely untouched (no
  Comments, no Label links, no archive, no State change). For an adopted Issue the
  interrupted run is completed: missing state transition, missing Comment/Label links,
  pending archive.
- **Comments are skipped on archived Issues (code-review fix)**: `create_comment`
  404s on archived Issues, so the seed never comments on them (previously a crash).
- **Admin password**: generated with `secrets.token_urlsafe(12)`, printed once on
  first creation; re-runs print "already exists (password unchanged)" and never reset
  or reprint it (stored hashed).
- **The four Users' password**: a fixed known dev password (`password123`), printed
  on creation — the ticket mandates the generated/Admin password rule only; a known
  password lets developers log in as any seeded User.
- **Teams**: the `create_team` service when the key is missing (default Workflow +
  six States + Admin owner in one transaction); an existing Team is kept as-is,
  Workflow and ownership untouched. State coverage guarantee: if a Team's Workflow
  is missing a category (a State deleted in the editor), the first canonical State of
  the missing category is appended — this is what makes "every State category" hold
  against the non-empty dev database.
- **Dataset (40 Issues: 20 ENG + 20 DSGN)**: all five State categories, all five
  priorities, 32 Label links across 6 Labels, 10 Markdown Comments on 9 Issues, 3
  parent/child pairs, 5 due dates, 22 estimates, 2 archived Issues (both Canceled),
  all four Users appear as assignees and creators. Deliberate extras beyond the
  ticket's parenthetical: the parent links, due dates and estimates (richer demo
  data; their counts are asserted in the tests).
- **Tests (5)**: full-domain coverage on a fresh `db_test`; second run is a no-op
  (row-count + `min`/`max(updated_at)` snapshot over all 12 tables identical — the
  ADR 0008 proof); pre-existing data (bootstrap Admin + ENG + 1 Issue via the API:
  the seed tops up, keeps the same Team row, and the ENG numbers continue from the
  counter); State backfill + category fallback (a deleted completed State is
  re-added; a renamed Backlog is resolved by category); adoption rule (a
  colliding-title user Issue is skipped, a seed-user-created Issue is completed).
  The seed tests drive the async `seed()` with a fresh asyncpg engine per test (one
  event loop per test) — a documented exception to the conftest synchronous-psycopg2
  strategy (noted in `core/tests/conftest.py`).

## Shipped (Phase 3)

- `Makefile`: new `seed` target (+ `## ` help line, Seeding section).
- `core/src/core/seed.py` (new): the dataset (40 `SeedIssue`s, Users, Teams, Labels)
  + `seed()` (idempotent, one transaction per step) + the `main()`/`run_seed()`/
  `format_report()` CLI.
- `core/tests/test_seed.py` (new, 5 tests): full domain, no-op re-run, pre-existing
  data, State backfill/fallback, adoption rule.
- `core/tests/conftest.py`: docstring note for the seed-test engine exception.
- Verified: `make check` green (ruff `ALL` + mypy 115 files + biome 86 files),
  `make test-core` 405 passed, `make seed` run against the dev database (Admin +
  4 Users + DSGN + 40 Issues created; second run: zero writes, counts unchanged),
  `pnpm --filter webapp run build` — no new tsc errors (zero webapp changes),
  `make test-webapp` 118/119 (see Deferred).

## Deferred (later tickets / later work)

- **Pre-existing webapp test failure (out of scope)**: `Admin.test.tsx > "shows
  Invitations with statuses and reveals the token once on invite"` fails because its
  fixture hardcodes `expires_at: 2026-08-30`, which was in the past by 2026-09-07
  (the Invitation renders as "Expired", not "Pending"). Not caused by this ticket;
  the webapp is otherwise untouched.
- **Title-collision edge case**: if a seeded User (e.g. Ada) personally creates an
  Issue with a seeded title, the seed treats it as its own — the creator heuristic is
  the best discriminator available without a marker column (a migration is out of
  scope for this ticket).
- **Dataset Comment edits**: changing a seeded Comment body adds a second Comment on
  the next run (the natural key is (issue, author, body)); the old row is orphaned.
- **No field sync on re-runs**: an adopted Issue is completed to its dataset State
  (and archive) only; other fields (title, priority, …) are never rewritten.
- The ~10 near-identical lookup-or-create blocks and the single-module layout
  (dataset + mechanism in `seed.py`) were kept as-is (code-review judgement calls,
  deliberate).
