# 07: Archive/restore & hard delete

**What to build:** The Issue lifecycle end: soft archive (owner/Admin) with full hiding from
default views and counts, restore, parent cascade rules, and Admin-only hard delete with
identifier confirmation and cascade.

**Blocked by:** 05 (Labels, list filters & bulk operations)

**Status:** done

- [x] A Team owner or Admin can archive an Issue (sets `archived_at`); archived Issues are hidden from all default views and counts, listable with `?include_archived=true`, and restorable.
- [x] Archiving a parent archives its children; restoring a parent does not auto-restore children.
- [x] Hard delete is Admin-only: the request body must repeat the Issue's identifier as confirmation; it cascades to Comments, Activity and label links; the Issue is permanently gone.
- [x] Tests: archived hidden from default list/counts and present with `?include_archived`; restore; parent cascade both directions; hard delete with wrong identifier rejected; 403 for non-owner/non-Admin archive, non-Admin hard delete.

## Decisions (recorded during Phase 3)

- **Endpoints** (brief §3.4; the brief does not name paths):
  `POST /issues/{issue_id}/archive` and `POST /issues/{issue_id}/restore`
  (200 + the updated Issue per brief §9), and `DELETE /issues/{issue_id}`
  with body `{"identifier": "ENG-42"}` (204 No Content, no body — the
  ADR 0013 delete precedent: nothing is left to return). No bulk restore
  endpoint: restore is per-Issue; the bulk bar keeps ticket 05's archive
  action.
