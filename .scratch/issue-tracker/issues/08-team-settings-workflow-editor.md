# 08: Team settings & Workflow editor

**What to build:** The Team settings tabs (owner-only): members, labels, and the Workflow
editor — add/rename/recolor/reorder States with version-guarded concurrency, delete-with-migrate
for States that still hold Issues, and the category-minimum invariant.

**Blocked by:** 04 (Transitions & Board)

**Status:** done

- [x] A Team owner can edit the Team's name and description; the key is immutable (no API or UI to change it); an Admin can archive a Team (hidden everywhere, data kept, reversible) and no Issues can be created in an archived Team.
- [x] A Team owner manages members: add existing Users, set owner/member roles, remove members.
- [x] The Workflow editor allows adding, renaming, recoloring and reordering (drag) Workflow States; every edit carries the last-seen State `version` and replies 409 when stale.
- [x] A State with non-archived Issues can be deleted only with a `migrate_to_state_id` of the same category, in one transaction, with one Activity per moved Issue; a Team must always keep ≥ 1 State in each of unstarted, started, completed and canceled (violations return 422 on delete and on category change).
- [x] Tests: category-minimum 422 (delete and category change); delete-with-migrate moves all Issues and writes Activities; stale version 409; archived Team rejects Issue creation; member management happy + 403.
## Decisions (recorded during Phase 3)

- **Team edit** (`PATCH /teams/{id}`; the brief does not name the path): body is
  `name` + `description` only — the `key` is immutable and has **no API field at
  all** (ticket line 1). Owner or Admin (brief §5.2 "edit Team" → new owner-only
  action `TEAM_UPDATE`; Admins always pass). Description cap **5,000 chars**
  (Issue descriptions allow 50,000; Team descriptions are short) — applied to
  `POST /teams` too, where it was 255 (now consistent). Name stays 1–100,
  trimmed. An explicit `description: null` clears it; an empty payload → 400
  (nothing to update, the label convention). **No Activity row** (Activity is
  per-Issue only — recorded). 200 + the updated Team.
