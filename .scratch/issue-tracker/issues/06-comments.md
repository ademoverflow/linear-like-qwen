# 06: Comments

**What to build:** A Comments thread on the Issue detail — create, edit by author, delete by
author/Team owner/Admin — merged chronologically with Activity into the issue's story.

**Blocked by:** 03 (Issue detail, edit & Activity)

**Status:** done

- [x] Any User with access to the Issue can write a Markdown Comment (full GFM, sanitised).
- [x] A Comment author can edit their own Comment; a Comment can be deleted by its author, a Team owner, or an Admin.
- [x] Comments and Activity appear merged chronologically in the Issue detail feed; comment create/update/delete each emit Activity rows.
- [x] Tests: happy-path + one 403 per new endpoint; only the author can edit (403 otherwise); deletion by author / owner / Admin; non-member cannot comment (404 on the Issue).

## Decisions (recorded during Phase 3)

- **Endpoints** (brief §9 lists `/issues/{id}/comments`): `POST/GET
  /issues/{issue_id}/comments` and `PATCH/DELETE
  /issues/{issue_id}/comments/{comment_id}` — nested under the Issue, like
  `/issues/{id}/activity` and `/issues/{id}/transitions` (the handoff's
  shorthand `PATCH /comments/{comment_id}` was implemented Issue-scoped so a
  Comment of another Issue is a 404). `POST` (201) and `PATCH` (200) return
  the updated Comment per brief §9; `DELETE` returns **204 No Content** —
  a deliberate §9 deviation, recorded in ADR 0013 (same as ticket 05's
  Label DELETE).
- **Model**: `Comment` (`issue_id`, `author_id`, `body` Text, `edited_at?`,
  timestamps). Body cap **20,000 chars** (the Issue description allows 50,000
  per brief §3.1); the cap is enforced in the domain **after** trimming
  (20,000 + whitespace is valid; empty → 422 via the schema, whitespace-only
  → 400 via the domain); one shared `CommentBodyRequest` serves POST and
  PATCH (the two were identical — code-review fix). `issue_id`
  is `ON DELETE CASCADE` so ticket 07's hard delete removes Comments without
  extra code; `author_id` is a plain FK (v1 never hard-deletes Users —
  deactivation only).
- **`activity.comment_id`** (new nullable column, **deliberately FK-less** —
  a `comment.deleted` row outlives the Comment, plus an index): identifies
  which Activity rows belong to which Comment, so a deletion removes exactly
  that Comment's `comment.created`/`comment.updated` rows.
- **Activity rows**: new kinds `comment.created`, `comment.updated`,
  `comment.deleted` — exactly one per create/update/delete (ticket line 3).
  No `from_value`/`to_value`: the feed renderer derives the text from the
  kind, and the body is not duplicated into the audit row. Re-sending the
  same body on an edit is a no-op (no Activity row, no new `edited_at`).
- **Delete semantics**: the row is removed outright (hard delete — Comments
  are not archived). The Comment's `comment.created`/`comment.updated` rows
  are removed and a single `comment.deleted` row is written, so the feed
  keeps a Linear-style "X deleted a Comment" trail.
- **Edit**: the author may edit **repeatedly**, each change stamping
  `edited_at` (shown as an "edited" marker on the card). Comments are
  **unversioned** — no `updated_at` echo (ADR 0008 scopes optimistic
  concurrency to Issues and Workflow States). The frontend `created_at` is a
  JS Date because it is never echoed (unlike the Issue `updated_at` raw
  string).
