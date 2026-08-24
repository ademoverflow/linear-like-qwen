# 04: Transitions & Board

**What to build:** Moving an Issue between Workflow States through the single domain code
path (with completed/canceled timestamp rules), and the Kanban Board — one column per
Workflow State, drag a card = transition — with optimistic updates.

**Blocked by:** 03 (Issue detail, edit & Activity)

**Status:** done

- [x] Any state → any state is permitted; entering a `completed` State sets `completed_at` and clears `canceled_at`; entering `canceled` sets `canceled_at` and clears `completed_at`; leaving either into anything else clears both; every transition emits Activity `issue.state_changed`.
- [x] Changing the state of an Issue goes through exactly one code path in the domain layer; no generic field update can bypass the transition rules.
- [x] The Board page renders one column per Workflow State (in position order) for the Team; dragging a card between columns performs the transition via the API; the drop is optimistic with rollback + toast on failure.
- [x] Board columns and cards carry ARIA roles and are keyboard-operable (dnd-kit keyboard sensor); the state property in the detail panel uses the same transition path.
- [x] Tests: pure-domain unit tests for the transition rules (full timestamp stamping/clearing matrix, any→any); HTTP: transition happy-path + 403 (see Deferred — non-members get 404, the 403s are the archived Team and deactivated member); `completed_at`/`canceled_at` verified through the API response.

## Shipped (Phase 3)

**Backend** (`core/`)
- `domain/workflow.py` (pure, DB-free): `TransitionEffect` + `transition(target, now)` —
  any State may move to any State; the effect depends only on the target's category:
  `completed` → `completed_at = now`, clear `canceled_at`; `canceled` → `canceled_at =
  now`, clear `completed_at`; any other target clears both. Unit-tested without a
  database, incl. the full category matrix.
- `services/issues.py::transition_issue` — the single code path for State changes: the
  generic `PATCH` cannot touch `state_id` (not in `EDITABLE_FIELDS`). Echoes the
  last-seen `updated_at` → 409 when stale (ADR 0008); 403 when the Issue's Team is
  archived (like `create_issue`); 400 when the target State is not in the Issue's Team
  Workflow; moving to the current State is a 200 no-op (no Activity, no timestamp
  change); otherwise one `issue.state_changed` Activity row (`field="state_id"`,
  from/to = State names). Refreshes `state`/`assignee`/`created_at`/`updated_at` after
  flush so the echoed `updated_at` is the real server value.
- `services/teams.py::list_team_states` — the Team's Workflow States in `position`
  order (board columns, ADR 0011); member-gated, 404 for non-members/unknown Teams.
- New endpoints on `/api/v1`: `POST /issues/{id}/transitions` (body: `state_id` +
  last-seen `updated_at`) and read-only `GET /teams/{id}/states` (brief §9).
- No migration: every column transitions need already existed.

**Webapp** (`webapp/`)
- `@dnd-kit/core` + `@dnd-kit/sortable` added per ADR 0006 (pre-approved;
  `@dnd-kit/utilities` deliberately avoided — the transform is inlined).
- Board route `/teams/$teamKey/board` + a "Board" entry under each Team in the
  sidebar (Settings stays ticket 08).
