# CONTEXT.md — domain glossary

Use these terms exactly, in code, SQL, docs, tests, commits and UI copy. If you need a new term,
add it here in the same commit. Full definitions and rules: `PROMPT-linear-like.md` §2–§6.

| Term | Meaning | Not |
|---|---|---|
| **Workspace** | Single tenant root (v1 has exactly one). | org, tenant |
| **User** | A person with an account (`users` table). `is_active=false` = deactivated. | account, member (that's a Membership) |
| **Admin** | User with `is_admin=true`; workspace-wide privilege. | superuser, owner (that's a Team role) |
| **Team** | Unit of ownership; has a `key` like `ENG`. Every Issue belongs to one Team. | group, squad, project |
| **Membership** | User ↔ Team link with `role ∈ {owner, member}`. | |
| **Issue** | The core record; identifier `KEY-number`, e.g. `ENG-42`. | ticket, task, card, story, bug |
| **Identifier** | The human id `KEY-number`. Computed, never stored. | slug |
| **My Issues** | Personal view: Issues assigned to the current User, aggregated across all the Teams they belong to. | my tasks, my list |
| **Search** | Global read-only overlay matching Issue identifier or title substrings across the User's Teams. | query (as a verb), find |
| **Workflow** | A Team's ordered set of Workflow States. | pipeline, board (the board is a *view* of the workflow) |
| **Workflow State** | `name`, `category`, `color`, `position`. | status, column, stage |
| **Category** | One of `backlog, unstarted, started, completed, canceled`; semantic meaning of a State. | type |
| **Transition** | Moving an Issue from one State to another, via `core.domain.workflow`. | status update |
| **Label** | Team-scoped tag on Issues. | tag |
| **Comment** | Markdown text on an Issue by a User. | note, reply |
| **Activity** | Append-only audit row on an Issue (who changed what, from → to). | history, event, log |
| **Invitation** | Email + token letting someone register after bootstrap. | invite link (colloquial ok in UI) |
| **Archive** | Soft delete (`archived_at`). Reversible. | delete (reserve for hard delete) |
| **Hard delete** | Permanent removal, Admin only, confirmed by identifier. | purge |
| **Bootstrap** | The first registration, which creates the first Admin. | setup |
