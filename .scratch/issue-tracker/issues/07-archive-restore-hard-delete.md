# 07: Archive/restore & hard delete

**What to build:** The Issue lifecycle end: soft archive (owner/Admin) with full hiding from
default views and counts, restore, parent cascade rules, and Admin-only hard delete with
identifier confirmation and cascade.

**Blocked by:** 05 (Labels, list filters & bulk operations)

**Status:** ready-for-agent

- [ ] A Team owner or Admin can archive an Issue (sets `archived_at`); archived Issues are hidden from all default views and counts, listable with `?include_archived=true`, and restorable.
- [ ] Archiving a parent archives its children; restoring a parent does not auto-restore children.
- [ ] Hard delete is Admin-only: the request body must repeat the Issue's identifier as confirmation; it cascades to Comments, Activity and label links; the Issue is permanently gone.
- [ ] Tests: archived hidden from default list/counts and present with `?include_archived`; restore; parent cascade both directions; hard delete with wrong identifier rejected; 403 for non-owner/non-Admin archive, non-Admin hard delete.