- **Team archive/restore** (brief §6, ticket line 1): `POST /teams/{id}/archive`
  and `POST /teams/{id}/restore`, both **Admin-only** (new admin-only actions
  `TEAM_ARCHIVE`/`TEAM_RESTORE` — "reversible" is read as the same privilege:
  the one who may archive may restore; owners may not). 200 + the updated Team;
  double archive → 404 (already invisible), restore of a non-archived Team → 400
  (ticket 07's Issue precedent). **Hidden everywhere**: `GET /teams` hides
  archived Teams from everyone **except Admins, who see them (with
  `archived_at` set) so Restore is reachable at all** — the sidebar badges them
  "Archived" (ticket 07's badge precedent; a deliberate, recorded deviation from
  "hidden everywhere" for the Admin view). Every other Team-scoped resource of
  an archived Team — Team detail (for non-Admins), Issues list/detail/Activity,
  Board (States), Members, Labels — is **404 on reads, 403 on writes** (restore
  is the one allowed write), the archived-Issue 404 pattern applied at the
  Team level. Issue creation in an archived Team already 403s via
  `MSG_TEAM_ARCHIVED`; asserted in a test (ticket line 5).
- **Members** (brief §5.2: owner = "manage members"):
  `POST /teams/{id}/members` (body `user_id`; 201 + the Membership), `PATCH
  /teams/{id}/members/{user_id}` (body `role`; 200 + the Membership), `DELETE
  /teams/{id}/members/{user_id}` (**204** — ADR 0013's delete precedent,
  nothing is left to return), `GET /teams/{id}/member-candidates`. All owner or
  Admin (new owner-only actions `MEMBER_ADD`/`MEMBER_ROLE`/`MEMBER_REMOVE`/
  `MEMBER_CANDIDATES`); a non-owner member is the ticket's genuine 403;
  non-members get 404; writes into an archived Team → 403.
  - **Add = existing Users only**, picked from `GET /teams/{id}/
    member-candidates`: the **active** Users who are **not** yet members of
    the Team (owner/Admin only), by display name/email. Chosen over
    add-by-email because a non-Admin owner has no other way to browse the
    User base (`GET /users` is Admin-only) — recorded. Adding a deactivated
    User id → 400; an unknown User → 404; a User who is already a member →
    409 (the `(user_id, team_id)` uniqueness, the label duplicate-name
    precedent). New members join as `member`.
  - **Ownership rules**: multiple owners are allowed (the Membership model
    has no single-owner constraint; ticket 01 seeds one). **Last-owner
    protection** (the brief §5.3 last-active-Admin rule, mirrored): demoting
    or removing the **last** owner → **422** (pure `assert_not_last_owner`,
    unit-tested). An owner demoting/removing **themselves** is allowed only
    while another owner remains (the same rule covers it). An **Admin may
    demote/remove any owner** (workspace privilege) — the last-owner
    invariant still applies (422 even for the Admin). Changing a role to the
    role the User already has → 400 (nothing to update).
  - **No Activity rows** (per-Issue only — recorded).
- **Workflow editor** (brief §4.3, ADR 0008): every endpoint owner or Admin
  (new owner-only actions `STATE_CREATE`/`STATE_EDIT`/`STATE_DELETE`), a
  non-owner member gets 403, non-members 404, writes into an archived Team
  403. `TeamStateResponse` and the webapp `workflowStateSchema` gain
  `version` (a raw int — never echoed as a timestamp).
  - `POST /teams/{id}/states` (name/category/color): the State is
    **appended at the end** (`position = max + 1`) and requires **no version
    echo** — it changes no existing State (ADR 0008: echo "the last-seen
    version of each state it changes"); the service locks the Workflow row so
    concurrent appends serialise on position allocation. Name 1–50 trimmed,
    unique per Workflow (409); category one of the five (400); colour
    `#RRGGBB` (400). 201 + the State (`version` 1).
  - `PATCH /teams/{id}/states/{state_id}`: `name?`/`color?`/`category?` plus
    a **required `version`** (stale → 409). A category change runs the
    category-minimum check (422, below). Nothing effectively changed → 400.
    The service **bumps `version`** (no DB trigger) and echoes the new value.
  - **Reorder**: `PATCH /teams/{id}/states/reorder` with the **full ordered
    list** `states: [{id, version}, …]` — one round-trip per drag; per-state
    position patches would race the unique `(workflow_id, position)` index
    (rejected in the Phase 1 grill, ADR 0008/0011 context — recorded here).
    Every version must match (any stale → 409); the list must be exactly the
    Workflow's States (missing/extra/duplicate id → 400). Positions are
    rewritten in one transaction **offset-then-settle** (all `position + n`,
    then the final values) so no intermediate duplicate is ever created.
    Versions are bumped only on rows whose position actually changed; an
    unchanged order → 400. 200 + the full list in the new order.
  - `DELETE /teams/{id}/states/{state_id}`: body `version` (required; stale
    → 409) + `migrate_to_state_id?`. **204** (ADR 0013).
- **Delete-with-migrate** (brief §4.3, ticket line 4):
  - The State has **non-archived** Issues → `migrate_to_state_id` is
    **required** (missing → 400). The target must belong to the same Workflow
    (400), not be the deleted State itself (400), and be of the **same
    category** (wrong category → **400** — invalid input, not an invariant
    violation; 422 is reserved for the category minimum — pick recorded).
  - **Archived Issues** in the State are migrated to the same target as well:
    the `issues.state_id` FK is plain (no cascade), so the row cannot be
    dropped while any Issue — archived or not — points at it, and blocking
    would leave such States undeletable forever. **Activity only for the
    non-archived** (matching "one Activity per moved Issue" — recorded),
    and **archived Issues keep their bookkeeping timestamps** — they are
    re-pointed to the target only, with no `transition()` effect and no
    `completed_at`/`canceled_at` change (code-review fix: the first
    version ran every moved Issue through `transition()`, which would
    have stamped fresh timestamps on frozen, archived Issues).
    Passing `migrate_to_state_id` while the State holds no Issues at all
    → 400 (nothing to migrate).
  - One transaction; each moved non-archived Issue goes through the domain
    `transition()` — the same code path `transition_issue` uses — so
    `issue.state_changed` plus the `completed_at`/`canceled_at` bookkeeping
    come for free (recorded: the domain path is reused, not the single-Issue
    service, which carries its own Issue-level guards).
  - **Category minimum** (brief §4.3): ≥ 1 State in each of `unstarted`,
    `started`, `completed`, `canceled` (**backlog is not in the minimum**).
    Enforced on delete and on category change → 422 (`RuleViolationError`).
    Pure rules in `domain/workflow.py` — `validate_state_deletion` (the
    brief's named file layout) and `validate_category_change` — unit-tested
    without a DB.
- **Version-guard mechanics** (ADR 0008, exact shape): add — none (no state
  changed); rename/recolor/category — the State's own `version`; reorder —
  each entry's `version`; delete — the deleted State's `version`. Stale on
  any of them → 409 with the server message; the **webapp never edits States
  optimistically** (the guard exists because last-write-wins would break the
  invariants) — 409 → refetch the States + toast (recorded). All state-edit
  responses carry the post-change version.
- **Settings UI** (brief §7.2.6/§6): new page `/teams/$teamKey/settings` with
  a Team section (name/description form for owner/Admin; Archive/Restore for
  Admins, two-step confirm) and tabs **Members / Labels / Workflow**. The
  sidebar **Settings link is shown to owners/Admins only** (brief §6: the
  tabs are owner-only); a non-owner member who reaches the URL sees an
  "owner access" message (the reads are member-visible, so there is no 403 to
  render). An archived Team (Admin view) renders the banner + Restore only,
  no tabs. Members tab: candidates picker (owner/Admin), role Select per
  member, two-step remove (the `LabelManagerDialog` pattern); a 422 surfaces
  as a toast. Labels tab: the dialog's content is extracted to a
  `LabelManager` component shared by the dialog (list toolbar, ticket 05) and
  the tab. Workflow tab: dnd-kit **sortable** vertical list (ADR 0006, the
  Board's wiring as reference; reordering States reorders Board columns for
  free, ADR 0011), an add-State dialog (name, category, `<input
  type="color">`), inline rename/recolor, category via Select, delete is
  two-step + a **migrate-to dialog** whose targets are restricted to the
  State's own category. The UI counts Issues from the Team's
  non-archived Issue list to decide whether to offer the dialog up
  front; the **endpoint is the source of truth** — a delete that 400s
  with "still has Issues" (the archived-only case the UI count cannot
  see) opens the same migrate-to dialog (code-review fix: the first
  version was a dead end there). All mutations are plain + cache
  invalidation (none of these are in the brief §7.4 optimistic list).
  (code-review fix: the first pass had the `createTeamState` client
  but no Add-State dialog; the dialog shipped with the tab.)
- **No Activity for Team/member/State edits** (per-Issue only — recorded);
  the only rows this ticket writes are `issue.state_changed` per moved Issue
  (via `record_activity` like every other service).
- **Archived-Team UI beyond the Settings page** (deliberate, recorded
  after code-review): the Issues list and the Board also render a
  "This Team is archived" message (with a settings link for
  owners/Admins) instead of their normal content — an archived Team is
  reachable in the Admin sidebar, so those routes must say something
  rather than 404 in the UI.
- **`update_team(changes: dict)`** (deliberate, recorded after
  code-review): the service takes the explicit field set the client sent
  (the router filters `model_fields_set` via `TEAM_UPDATE_FIELDS`),
  because an explicit `description: null` (clear) must stay
  distinguishable from an omitted field — separate optional parameters
  could not carry that.
- **Code-review fix**: Standards violations fixed before shipping —
  docstrings on the new private service helpers, one-line justifications
  on the new `# type: ignore`s, `MSG_CATEGORY_INVALID` constant in
  `domain/workflow.py`, and the candidates endpoint moved to the
  recorded path `GET /teams/{id}/member-candidates` (the first pass
  mounted it under `/members/candidates`).

- **No migration**: `teams.description` (Text), `teams.archived_at` and
  `workflow_states.version` all exist (verified against the initial migration
  + head `cc365a924274`). **No new ADR**: the 204s follow ADR 0013, the
  version mechanics follow ADR 0008, and the Admin-visible archived Team
  list is a small deviation recorded here (same spirit as ticket 07's badge).


## Shipped (Phase 3)

**Backend** (`core/`)
- `domain/authz.py`: `Action` grows with `TEAM_UPDATE`, `TEAM_ARCHIVE`,
  `TEAM_RESTORE`, `MEMBER_ADD`/`MEMBER_ROLE`/`MEMBER_REMOVE`/
  `MEMBER_CANDIDATES`, `STATE_CREATE`/`STATE_EDIT`/`STATE_DELETE`
  (owner-only) and `TEAM_ARCHIVE`/`TEAM_RESTORE` (in
  `ADMIN_ONLY_ACTIONS`).
- `domain/workflow.py`: `validate_state_name` (1–50, trimmed),
  `validate_state_color` (`#RRGGBB`), `validate_category` (the five),
  `validate_state_deletion` + `validate_category_change` (category
  minimum, 422), `assert_migration_target_same_category` (wrong
  category → 400), `MSG_CATEGORY_INVALID`.
- `domain/memberships.py` (new): `MembershipRef` +
  `assert_not_last_owner` (422 "A Team must keep at least one owner";
  pure, unit-tested).
- `services/teams.py`: `get_team` (Admins see archived; others 404),
  `update_team` (owner/Admin; name/description; explicit null clears;
  empty → 400; no Activity), `archive_team` / `restore_team`
  (Admin-only; double archive 404 / restore non-archived 400),
  `list_teams` (Admins also see archived Teams — recorded deviation),
  `_visible_team`; description cap 255 → 5,000 (applied to POST too).
- `services/memberships.py` (new): add (existing Users only, 201;
  deactivated 400 / unknown 404 / duplicate 409), role change (same
  role 400; last-owner 422), remove (204; last-owner 422),
  `list_member_candidates` (active non-members), `get_member_user`.
- `services/workflow_states.py` (new): `create_team_state` (append at
  end, no version echo, Workflow row locked), `update_team_state`
  (version echo, 409 stale, category minimum 422, no-op 400, version
  bump), `reorder_team_states` (full ordered list, offset-then-settle
  in one transaction, bump only moved rows, unchanged 400),
  `delete_team_state` (version + `migrate_to_state_id?`; 204; one
  transaction; moved non-archived Issues through the domain
  `transition()` → one `issue.state_changed` each; archived Issues
  re-pointed only, no Activity, no timestamp change — code-review
  fix).
- `services/{labels,issues,comments}.py`: archived-Team semantics —
  reads 404, writes 403 (restore is the one allowed write);
  `hard_delete_issue` stays allowed in archived Teams (ticket 07).
- `routers/teams.py`: `GET/PATCH /teams/{id}`,
  `POST /teams/{id}/archive|restore` (states/members moved out of this
  router).
- `routers/memberships.py` (new): `GET/POST /teams/{id}/members`,
  `PATCH/DELETE /teams/{id}/members/{user_id}` (204),
  `GET /teams/{id}/member-candidates`.
- `routers/workflow_states.py` (new): `GET/POST /teams/{id}/states`,
  `PATCH /teams/{id}/states/reorder` (declared before `PATCH /{state_id}`
  — UUID route ordering), `PATCH /teams/{id}/states/{state_id}`,
  `DELETE /teams/{id}/states/{state_id}` (204, body).

**Webapp** (`webapp/`)
- `api/teams.ts`: `version` on `workflowStateSchema`; `getTeam`,
  `updateTeam`, `archiveTeam`, `restoreTeam`,
  `listTeamMemberCandidates` (`teamMemberCandidateSchema`),
  `addTeamMember`, `updateTeamMemberRole`, `removeTeamMember` (204),
  `createTeamState`, `updateTeamState`, `reorderTeamStates`,
  `deleteTeamState` (204).
- `api/query-keys.ts`: `teams.detail`, `teams.candidates`.
- `test/fixtures.ts`: `version: 1` on every State fixture.
- `router.tsx`: the `/teams/$teamKey/settings` route; the Home
  redirect lands on the first **non-archived** Team.
- `components/layout/Sidebar.tsx`: Settings link (owner/Admin only,
  `isOwnerOrAdmin`), "Archived" badge for `archived_at != null` (Admin
  view).
- `pages/TeamIssues.tsx` + `pages/TeamBoard.tsx`: "This Team is
  archived" branch (settings link for owners/Admins).
- `pages/TeamSettings.tsx` (new): Team section (name/description form
  for owner/Admin; two-step Archive for Admins) + Members / Labels /
  Workflow tabs; non-owner member → "owner access" message; archived
  Team → banner + two-step Restore (Admin), no tabs.
- `components/teams/SettingsMembersTab.tsx` (new): member list with
  role Select, two-step remove, candidate picker (add existing Users).
- `components/teams/SettingsWorkflowTab.tsx` (new): dnd-kit sortable
  vertical list (ADR 0006), Add-State dialog (name/category/colour),
  inline rename/recolor, category Select, two-step delete; the
  migrate-to dialog (same-category targets) opens for a State that
  visibly holds Issues **and** whenever the server 400s a delete
  (archived-only Issues — code-review fix); 409 → refetch + toast,
  never optimistic (ADR 0008).
- `components/teams/LabelManager.tsx` (new): the label management
  content extracted from `LabelManagerDialog`, now shared by the
  dialog (list toolbar, ticket 05) and the Labels tab.

**Tests** (`make test-core` 354 passing, `make test-webapp` 81 passing)
- `core/tests/test_team_settings.py` (35): Team detail (member/
  non-member/archived-Admin-only), edit (owner/Admin 200, member 403,
  non-member 404, archived 403, invalid name, empty payload,
  description cap), archive/restore (Admin-only, double archive 404,
  restore non-archived 400, member hidden / Admin still sees),
  archived Team rejects Issue creation + hides Issue views, member
  add/role/remove happy + 403/404/409/400/422 (last owner, incl.
  self), candidates (active non-members, 403/404).
- `core/tests/test_workflow_states.py` (40): listing carries version;
  add (append, admin/owner/member 403/non-member 404, validation,
  archived 403); edit (rename bumps version, recolor, recategorise,
  category minimum 422, stale 409, duplicate name 409, no-op 400,
  unknown/foreign 404, member 403/non-member 404, archived 403);
  reorder (full rewrite, partial bump, incomplete 400, stale 409,
  unchanged 400, 403/404, archived 403); delete + delete-with-migrate
  (204, target required, wrong category 400, foreign target 400,
  archived-only needs a target, no-Activity for archived, migrate
  keeps archived timestamps, required-category 422, moves Issues +
  one Activity each + `completed_at` bookkeeping, stale 409, 403/404,
  archived 403).
- `core/tests/domain/test_memberships.py` (5): last-owner rule
  (remove/demote blocked, two owners fine, members never blocked,
  deactivated owners still count).
- `core/tests/domain/test_workflow.py`: category minimum (delete and
  category change), migration-target category, name/colour/category
  validation.
- `core/tests/domain/test_authz.py` + `test_authz_admin_actions.py`:
  the new actions' owner/Admin semantics.
- `core/tests/test_archive.py`, `test_comments.py`, `test_transitions.py`:
  ticket 04/06/07 tests updated for the new archived-Team 404 reads.
- `webapp/src/pages/TeamSettings.test.tsx` (15): owner section +
  tabs, non-owner message, archived banner + Restore, Team save,
  two-step archive, member role change / add from candidates /
  two-step remove, States list with Issue counts, rename with version
  echo, stale 409 → toast + refetch, migrate-to dialog
  (same-category targets, archived-only fallback via 400), direct
  delete, Add-State dialog.
- `webapp/src/components/layout/Sidebar.test.tsx` (3): Settings link
  owner/Admin only, hidden for plain members, Archived badge.

## Deferred (later tickets / later work)

- Deleting a State leaves **position gaps** (the remaining States are
  not renumbered): positions are an ordering, not displayed values, so
  nothing breaks — but a cleanup/renormalise could land later.
- No Team-level Activity: Team edits, member changes and State edits
  are not audited (Activity is per-Issue only, `issue_id` NOT NULL);
  the only rows this ticket writes are `issue.state_changed` per
  migrated Issue.
- No "add member by email" (the candidates picker was chosen —
  Decisions); inviting non-Users stays ticket 02's invitation flow.
- Reordering is tested at the API level (the dnd-kit drag itself is
  not simulated in jsdom, same as the Board).
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` +
  `Admin.test.tsx` (2 errors, files untouched by this ticket) still
  fail `pnpm --filter webapp run build`; everything added here
  type-checks clean.
