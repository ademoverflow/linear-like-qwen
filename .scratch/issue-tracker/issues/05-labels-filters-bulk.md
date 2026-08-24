# 05: Labels, list filters & bulk operations

**What to build:** Team-scoped Labels (owner-managed) applied to Issues, the full list
toolbar — filters by State/Assignee/Label/Priority, sort by created/updated/priority, cursor
pagination — and the all-or-nothing bulk operation endpoint.

**Blocked by:** 03 (Issue detail, edit & Activity)

**Status:** done

- [x] A Team owner can create, rename, recolor and delete Team-scoped Labels.
- [x] A Team member can add and remove Labels (same Team) on an Issue; each add/remove emits one Activity row.
- [x] The Issues list supports filters by state, assignee, label and priority (combinable), sorting by created/updated/priority, and cursor pagination (default 50, max 200).
- [x] The bulk endpoint accepts `issue_ids[]` (same Team) and one of: `state_id`, `assignee_id`, `add_label_ids`, `remove_label_ids`, `archive: true`; it is all-or-nothing in one transaction and writes one Activity per Issue.
- [x] Tests: label scope (other-Team label rejected); bulk all-or-nothing (one invalid id → nothing changes); filter/sort correctness; cursor pagination (page boundaries, max limit); one 403 per new endpoint.

## Decisions (recorded during Phase 3)

- **List response shape**: an envelope `{issues: [...], next_cursor: string | null}`
  (not array + header — the client is a plain JSON fetch wrapper and an envelope is
  unambiguous). All consumers updated: the list page uses a paginated `issues.list`
  cache; the Board and the Issue-detail sidebar fetch the Team's full set by paging
  through with `limit=200` until `next_cursor` is null (`listAllIssues`); the
  optimistic hooks keep writing the full `issues.team` cache and additionally
  invalidate the paginated list queries.
- **Sort**: `sort={created|updated|priority}:{asc|desc}`; default `created:desc`;
  tie-breaker `number desc` (stable, human-meaningful). Priority rank: urgent >
  high > medium > low > none (pure `PRIORITY_RANK` in the domain layer).
- **Pagination**: keyset (cursor) pagination — the cursor is an opaque base64 of the
  last row's (sort value, number, id); default `limit=50`, allowed 1–200
  (out of range → 400), malformed cursor → 400.
- **Filters**: repeated query params `state_id`, `assignee_id`, `label_id`,
  `priority` (AND across fields, OR within one); the label filter is an EXISTS over
  the M2M, so other-Team labels match nothing.
- **Label model**: `Label` (`name` 1–50 chars, trimmed, case-sensitive and unique per
  Team; `color` `#RRGGBB` hex, same format as Workflow State colours) + `IssueLabel`
  (unique `(issue_id, label_id)`). Both tables get the usual `updated_at` trigger.
- **Label management** (`/teams/{id}/labels`, brief §9): GET is member-gated;
  POST/PATCH/DELETE are owner-gated — a non-owner mutation is the ticket's genuine
  403 (`ForbiddenError`), non-members get 404 (the established ticket 03/04
  convention). Duplicate name → 409. Renaming/recoloring updates Issues' cached
  label data via cache invalidation (no per-Issue Activity — the Issue was not
  edited).
- **Deleting a Label** removes its links from all Issues (Linear behaviour); it
  emits no Activity rows (the Issues' label set changed by the Label's
  disappearance, not by an edit of the Issues).
