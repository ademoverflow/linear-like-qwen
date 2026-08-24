# 03: Issue detail, edit & Activity

**What to build:** The Issue detail panel — inline-editable title, Markdown description with
edit/preview, the full properties column (State, Priority, Assignee, Labels, Parent, Due date,
Estimate) and the Activity feed — plus full Issue editing with optimistic-concurrency
protection and per-field Activity rows.

**Blocked by:** 01 (Core loop)

**Status:** done

- [x] The Issue detail (right-hand panel on wide screens, full page on narrow) shows the inline-editable title, the Markdown description (edit/preview, full GFM, sanitised) and the properties: State, Priority, Assignee, Labels, Parent, Due date, Estimate.
- [x] Any Member (or Admin) can edit any Issue field except number, creator and Team; each changed field emits exactly one Activity row with `from_value`/`to_value`; `PATCH` carries the last-seen `updated_at` and replies 409 when stale.
- [x] Assignee must be a Member of the Issue's Team (else rejected); parent must be in the same Team, one level deep, no cycles.
- [x] Property changes in the UI are optimistic (TanStack Query mutation) with rollback and a toast on error; the stale case (409) refetches and toasts.
- [x] The Activity feed in the detail shows the Issue's Activity rows chronologically.
- [x] Tests: stale `updated_at` → 409; one Activity per changed field; assignee/parent validation; non-member 404 (see Deferred — deliberate deviation from the 403 in this line); description sanitisation (no raw HTML in rendered output).


## Shipped (Phase 3)

**Backend** (`core/`)
- New `domain/issues.py` (pure, DB-free): title/description/priority/estimate validators.
- `activity.seq` BIGINT identity column + migration `c0de8a243260`: rows written in one
  transaction share `now()`, so `created_at, id` ordered nondeterministically; the
  migration backfills existing rows in `created_at, id` order and setvals the sequence
  (downgrade drops the column). The column is deliberately **not mapped** on the `Activity`
  model (docstring note; autogen caution under Deferred).
- Services (`services/issues.py`): `get_issue` (detail + parent's identifier/title),
  `update_issue` (ADR 0008: echoes the last-seen `updated_at`, 409 when stale; canonical
  field order for the Activity rows of one update — title, description, priority,
  assignee_id, parent_id, due_date, estimate — iterated in the service, not the router;
  exactly one `issue.updated` row per *changed* field with human-readable from/to —
  assignee → display name, parent → identifier, due_date → ISO date, estimate → string;
  assignee must be a Team member; parent must be same Team, one level deep, not self;
  explicit null title → 400 "Title is required"), `list_issue_activity` (oldest first,
  ordered by `seq`), and a shared `_visible_issue` helper (load / `can(ISSUE_VIEW)` /
  archived / 404; `for_update` locks the row for the write path).
- New read-only `GET /teams/{id}/members` (member-gated, 404 for outsiders) — the
  assignee-picker prerequisite (brief §9).
- New endpoints on `/api/v1`: `GET /issues/{id}`, `PATCH /issues/{id}`,
  `GET /issues/{id}/activity`; `number`, `creator_id` and `team_id` are immutable.

**Webapp** (`webapp/`)
- Issue detail route `/teams/$teamKey/issues/$issueId` (ticket 03): the Team's Issues in
  the left column on wide screens, the detail panel on the right; the panel is the full
  page on narrow screens (brief §7.1/§7.4). `IssueCard` now links to the detail.
- `IssueDetailPanel`: inline-editable title, Markdown description with edit/preview
  (full GFM, sanitised per ADR 0007 — `react-markdown` + `remark-gfm` + `rehype-sanitize`
  with an explicit allowlist in `lib/markdown.tsx`; no `dangerouslySetInnerHTML`), and
  the properties: State (display-only), Priority, Assignee (member picker), Labels
  ("No labels yet" placeholder), Parent (one level), Due date, Estimate.
- `ActivityFeed`: the Issue's Activity rows chronologically (oldest first).
- `useUpdateIssue`: optimistic TanStack Query mutation — the change is applied to the
  cached Issue, rolled back on error; on success the server response (authoritative
  `updated_at`) is written directly into the detail cache (merging the cached
  `parent_identifier`/`parent_title`) and the list cache, and only the Activity feed
  refetches — so the next edit echoes the real timestamp instead of the optimistic
  placeholder (removes the spurious-409 edge); a 409 refetches all three and toasts.
- New `Toast` primitive (`components/ui/Toast.tsx`).
- `updated_at` is a raw string in the Issue schema (`z.string()`, not `z.coerce.date()`):
  a JS Date truncates microseconds and would make every echo a 409.

**Tests**
- `core/tests`: 113 passing — `tests/test_issue_detail.py` (16): detail + parent
  fields, unknown/archived/non-member 404, one Activity row per changed field (and none
  for unchanged), stale `updated_at` → 409, assignee member/non-member, parent
  self/cross-team/one-level rules, clearing assignee + parent, oldest-first feed,
  invalid inputs (400 domain / 422 schema), null title → 400; `tests/domain/test_issues.py`
  (13): validator unit tests.
- `webapp`: 30 passing — `pages/IssueDetail.test.tsx` (4): identifier/title/properties
  render, sanitised Markdown (no raw HTML), chronological Activity feed, title edit saves
  with the last-seen `updated_at`, 409 rolls back and toasts; `lib/markdown.test.tsx`
  (6): sanitisation allowlist.

## Deferred (later tickets / later work)

- Non-members get **404, not the 403** named in the ticket's test line — the established
  convention (`core/src/core/domain/authz.py` docstring: "non-members get 404 on
  Team/Issue resources"), asserted in `test_non_member_cannot_view_or_edit_issue`.
- State is display-only (transitions land in ticket 04); Labels is a "No labels yet"
  placeholder (ticket 05); no comment thread (ticket 06).
- `activity.seq` is DB-managed and intentionally unmapped on the `Activity` model; the
  next `make db-migrate` autogen may propose `op.drop_column("activity", "seq")` — it
  must be removed (caution recorded in the model docstring).
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` + `Admin.test.tsx` (2 errors,
  files untouched by this ticket) still fail `pnpm --filter webapp run build`;
  everything added here type-checks clean.
