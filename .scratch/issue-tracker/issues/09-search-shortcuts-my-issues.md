# 09: Search, keyboard shortcuts & My Issues

**What to build:** Global search across the user's Teams (identifier or title substring,
`/` or Cmd/Ctrl+K, arrow keys + Enter), the full keyboard-shortcut set with the `?`
cheat-sheet, and the My Issues view aggregating the user's assigned Issues.

**Blocked by:** 05 (Labels, list filters & bulk operations)

**Status:** done

- [x] Global search (`/` or Cmd/Ctrl+K) matches Issue identifier or title substring across all Teams the current User belongs to; results are navigable with arrow keys and Enter opens the Issue.
- [x] My Issues aggregates Issues assigned to the current User across all their Teams.
- [x] The shortcut set works: `C` new Issue, `J`/`K` or arrows move selection, `Enter` open, `Esc` close, `S` state, `A` assignee, `P` priority, `L` labels, `?` cheat-sheet; none of them fire while focus is in an input, textarea or contenteditable.
- [x] Tests: search scope (only the user's Teams; identifier and title matches); render tests for the search overlay and shortcut activation/suppression.

## Decisions (recorded during Phase 3)

- **Search endpoint** (`GET /api/v1/search`, brief §9): `q` is the single
  query param. Missing / empty / blank `q` → 400 `ValidationError` ("Search
  query is required") — one consistent envelope for every invalid `q` (the
  webapp never sends an empty query; it stays at the hint state). The query
  is **trimmed** before matching. Matching: **title** case-insensitive
  `ILIKE '%q%'` OR **identifier substring** on the computed `KEY-number`
  form — in SQL `Team.key || '-' || Issue.number::text ILIKE %q%` (Team join;
  `parse_identifier` is *not* used: partial identifiers like `NG-1` do not
  parse, and the ILIKE over the computed string covers full / partial /
  bare-number uniformly — bare `1` matches every number containing 1:
  ENG-1, ENG-11, ENG-21, …).
- **Search scope**: only the Teams the current User **belongs to**
  (Membership scope). A workspace Admin who is *not* a member of a Team
  does **not** get that Team's Issues in search — author-relative by
  definition, the ADR 0013 precedent (requester-relative rules live outside
  the `can()` matrix). **No new `Action`** in `domain/authz.py` (verified;
  search and My Issues are read-only). Archived Issues excluded (no
  `include_archived` on search); Issues of archived Teams excluded (ticket
  07/08 "hidden everywhere" convention).
- **Search pagination**: a **fixed cap of 50, no cursor** (search UX is one
  page; the cap is the list's `DEFAULT_LIMIT` — imported from
  `domain.listing`, not a second hard-coded 50 (code-review fix); no
  `next_cursor` in the response). Ordering: identifier matches first, then `team_key`,
  then `number` (deterministic).
- **Search response**: `{issues: [IssueResponse + team_key + team_name]}` —
  explicit Team fields keep the API self-describing (vs the webapp mapping
  `team_id` via `me`). Read-only: no Activity rows, no writes.
- **My Issues endpoint shape**: option (a) — `team_id` becomes **optional**
  on `GET /issues` (closest to brief §9, which names only `/search` as a
  new path). When omitted: scope = all Teams the user belongs to (archived
  Teams excluded — their Issues are hidden from every list view); every
  existing filter/sort/cursor-pagination applies unchanged (the keyset
  machinery is **reused** from `domain/listing.py` via a shared
  statement/pagination helper — nothing duplicated). The assignee is **not
  forced** by the endpoint: the My Issues page itself requests
  `assignee_id=[current user]` (the endpoint aggregates the user's Teams;
  "assigned to me" is the page's filter). Archived Issues hidden by default;
  `include_archived` works cross-Team. A user with zero Teams → 200 empty
  page (personal views are 404-free — a non-member Team is simply out of
  scope, never a 404 per Team).
- **Search overlay** (webapp, global in `AppShell` beside `NewIssueDialog`):
  opens on `/` or `Cmd/Ctrl+K` (both **toggle**), the input is focused on
  open, debounced **150 ms** with request cancellation (AbortController),
  results grouped by Team (Team name header), **arrow keys move the
  selection (wrapping at both ends)**, Enter navigates to
  `/teams/$teamKey/issues/$issueId` and closes, Esc closes and clears; a click on the
  dimmed backdrop also closes (Esc is the keyboard path).
  Deliberately **stateful — no TanStack Query cache** (a transient overlay,
  fresh each open; caching would need invalidation for no benefit).
  Arrow/Enter/Esc are handled by the overlay's own input `keydown` — *not*
  `useShortcut` (focus is in an input, so the global shortcuts are
  suppressed by design, brief §7.3). The `/` hint sits in the input
  placeholder and the sidebar trigger.
- **Shortcut plumbing**: `useShortcut` gains an optional
  `{ modifier: true }` (fires only with Cmd **or** Ctrl held and no other
  modifier) so `Cmd/Ctrl+K` can be registered — the **single source of
  truth** for typing suppression stays the hook's `isTypingTarget` check
  (it runs on both paths, so a modifier key inside an input is suppressed
  too). Key matching is **case-insensitive** (letter case does not
  matter; recorded — Shift is not filtered on the plain path because `?`
  is physically Shift+`/`, and jsdom sends `key: "?"`). The modifier path
  additionally ignores Shift: Cmd/Ctrl+Shift+K does **not** open search
  (code-review fix). The list-level set is a new shared hook
  `useIssueListKeyboard`, used by **both** the Team Issues list and the My
  Issues list; the Board stays drag-only. The keyboard cursor is a
  **separate state** from the bulk checkbox `Set`: the cursor tracks the
  Issue **id** (survives State re-grouping) and the row under the cursor
  is scrolled into view on move (`scrollIntoView` `block: "nearest"`,
  guarded for jsdom); bulk mode (Select)
  **suspends** the cursor set (J/K/arrows/Enter/S/A/P/L become no-ops;
  bulk stays mouse-driven). Esc closes, in order: quick menu → bulk
  selection → keyboard cursor. **S/A/P/L select the first row when nothing
  is selected** (friendlier than a no-op — recorded). S/A/P/L open a small
  quick-action bar (fixed bottom-centre, same look as the bulk bar):
  State / Assignee / Priority are selects, Labels are checkboxes; the
  mutation reuses `useTransitionIssue` / `useUpdateIssue` as-is (optimistic
  per brief §7.4); the bar closes after an action. On My Issues the quick
  action additionally invalidates the Issue caches on success (the
  optimistic hooks patch the per-Team caches, which do not include the
  cross-Team My Issues page).
- **Shared `user_teams` service helper** (code-review fix): the
  "Teams the user belongs to (non-archived)" lookup lived verbatim in both
  `list_user_issues` and `search_issues`; it is now one helper in
  `services/issues.py` that both call. Deliberate **deviations** from the
  code-review suggestions: the quick-action callbacks stay per-page (two
  call sites with different invalidation semantics — My Issues refreshes
  the cross-Team page after each action; a shared hook would add plumbing
  for no real savings), and the Issues list router keeps dispatching to
  the two service entry points on `team_id` presence (dispatch + response
  shaping only; the services return different shapes — one Team vs many).
- **My Issues page**: new route `/my-issues` under the app layout; the
  sidebar link sits between the search trigger and the Teams section
  (brief §7.1 order) and is **always visible** (a user with zero Teams
  still has the view — empty state "No Issues assigned to you"). Rows
  **reuse `IssueCard` as-is** (it already links to the detail route — no
  separate row renderer; recorded). Load-more pagination like the Team
  list; rows are grouped by Team (via `me.memberships` keys/names).
- **No new ADR**: the membership-scoped (author-relative) search / My
  Issues reads are the ADR 0013 pattern; the rest (ILIKE, fixed cap,
  stateful overlay, cursor-by-id) are small mechanical choices recorded
  here. No new Activity, no migration (read-only over existing columns —
  head `cc365a924274` verified).

## Shipped (Phase 3)

- `core/src/core/domain/search.py` (pure, ADR 0004): `clean_search_query`
  (trim; missing/empty/blank → 400 "Search query is required") and
  `SEARCH_RESULT_LIMIT` (= `domain.listing.DEFAULT_LIMIT`).
- `core/src/core/services/search.py`: `search_issues` — Membership scope
  (author-relative, ADR 0013 precedent), title `ILIKE` OR identifier
  substring on the computed `KEY-number` (ADR 0010), archived Issues and
  archived Teams excluded, cap 50 no cursor, order: identifier matches
  first, then Team key, then number.
- `core/src/core/services/issues.py`: `list_user_issues` (cross-Team,
  Membership scope, 404-free) plus the shared `_issue_list_statement` /
  `_paginate_issues` / `user_teams` helpers — the keyset machinery is
  reused, not duplicated.
- `core/src/core/routers/search.py`: `GET /api/v1/search` →
  `{issues: [IssueResponse + team_key + team_name]}`.
- `core/src/core/routers/issues.py`: `team_id` is now optional on
  `GET /issues` (omitted → the user's Teams scope).
- `core/tests/test_search.py` (13): 400 on missing/blank `q`, title match
  (case-insensitive), identifier matches (full / partial / bare number),
  non-matches, archived exclusion, cross-Team scope, Admin-not-member
  exclusion, the 50-cap, response shape.
- `core/tests/test_my_issues.py` (8): assigned Issues across two Teams,
  out-of-scope Teams invisible (even to a workspace Admin), pagination
  cursor across the cross-Team scope, archived hidden, filters + sort
  apply cross-Team, zero Teams → 200 empty.
- `core/tests/domain/test_search.py` (6): the pure query rules (trim,
  one-char ok, `None`/`""`/blank → 400 message, cap value).
- `webapp/src/hooks/use-shortcut.ts`: `{ modifier: true }` option
  (Cmd **or** Ctrl, no other modifier), case-insensitive key match.
- `webapp/src/hooks/use-issue-list-keyboard.ts` (new): the list keyboard
  set — J/K/arrows (wrapping), Enter, S/A/P/L (first-row fallback),
  cursor by Issue id, disabled-guard (bulk mode / quick bar),
  `scrollIntoView` on move.
- `webapp/src/components/layout/SearchOverlay.tsx` (new): the global
  overlay — 150 ms debounce + AbortController, results grouped by Team,
  wrapping arrows, Enter → Issue detail + close, Esc / backdrop close,
  stateful (no cache).
- `webapp/src/components/layout/ShortcutCheatsheet.tsx` (new): the `?`
  cheat-sheet dialog.
- `webapp/src/components/layout/AppShell.tsx`: mounts the overlay +
  cheat-sheet; `/` and Cmd/Ctrl+K (toggle) + `?` shortcuts.
- `webapp/src/components/layout/Sidebar.tsx`: search trigger (icon +
  label + `/` kbd) and the always-visible My Issues link, above the Teams
  section (brief §7.1 order).
- `webapp/src/components/issues/IssueQuickActions.tsx` (new): the
  quick-edit bar (State/Assignee/Priority selects, Labels checkboxes;
  reuses the optimistic hooks; closes after an action).
- `webapp/src/components/issues/IssueCard.tsx`: `selected` cursor
  highlight (`ring-2 ring-accent` + `aria-current`) and `data-issue-id`.
- `webapp/src/lib/styles.ts` (new): `SELECT_CLASS` shared between the
  Team Issues list and the quick bar.
- `webapp/src/pages/TeamIssues.tsx`: the keyboard set wired (flat State
  groups), Esc precedence quick → bulk → cursor, quick bar wired.
- `webapp/src/pages/MyIssues.tsx` (new) + `router.tsx` `/my-issues`:
  cross-Team page (assignee = self), grouped by Team, load-more, sort,
  empty state "No Issues assigned to you", quick actions with
  cross-Team cache refresh.
- `webapp/src/api/issues.ts` + `query-keys.ts`: `listIssues(teamId?)`,
  `searchIssues(q, signal?)`, search schemas, `issues.myPage` key.
- `webapp/src/components/layout/SearchOverlay.test.tsx` (7): opens on `/`
  and Cmd/Ctrl+K, no plain-`k` open, grouped results + arrow wrap +
  Enter navigation, no-results + Esc, no fetch on empty query, shortcuts
  suppressed while typing in the search input.
- `webapp/src/components/layout/AppShell.test.tsx` (7): the shortcut set
  (C, `/`, Cmd/Ctrl+K, `?`), typing suppression, cheat-sheet close.
- `webapp/src/pages/MyIssues.test.tsx` (3): grouped by Team, empty state,
  load-more.
- `webapp/src/components/layout/Sidebar.test.tsx` (+2): My Issues link +
  search trigger above Teams (zero-Teams user), overlay opens from the
  trigger.
- `CONTEXT.md`: new glossary terms **My Issues** and **Search**.
- Verified: `make check` green (ruff ALL + mypy 110 files + biome),
  `make test-core` 381 passed, `make test-webapp` 100 passed,
  `pnpm --filter webapp run build` — no new tsc errors (the 2
  pre-existing Admin errors stay).

## Deferred (later tickets / later work)

- The quick-action callbacks are duplicated between the Team Issues list
  and My Issues (kept per-page — code-review deviation, see Decisions).
- No fuzzy/prefix search and no search in descriptions/Comments (brief
  §7.2.8: identifier or title only).
- Search results are not cached and the overlay has no history — a
  deliberate stateful view (recorded in Decisions).
- The Board stays drag-only (the keyboard set is list-only, as decided).
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` +
  `Admin.test.tsx` (2 errors, files untouched by this ticket) still
  fail `pnpm --filter webapp run build`; everything added here
  type-checks clean.
