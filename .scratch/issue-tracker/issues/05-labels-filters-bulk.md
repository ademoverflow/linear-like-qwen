# 05: Labels, list filters & bulk operations

**What to build:** Team-scoped Labels (owner-managed) applied to Issues, the full list
toolbar — filters by State/Assignee/Label/Priority, sort by created/updated/priority, cursor
pagination — and the all-or-nothing bulk operation endpoint.

**Blocked by:** 03 (Issue detail, edit & Activity)

**Status:** ready-for-agent

- [ ] A Team owner can create, rename, recolor and delete Team-scoped Labels.
- [ ] A Team member can add and remove Labels (same Team) on an Issue; each add/remove emits one Activity row.
- [ ] The Issues list supports filters by state, assignee, label and priority (combinable), sorting by created/updated/priority, and cursor pagination (default 50, max 200).
- [ ] The bulk endpoint accepts `issue_ids[]` (same Team) and one of: `state_id`, `assignee_id`, `add_label_ids`, `remove_label_ids`, `archive: true`; it is all-or-nothing in one transaction and writes one Activity per Issue.
- [ ] Tests: label scope (other-Team label rejected); bulk all-or-nothing (one invalid id → nothing changes); filter/sort correctness; cursor pagination (page boundaries, max limit); one 403 per new endpoint.