- **Labels on Issues**: `PATCH /issues/{id}` gains a managed `label_ids` field
  (full-set replace; every id must be a Label of the Issue's Team, else 400).
  Exactly one `issue.updated` Activity row per added label (`to_value` = name) and
  per removed label (`from_value` = name), field `label_id`; removed before added,
  name-ordered (deterministic feed order).
- **Bulk endpoint** (`POST /issues/bulk`): exactly one of `state_id`,
  `assignee_id`, `add_label_ids`, `remove_label_ids`, `archive: true` (none or
  several → 400). All-or-nothing in one transaction: everything is validated
  before anything is written (unknown id, already-archived Issue, cross-Team
  state, non-member assignee, other-Team label → 400, nothing changes); Issues
  must share one Team (mixed → 400). Non-member → 404 (convention); archived
  Team → 403. **Only `archive: true` is owner-gated (403)** — the other actions
  follow the single-Issue rules (any member), matching brief §5.2. **No
  `updated_at` echo**: bulk stays unversioned (brief §4.4; ADR 0008
  "Bulk operations remain unversioned"). The `state_id` action goes through the
  domain `transition()` (timestamp stamping + `issue.state_changed`); Issues
  already in the target State are skipped. One Activity row per Issue (per
  added/removed label for label actions). Response: `{issues: [...]}` (every
  mutation returns the updated resources).
- **List UI** (brief §7.2.2): the list is **grouped by State** (position order,
  only non-empty groups) — introduced now, replacing the flat card stack.
  Toolbar: Filter dialog (multi-checkbox per dimension, combinable), sort Select,
  "Load more" for the next cursor page, and an owner-only "Labels" button (the
  Team Settings screen is ticket 08, so the Labels manager ships as a dialog
  here: create / rename / recolor / delete).
- **Label chips**: `LabelChip` (coloured dot = the Label's own colour) on the
  list cards, the Board cards and the detail panel; the detail-panel Labels
  property is a picker (dialog with checkboxes) applying the change optimistically
  through `useUpdateIssue` with the raw last-seen `updated_at` (ADR 0008).
- **Bulk UI**: a minimal selection mode on the list (checkboxes + a bulk bar with
  State, Assignee and — owner-only — Archive). The bulk mutation is
  **not** optimistic (all-or-nothing; on success the Issues caches are
  invalidated and refetched). Bulk add/remove **labels in the UI is deferred**
  (the endpoint supports it).

- **Labels list order**: the Labels `GET` orders case-insensitively by name
  (`lower(name), name`), then exact name — Linear-style; recorded here (a small
  addition to "case-sensitive and unique per Team").
- **Cross-sort cursors are 400**: a cursor is only valid for the sort that
  encoded it; reusing it with another sort key is rejected (400) by
  `validate_cursor_for_sort` (domain). Without the guard, mixing an ISO
  timestamp cursor with a priority sort (or vice versa) reaches Postgres with
  incompatible types and becomes a 500.

## Shipped (Phase 3)

**Backend** (`core/`)
- Models: `models/label.py` (`Label`: `team_id`, `name` 1–50 chars, `color`
  `#RRGGBB`; unique per Team on `(team_id, name)`) and `models/issue_label.py`
  (`IssueLabel` M2M link with its own id/timestamps, unique per
  `(issue_id, label_id)`); `Issue.labels` and `Team.labels` relationships.
- Migration `98e47c2c4be7`: both tables + indexes + the usual `updated_at`
  triggers; downgrade drops them (verified).
- `domain/labels.py` (pure): `validate_label_name` (trim, 1–50) and
  `validate_label_color` (`#RRGGBB`).
- `domain/listing.py` (pure): `parse_sort` (`created|updated|priority:asc|desc`,
  default `created:desc`), `validate_limit` (1–200, default 50),
  `validate_priorities`, `PRIORITY_RANK` (urgent > high > medium > low > none),
  and the opaque base64 keyset cursor (`encode_cursor`/`decode_cursor`/
  `validate_cursor_for_sort`; value + `number` tie-breaker + id).
- `domain/issues.py`: `BulkAction` + `parse_bulk_action` (exactly one action;
  none or several → 400). `domain/authz.py`: `OWNER_ONLY_ACTIONS`
  (Label create/edit/delete, Issue archive) — a non-owner mutation is the
  ticket's genuine 403.
- `services/labels.py`: `list_team_labels` (member-gated, case-insensitive name
  order), `create_team_label` (owner; 409 on duplicate name),
  `update_team_label` (owner; 409 on rename to an existing name; 400 when
  nothing to update), `delete_team_label` (owner; removes all `IssueLabel`
  links, no Activity rows). Non-members get 404 on every endpoint
  (ticket 03/04 convention); a Label of another Team is invisible (404).
- `services/issues.py`:
  - `list_issues` now returns `(team, page, next_cursor)` — filters
    (`state_id`/`assignee_id`/`priority` as `IN`, `label_id` as an `EXISTS` over
    the M2M, AND across fields / OR within one), sort with `number desc`
    tie-breaker, keyset pagination (`limit + 1` fetch for `has_more`; the cursor
    is the last row's sort value + number + id). Cross-sort cursors → 400.
  - `update_issue` gains the managed `label_ids` field (full-set replace; every
    id must be a Label of the Issue's Team else 400): one `issue.updated`
    Activity per added label (`to_value` = name) and per removed label
    (`from_value` = name), removed rows first then added, each name-ordered;
    re-sending the same set is a no-op.
  - `bulk_update_issues` (brief §4.4): one transaction, all-or-nothing — every
    id and value is validated before anything is written (unknown id, mixed
    Teams, already-archived Issue, cross-Team State, non-member assignee,
    other-Team Label → 400, nothing changes); non-member → 404, archived Team →
    403, non-owner archiving → 403. `state_id` goes through the domain
    `transition()` (Issues already in the target State are skipped); one
    Activity row per Issue (per added/removed label for label actions). Unversioned
    (no `updated_at` echo; ADR 0008).
- Routers: `GET/POST /teams/{id}/labels`, `PATCH/DELETE
  /teams/{id}/labels/{label_id}`; `POST /issues/bulk` (`{issues: [...]}`
  response); `GET /issues` gains `state_id[]`, `assignee_id[]`, `label_id[]`,
  `priority[]`, `sort`, `cursor`, `limit` and returns the `{issues,
  next_cursor}` envelope. Every Issue response now embeds `labels`.

**Webapp** (`webapp/`)
- `api/issues.ts`: `issueLabelSchema` (composed from the Teams `labelSchema`),
  the `IssueListPage` envelope, `listIssues(params)`, `listAllIssues` (pages
  through with `limit=200` until `next_cursor` is null),
  `issueBulkResponseSchema` + `bulkUpdateIssues`. `api/teams.ts`:
  `labelSchema` + `listTeamLabels`/`createTeamLabel`/`updateTeamLabel`/
  `deleteTeamLabel`. `queryKeys.teams.labels` + `queryKeys.issues.page`.
- `TeamIssues`: toolbar with a Filter button (shows the active filter count),
  a sort Select, an owner-only Labels button and Select/Done (selection mode).
  The list is **grouped by Workflow State** (position order, non-empty groups
  only, §7.2.2) replacing the flat card stack; "Load more" appends the next
  cursor page to the same cache; the empty state distinguishes "No Issues
  match the filters" (with a Clear button) from "No Issues yet — press C".
- `IssueFilterDialog`: multi-checkbox per dimension (State, Assignee, Label,
  Priority), combinable, applied live; "Clear" resets all.
- `LabelManagerDialog` (owner; reached from the list toolbar because Team
  Settings is ticket 08): create (colour + name form), rename (blur/Enter
  commits), recolor (native colour input, blur commits), delete (two-step
  confirm button); invalidates the Team's labels and the Issues caches
  (Issues embed their Labels).
- `LabelChip` (dot = the Label's own colour, compact variant for the narrow
  Board cards) on the list `IssueCard`s and the Board cards.
- `IssueDetailPanel`: the Labels property is a picker (dialog with a checkbox
  per Team Label) that applies the full set through `useUpdateIssue` —
  optimistic with rollback, raw last-seen `updated_at` echo (ADR 0008), 409 →
  refetch + toast.
- `useUpdateIssue`/`useTransitionIssue` now also patch the paginated
  `issues.page` caches optimistically (snapshot + rollback + 409
  invalidation), keeping list and detail consistent.
- `useBulkIssues`: deliberately **not** optimistic (all-or-nothing); on success
  all Issue caches are invalidated and refetched; error → toast with the
  server message.
- Selection mode on the list: a checkbox per IssueCard; a bulk action bar
  (bottom, fixed) with Set State…, Assign to… and — owner-only — Archive,
  plus Clear/Done. Bulk add/remove **Labels in the UI is deferred** (the
  endpoint supports it).
- Board and Issue-detail sidebar consume `listAllIssues` for the Team's full
  set (the Board needs every Issue for DnD; ADR 0011).

**Tests** (`make test-core` 220 passing, `make test-webapp` 46 passing)
- `core/tests/test_labels.py` (11): owner CRUD incl. case-insensitive listing
  order; non-owner create/PATCH/DELETE → 403; non-member GET/POST/PATCH/DELETE
  → 404 (incl. unknown Team); duplicate name → 409 (create and rename onto an
  existing name); invalid name/colour → 400; a Label of another Team is 404
  on PATCH/DELETE; deleting a Label removes its links from Issues.
- `core/tests/test_issue_list.py` (17): envelope shape + embedded labels;
  filters by state / priority (+AND combination) / assignee / label (incl.
  other-Team label matching nothing); sort by created (default + asc) /
  updated / priority (both directions); pagination page boundaries (52 Issues,
  50+2), tied sort values across pages in both directions, `limit=1`/`200` and
  out-of-range → 400; invalid sort/cursor/priority → 400; cross-sort cursor →
  400 (both directions); archived Issues hidden; non-member and unknown Team →
  404.
- `core/tests/test_bulk.py` (14): transition action (timestamp stamping, one
  `issue.state_changed` per moved Issue, same-State Issues skipped); assignee
  action (one `issue.updated` per Issue); add/remove label actions (one
  Activity per label per Issue); archive by owner (stamp + Activity + hidden
  from the list) and by member → 403; all-or-nothing (one unknown id → 400,
  nothing changes); already-archived Issue → 400; mixed Teams → 400;
  cross-Team State → 400; other-Team Label → 400; assign to a non-member User →
  400; non-member → 404; no action / `archive: false` / several actions → 400;
  archived Team → 403.
- `core/tests/test_issue_detail.py` (+4): `label_ids` full-set replace with one
  Activity per added/removed label (removed before added, name-ordered; empty
  list clears; re-sending the same set is a no-op); other-Team Label → 400;
  unknown Label → 400; a plain (non-Admin) Team member can set `label_ids`.
- Pure domain tests (no DB): `domain/test_listing.py` (13: sort parsing,
  limits, priorities, cursor round-trip, cross-sort rejection),
  `domain/test_labels.py` (5), `domain/test_bulk.py` (3: exactly-one-action),
  `domain/test_authz.py` (+owner-only actions).
- `webapp`: 46 passing — `TeamIssues.test.tsx` (9: State grouping with
  counts, toolbar (Filter count / sort / owner-only Labels), selection mode +
  bulk bar (incl. owner-only Archive), filter count + empty-match state,
  Load-more wiring), `IssueDetail.test.tsx` (6, incl. the Labels picker),
  plus the existing Board/IssueDetail/Admin/About/client suites (the Board and
  list hooks now carry the `issues.page` cache patching).

## Deferred (later tickets / later work)

- Non-members get **404, not 403** on the Labels endpoints and the bulk
  endpoint — the established ticket 03/04 convention. The genuine 403s: a
  **non-owner mutating a Label** (the ticket's named 403), **archiving by a
  non-owner**, writes into an **archived Team**, and the **deactivated User**
  middleware (asserted as usual).
- Bulk add/remove **Labels in the UI** is deferred (the endpoint supports
  `add_label_ids`/`remove_label_ids`); the bulk bar ships with State, Assignee
  and owner-only Archive only.
- The Label management UI ships as a dialog on the list toolbar; it moves to
  Team Settings (ticket 08) when that screen exists.
- The bulk mutation is not optimistic (all-or-nothing semantics make
  speculative UI risky); success invalidates and refetches the Issue caches.
- The compact toolbar/bulk `<select>`s use a shared `SELECT_CLASS` constant in
  `TeamIssues.tsx` instead of `ui/Select` — that component renders a visible
  label, which does not fit the dense toolbar (judgement call).
- Code-review judgement calls left for later (no behaviour impact): a shared
  per-Issue applier in `services/issues.py` (the bulk state/assignee/label
  branches mirror the single-Issue helpers), a shared optimistic
  `issues.page` cache-patch helper between `useUpdateIssue`/
  `useTransitionIssue`, and one shared "visible Team" helper instead of the
  per-service copies (`services/labels.py` has its own `_visible_team`).