- **`?include_archived=true`** lists archived Issues **alongside the
  active ones** (an inclusive flag, not an "archived only" view) and
  combines with every existing filter (brief §3.4: "listable with
  ?include_archived=true").
- **Authorization** (brief §5.2): archive = `can(ISSUE_ARCHIVE)`,
  restore = `can(ISSUE_RESTORE)` (both Team owner or Admin — the
  original draft reused `ISSUE_ARCHIVE` for restore, which read as
  double duty; code-review fix), hard delete = **Admin only** via
  `can(ISSUE_DELETE, None)`. The `Action` enum grew with
  `ISSUE_RESTORE`/`ISSUE_DELETE`; `ISSUE_DELETE` joins the new
  admin-only set alongside `TEAM_CREATE` (code-review fix: the
  original `actor.is_admin` gate bypassed `can()`, the single
  authorization entry point).
- **No 409**: archive/restore/hard delete accept no `updated_at`, so
  they cannot 409 — brief §3.3 ties optimistic concurrency to the
  PATCH echo (recorded per code review).
- **Activity rows**: no new kinds — the single ops reuse ticket 05's
  bulk-archive shape: `issue.updated` with `field="archived_at"`
  (archive: `to_value` = timestamp; restore: `from_value` = the old
  timestamp). The webapp renders those rows as "archived this Issue" /
  "restored this Issue".
- **Parent cascade** (brief §3.4): archiving a parent archives every
  **non-archived direct child** (the hierarchy is one level deep per
  brief §3.1); already-archived children are skipped. One Activity row
  per newly-archived Issue. Restoring a parent touches **only** the
  parent.
- **Hard delete scope**: removes the Issue **and its direct children**
  (the whole subtree), plus each one's Comments, Activity rows and
  Label links, in one transaction. The brief names Comments/Activity/
  label links; the `issues.parent_id` FK forces subtree handling, and
  "permanently gone" was read as the whole subtree (recorded here). No
  Activity row is written — the trail goes with the Issue.
- **Archived visibility**: archived Issues stay **404 on detail,
  comments and Activity** (ticket 03's locked behaviour), so restore
  happens **from the list** (per-row Restore, owner/Admin); double
  archive → 404 (already invisible), restore of a non-archived Issue →
  400.
- **Archived Team**: archive/restore → 403 like every other write into
  an archived Team; **hard delete by an Admin is allowed even in an
  archived Team** (the Team archive is a soft hide; the removal is a
  workspace-level Admin action).
- **Identifier confirmation**: trimmed, **case-sensitive exact match**
  against the canonical `KEY-number`; mismatch → 400 before anything is
  deleted. Pure domain rule (`confirm_identifier`), unit-tested.
- **Webapp**: "Archived" toggle in the list toolbar (aria-pressed,
  accent border when on; the flag joins the query key). Archived rows
  carry an "Archived" badge and **do not navigate** (the detail 404s
  while archived); owners/Admins get a per-row **Restore**. Detail
  header: **Archive** (owner/Admin, direct — it is reversible) and
  **Delete** (Admin only, identifier-confirmation dialog). Both return
  to the Team's Issues list on success. Plain non-optimistic mutations
  + cache invalidation (as for ticket 06's Comments; archiving/deleting
  are not in the brief §7.4 optimistic list).
- **No migration**: no schema changes (`archived_at` and `parent_id`
  already exist); the hard-delete cascade is explicit service-level
  deletes. **No new ADR**: the 204 delete follows ADR 0013; everything
  else follows the brief, and the choices above are recorded here.

## Shipped (Phase 3)

**Backend** (`core/`)
- `domain/issues.py`: `confirm_identifier` (pure: trimmed exact match,
  400 otherwise) + `MSG_IDENTIFIER_MISMATCH`.
- `domain/authz.py`: `Action` grows with `ISSUE_RESTORE` (owner-only,
  like archive) and `ISSUE_DELETE` (Admin-only, with `TEAM_CREATE` in
  the new `ADMIN_ONLY_ACTIONS` set) — code-review fix.
- `domain/listing.py`: `IssueQuery.include_archived` (default false).
- `services/issues.py`: `archive_issue` (owner/Admin; stamps
  `archived_at` on the Issue and its non-archived children; one
  `issue.updated` row per archived Issue), `restore_issue` (owner/Admin
  via `can(ISSUE_RESTORE)`; parent only; `from_value` = old timestamp),
  `hard_delete_issue` (Admin only via `can(ISSUE_DELETE)`; identifier
  confirmation; explicit cascade: children,
  then per Issue — label links, Comments, Activity rows, the row
  itself); `_visible_issue` gains `include_archived` (restore/hard
  delete reach archived rows); `list_issues` hides archived unless
  flagged.
- `routers/issues.py`: `POST /{issue_id}/archive` and
  `POST /{issue_id}/restore` (200 + `IssueResponse`),
  `DELETE /{issue_id}` (204, `IssueIdentifierRequest`), and the
  `include_archived` query param on the list.

**Webapp** (`webapp/`)
- `api/issues.ts`: `include_archived` list param; `archiveIssue` /
  `restoreIssue` / `deleteIssue` (204 → no body).
- `lib/permissions.ts`: `isOwnerOrAdmin` (owner or workspace Admin,
  client-side from `/auth/me` per ADR 0004), shared by the list, the
  detail header and the Comment cards (code-review fix — the
  predicate lived in two copies).
- `hooks/use-issue-actions.ts`: the three plain mutations share one
  `useIssueAction` factory (invalidate + toast; code-review fix) and
  expose `{ archive, restore, hardDelete }` (the API's `deleteIssue`
  naming; `delete` is not a valid binding name).
- `pages/TeamIssues.tsx`: the Archived toggle (the flag joins the
  query key), per-row Restore for owners/Admins.
- `components/issues/IssueCard.tsx`: "Archived" badge; archived cards
  render as plain cards (no navigation) + optional Restore action.
- `components/issues/IssueDetailPanel.tsx`: header Archive (owner/Admin)
  and Delete (Admin, identifier-confirmation dialog; the confirm field
  uses the `Input` primitive — code-review fix); both navigate back
  to the Team's Issues list on success.
- `components/issues/IssueFeed.tsx`: `archived_at` rows render as
  "archived this Issue" / "restored this Issue".
- `test/fixtures.ts`: `ISO` exported (test fixtures).

**Tests** (`make test-core` 261 passing, `make test-webapp` 63 passing)
- `core/tests/test_archive.py` (21): default list hides archived, the
  flag lists them (with the `archived_at` value) and combines with
  filters; archive by Admin and by a non-Admin owner, member → 403,
  non-member → 404, archived Team → 403, one Activity row, double
  archive → 404, parent cascades to children (already-archived children
  skipped); restore by owner/Admin, member → 403, non-member → 404,
  archived Team → 403, non-archived → 400, children stay archived,
  Activity `from_value`; hard delete by Admin (204; Issue, children,
  Comments, Activity and label links all gone; whitespace-tolerant
  identifier), an archived Issue in an archived Team, wrong identifier
  → 400 with nothing deleted, non-Admin owner → 403, non-member → 404.
- `core/tests/domain/test_issues.py` (+4): identifier exact match,
  trimming, mismatch → 400, empty → 400.
- `core/tests/domain/test_authz.py` + `test_authz_admin_actions.py`:
  `ISSUE_RESTORE` owner-only, `ISSUE_DELETE` Admin-only (code-review
  fix).
- `webapp` (63 passing): `TeamIssues.test.tsx` (+3: the toggle fetches
  with `include_archived` and the badge shows, restore fires from the
  row action, members see no Restore) and
  `pages/IssueDetail.test.tsx` (+3: archive returns to the list,
  members see neither Archive nor Delete, hard delete is gated on
  typing the exact identifier).

## Deferred (later tickets / later work)

- No "archived only" filter — `include_archived` is inclusive (see
  Decisions); a dedicated filter can be added if wanted.
- No per-Issue Archive action in the list (the detail header and the
  bulk bar cover archiving); restore is per-row in the list only.
- No bulk restore endpoint (restore is per-Issue; the bulk bar stays
  ticket 05's archive-only).
- Hard delete has no UI outside the Admin detail header, and the
  confirmation dialog names the children in prose only (no itemised
  count of what will be removed).
- Archived Issues remain **404 on detail/comments/Activity** (ticket
  03's locked behaviour): their content cannot be viewed, only
  restored from the list.
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` +
  `Admin.test.tsx` (2 errors, files untouched by this ticket) still
  fail `pnpm --filter webapp run build`; everything added here
  type-checks clean.
