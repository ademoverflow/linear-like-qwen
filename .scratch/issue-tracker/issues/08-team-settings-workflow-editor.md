# 08: Team settings & Workflow editor

**What to build:** The Team settings tabs (owner-only): members, labels, and the Workflow
editor — add/rename/recolor/reorder States with version-guarded concurrency, delete-with-migrate
for States that still hold Issues, and the category-minimum invariant.

**Blocked by:** 04 (Transitions & Board)

**Status:** ready-for-agent

- [ ] A Team owner can edit the Team's name and description; the key is immutable (no API or UI to change it); an Admin can archive a Team (hidden everywhere, data kept, reversible) and no Issues can be created in an archived Team.
- [ ] A Team owner manages members: add existing Users, set owner/member roles, remove members.
- [ ] The Workflow editor allows adding, renaming, recoloring and reordering (drag) Workflow States; every edit carries the last-seen State `version` and replies 409 when stale.
- [ ] A State with non-archived Issues can be deleted only with a `migrate_to_state_id` of the same category, in one transaction, with one Activity per moved Issue; a Team must always keep ≥ 1 State in each of unstarted, started, completed and canceled (violations return 422 on delete and on category change).
- [ ] Tests: category-minimum 422 (delete and category change); delete-with-migrate moves all Issues and writes Activities; stale version 409; archived Team rejects Issue creation; member management happy + 403.
