# 11: Seed

**What to build:** `make seed` — a one-command realistic Workspace for demos and development:
an Admin, two Teams, four Users with memberships, and ~40 Issues spread across the States
with Labels and Comments. Idempotent.

**Blocked by:** 06 (Comments), 07 (Archive/restore & hard delete)

**Status:** ready-for-agent

- [ ] `make seed` creates: Admin `admin@example.com` (password printed once), Teams `ENG` and `DSGN`, four Users with Team memberships, and ~40 Issues across Workflow States with Labels and Comments.
- [ ] The seed is idempotent: running it twice creates nothing new and changes nothing.
- [ ] The seeded data exercises the full domain (every State category, every priority, labels, comments, at least one archived Issue).
- [ ] Test: seed runs against the test database and the expected counts/assertions hold; a second run is a no-op.
