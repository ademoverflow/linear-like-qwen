# 03: Issue detail, edit & Activity

**What to build:** The Issue detail panel — inline-editable title, Markdown description with
edit/preview, the full properties column (State, Priority, Assignee, Labels, Parent, Due date,
Estimate) and the Activity feed — plus full Issue editing with optimistic-concurrency
protection and per-field Activity rows.

**Blocked by:** 01 (Core loop)

**Status:** ready-for-agent

- [ ] The Issue detail (right-hand panel on wide screens, full page on narrow) shows the inline-editable title, the Markdown description (edit/preview, full GFM, sanitised) and the properties: State, Priority, Assignee, Labels, Parent, Due date, Estimate.
- [ ] Any Member (or Admin) can edit any Issue field except number, creator and Team; each changed field emits exactly one Activity row with `from_value`/`to_value`; `PATCH` carries the last-seen `updated_at` and replies 409 when stale.
- [ ] Assignee must be a Member of the Issue's Team (else rejected); parent must be in the same Team, one level deep, no cycles.
- [ ] Property changes in the UI are optimistic (TanStack Query mutation) with rollback and a toast on error; the stale case (409) refetches and toasts.
- [ ] The Activity feed in the detail shows the Issue's Activity rows chronologically.
- [ ] Tests: stale `updated_at` → 409; one Activity per changed field; assignee/parent validation; non-member 403; description sanitisation (no raw HTML in rendered output).
