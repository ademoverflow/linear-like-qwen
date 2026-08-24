# 0013 — Comment edit/delete authz lives beside `can()`, not in it; Comment DELETE returns 204

**Status**: accepted

## Context

Ticket 06 (Comments) introduces two rules that do not fit the existing
conventions:

- Comment authorization depends on the **resource's author**: editing is
  author-only (no owner or Admin exception, brief §2); deletion is allowed
  for the author, a Team owner, or a workspace Admin. The centralized
  `can(actor, action, resource)` matrix (ADR 0004) decides from the actor's
  role on the resource's Team only — `Resource` carries a `team_id`, not an
  author — so an author-relative rule cannot be expressed in the matrix
  without changing its shape.
- Brief §9 says "every mutation returns the updated resource", but a
  deletion leaves no resource to return. Ticket 05 already shipped
  `DELETE /teams/{team_id}/labels/{label_id}` as `204 No Content`; the
  Comment delete follows the same convention.

Brief §10 requires an ADR for any deviation from §8/§9.

## Decision

- `can_edit_comment` / `can_delete_comment` live in `core/domain/comments.py`
  as pure functions over a plain `CommentRef` (`team_id`, `author_id`) —
  same layer and testability as `can()`, but outside the matrix because the
  decision needs resource metadata the matrix does not carry. `can()` is
  unchanged; no `Action` entries are added for Comments.
- `DELETE /issues/{issue_id}/comments/{comment_id}` returns **204 No
  Content** with no body. `POST` (201) and `PATCH` (200) return the
  Comment, as §9 requires.

## Consequences

- If a future ticket needs role-only Comment checks (e.g. "owners may edit
  any comment"), extend `Resource` with author metadata and fold the rules
  into `can()` then.
- Clients get no resource back from a delete and must invalidate/refetch
  (the webapp invalidates the Issue's Comments + Activity caches).
- The same rationale retroactively covers ticket 05's Label DELETE 204.