- **Authorization** (brief §2/§5.2): edit = **author only** (no owner or
  Admin exception); delete = **author, Team owner, or Admin**. The composite
  rules live in `domain/comments.py` as pure functions over plain data
  (`can_edit_comment` / `can_delete_comment` over a `CommentRef`) — they do
  not fit the single-action `can()` matrix (the decision depends on the
  resource's author, which `Resource` does not carry); ADR 0013 records
  the deviation.
- **`GET /issues/{id}/comments`**: the **full list, oldest first**
  (`created_at, id`), no pagination in v1 (like the Activity feed). The
  merged feed needs every Comment to align with its `comment.created` row,
  which pagination would break.
- **Merged feed** (brief §7.2.3): **client-side merge of the two existing
  queries** — a pure `mergeFeed(activities, comments)` in `lib/feed.ts`
  (unit-tested). Rows are paired to Comments **by `comment_id`** (set on
  every `comment.*` Activity row, exposed on `ActivityResponse` and the
  webapp's `activitySchema`; rows without an id fall back to creation
  order), so tied `created_at` timestamps cannot misplace a card — the
  original i-th-row/i-th-Comment pairing broke on ties (code-review
  fix). The Comment's own `comment.created` row is **replaced by the
  Comment card** (no duplicate "commented" line); deletion removes the
  row and its Comment together, so surviving rows always pair with a
  surviving Comment. `comment.updated` rows
  render as an "edited their Comment" line (the card also carries the
  "edited" marker); `comment.deleted` rows render as a line. A Comment
  without a surviving row (should not happen) is appended, creation-ordered.
  `GET /issues/{id}/activity` is unchanged (ticket 03's shape tests still
  pass).
- **Webapp**: the Story section (replacing the old Activity feed) shows the
  merged feed plus a **comment composer at the bottom** (Write/Preview GFM,
  mirroring the description editor; ADR 0007 pipeline for render). Inline
  edit for own Comments; **two-step delete confirm** (the
  `LabelManagerDialog` pattern). Comments use **plain mutations + cache
  invalidation** — the brief §7.4 optimistic list (state/assignee/priority/
  label) does not name Comments, so speculative UI was skipped.
- **403 line**: the genuine 403s are a **non-author edit** (member, owner,
  and even an Admin), a **non-author non-owner delete**, **writes into an
  archived Team**, and the **deactivated User** middleware (as usual).
  Non-members get **404** on all four Comment endpoints (the established
  ticket 03/04 convention; the ticket's test line says 404 explicitly).

## Shipped (Phase 3)

**Backend** (`core/`)
- Models: `models/comment.py` (`Comment`: `issue_id` FK **ON DELETE
  CASCADE**, `author_id` FK, `body` Text, `edited_at?`) and
  `models/activity.py` gains `comment_id?` (FK-less, see Decisions);
  registered in `models/__init__.py`.
- Migration `cc365a924274`: the `comments` table (FKs, `ix_comments_issue_id`
  / `ix_comments_author_id`, the usual `updated_at` trigger) plus
  `activity.comment_id` + `ix_activity_comment_id`; downgrade verified
  (drop index/column/trigger/table).
- `domain/comments.py` (pure, DB-free): `validate_comment_body` (trim,
  1–20,000), `CommentRef`, `can_edit_comment` (author only),
  `can_delete_comment` (author / Team owner / Admin).
- `services/comments.py`: `create_comment` (any member or Admin; archived
  Team → 403; one `comment.created` row), `list_issue_comments` (oldest
  first, full list), `update_comment` (author only → 403; repeatable with
  `edited_at`; same-body no-op; one `comment.updated` per change),
  `delete_comment` (author/owner/Admin → 403; hard delete; removes the
  Comment's created/updated Activity rows and writes `comment.deleted`).
  All writes load the Issue row-locked via the shared `_visible_issue`
  helper (non-member → 404).
- `routers/comments.py`: `POST/GET /issues/{issue_id}/comments`,
  `PATCH/DELETE /issues/{issue_id}/comments/{comment_id}`; one shared
  `CommentBodyRequest`; `CommentResponse` (author display-ready).
- `routers/issues.py`: `ActivityResponse` gains `comment_id` (set on
  `comment.*` rows) so the client can pair feed rows to Comments.

**Webapp** (`webapp/`)
- `api/comments.ts` (Zod schema + `listIssueComments`/`createComment`/
  `updateComment`/`deleteComment`); `queryKeys.issues.comments`.
- `lib/feed.ts`: pure `mergeFeed` + `FeedEntry` (the merged-feed seam;
  unit-tested).
- `hooks/use-comments.ts`: plain (non-optimistic) create/update/delete
  mutations; on success invalidate the Issue's Comments + Activity caches
  (the Activity feed carries the `comment.*` rows); toast on error.
- `components/issues/MarkdownEditor.tsx`: the shared Write/Preview GFM
  editor (ADR 0007) behind the description editor, the Comment editor
  and the composer (code-review fix — removes the triplicated editor).
- `components/issues/IssueFeed.tsx` (replaces `ActivityFeed`, which was
  removed): the merged Story — Comment cards (author, timestamp, rendered
  Markdown, "edited" marker; Edit for the author, two-step Delete for
  author/owner/Admin), Activity lines (`comment.updated` → "edited their
  Comment", `comment.deleted` → "deleted a Comment"), and the composer
  (Write/Preview) at the bottom.
- `IssueDetailPanel`: the Story section replaces the Activity section;
  `me` (via `useCurrentUser`) drives the per-Comment actions.

**Tests** (`make test-core` 236 passing, `make test-webapp` 57 passing)
- `core/tests/test_comments.py` (11): create + list (oldest first,
  `comment.created` Activity with the author's display name); repeatable
  edits (`edited_at` stamped, one `comment.updated` per change, same-body
  no-op); non-author edit → 403 (member, owner, and Admin); deletion by
  author / (non-Admin) owner / Admin, non-author member → 403; deletion
  removes the Comment's old Activity rows (only `comment.deleted` remains);
  non-member → 404 on all four endpoints; a Comment of another Issue and an
  unknown Comment id → 404; archived Team → 403 on writes (reads still
  work); deactivated User → 403 (middleware); invalid bodies (422 empty /
  20,001 chars; 400 whitespace-only); feed order (`comment.*` rows
  interleaved with issue rows in seq order; deletion leaves the trail).
- `core/tests/domain/test_comments.py` (5): body trim / cap / empty;
  author-only edit (no owner/Admin exception); delete matrix
  (author/owner/Admin yes; member, other-Team owner, outsider no).
- `webapp` (57 passing): `lib/feed.test.ts` (6: no-Comments passthrough,
  in-place card replacement, multiple Comments in creation order,
  updated/deleted lines, defensive append, by-id pairing with
  out-of-order `comment_id`s) and `pages/IssueDetail.test.tsx`
  (+5: Comment card with author + sanitised Markdown, composer post, Edit
  only for own Comments (Delete offered on both for an Admin), inline edit
  save, two-step delete confirm), plus the existing suites.

## Deferred (later tickets / later work)

- Non-members get **404, not 403** on the Comment endpoints — the
  established ticket 03/04 convention (the ticket's test line says 404).
  The genuine 403s: **non-author edit**, **non-author non-owner delete**,
  **archived-Team writes**, and the **deactivated User** middleware.
- `GET /issues/{id}/comments` is the **full list, no pagination** (v1); the
  merged-feed alignment needs every Comment (see Decisions).
- The composer is **not hidden on an archived Team** (the server rejects
  with 403 + toast; the detail route does not yet pass the Team's archived
  state to the panel).
- `activity.comment_id` is deliberately **FK-less** (a `comment.deleted`
  row outlives the Comment); it is set only on `comment.*` rows.
- `Issue.comments` is intentionally **not mapped** on the ORM (the DB FK
  cascade covers ticket 07's hard delete; a mapped relationship would need
  cascade handling on parent deletion).
- Comment-card Edit/Delete visibility is computed **client-side** from
  `/auth/me` (is_admin, Team memberships, Comment author) — the ADR 0004
  pattern the webapp uses throughout; no server-side `can_edit`/
  `can_delete` flags on `CommentResponse` (recorded per code review).
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` +
  `Admin.test.tsx` (2 errors, files untouched by this ticket) still fail
  `pnpm --filter webapp run build`; everything added here type-checks clean.