- `Board` (`components/issues/Board.tsx`): one column per Workflow State in `position`
  order — including `backlog` and `canceled` (ADR 0011); wide board = horizontal
  scroll. The whole column (`<section>`) is the drop target, so drops on the header
  strip or an empty column are not discarded. The drag handle is a focusable button —
  keyboard: Space/Enter lifts, arrows move, Space/Enter drops, Esc cancels (dnd-kit
  keyboard sensor); the card title is a separate `Link` to the detail. ARIA: column =
  `section`/region with `aria-label`, `ul` list, `li` cards. Dots use the State's own
  `color` (the default workflow's colours already carry the §7.4 category semantics).
- `useTransitionIssue` (`hooks/use-transition-issue.ts`): optimistic TanStack Query
  mutation mirroring ticket 03's `useUpdateIssue` — the move is applied to the cached
  Issue (detail + Team list) with a client-side `updated_at` placeholder, replaced by
  the authoritative server response on success (detail parent fields merged in); the
  Activity feed alone refetches; error → rollback + toast; 409 → refetch + toast.
  Echoes the raw `updated_at` string (ADR 0008).
- Detail panel State property is now a `Select` on the same transition path (was
  display-only in ticket 03).
- `TeamBoard`: "New Issue" button in the header (consistent with the Issues list
  toolbar); a states **or** issues query failure shows an error state with a Retry
  that refetches both (a states failure would otherwise render zero columns silently).

**Tests**
- `core/tests`: 133 passing — `tests/test_transitions.py` (15): happy path
  (`completed_at` + `issue.state_changed` Activity with from/to names verified through
  the API response), canceled stamping/clearing, leaving completed/canceled clears
  both, same-state no-op (no Activity, `updated_at` unchanged), re-entering the current
  completed State keeps its timestamp, stale `updated_at` → 409, non-member → 404,
  archived Team → 403, deactivated member → 403 (middleware), cross-team State → 400,
  unknown State → 400, `GET /teams/{id}/states` (position order; non-member/unknown →
  404; deactivated member → 403). `tests/domain/test_workflow.py` (9, +5): the full
  timestamp matrix — into completed / into canceled / leaving either / full category
  matrix any→any.
- `webapp`: 40 passing — `pages/TeamBoard.test.tsx` (9): columns in position order
  with Issues grouped by State, ARIA roles + drag handle per card, sidebar Board link,
  empty state, pure `targetStateForDrop` (column id → its State; card id → that
  Issue's State), plus `useTransitionIssue` at the hook/API seam via `TransitionHarness`
  (QueryClient + detail/list/activity observers + mocked `transitionIssue`): optimistic
  move sends the raw last-seen `updated_at`, the authoritative response is written into
  the caches and Activity refetches, failure rolls back + toasts, 409 refetches +
  toasts. `pages/IssueDetail.test.tsx` (5): the State picker transitions through the
  same path with the last-seen `updated_at`.
- dnd-kit testing approach: full pointer-drag simulation in jsdom is flaky — drags are
  **not** simulated; the board drop is tested at the hook/API seam (decision recorded
  under Deferred).

## Deferred (later tickets / later work)

- Non-members get **404, not the 403** named in the ticket's test line — the
  established convention (ticket 03, `core/src/core/domain/authz.py` docstring).
  The genuine 403s here: a write (transition) into an **archived Team**
  (`ForbiddenError`, like `create_issue`) and a **deactivated User** (middleware,
  asserted on both the transition and the read-only states endpoint).
- Single transition path: `POST /issues/{id}/transitions` (brief §9 gave no exact
  path); `state_id` is not in `EDITABLE_FIELDS`, so the generic `PATCH` cannot bypass
  the transition rules; a same-state transition is a 200 no-op (no Activity, no
  timestamp change).
- dnd-kit pointer drags are not simulated in jsdom (flaky); the drop is tested at the
  hook/API seam (`TransitionHarness`) plus a pure `targetStateForDrop` unit test
  instead.
- The Board's "New Issue" button is deliberate consistency with the Issues list
  toolbar (accepted judgement call, not scope creep).
- The optimistic-mutation hook duplicates `use-update-issue.ts` (the handoff said
  "mirror it"); extracting a shared optimistic-update helper is later work.
- Per-page `CenteredMessage` duplication matches the existing TeamIssues/IssueDetail
  pattern.
- `update_issue` (ticket 03) lacks the archived-Team 403 that `transition_issue` has —
  pre-existing gap, not fixed here.
- Inline `TeamStateResponse`/`TeamMemberResponse` construction in the routers matches
  the existing router style.
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` + `Admin.test.tsx` (2
  errors, files untouched by this ticket) still fail `pnpm --filter webapp run
  build`; everything added here type-checks clean.
