# 06: Comments

**What to build:** A Comments thread on the Issue detail — create, edit by author, delete by
author/Team owner/Admin — merged chronologically with Activity into the issue's story.

**Blocked by:** 03 (Issue detail, edit & Activity)

**Status:** ready-for-agent

- [ ] Any User with access to the Issue can write a Markdown Comment (full GFM, sanitised).
- [ ] A Comment author can edit their own Comment; a Comment can be deleted by its author, a Team owner, or an Admin.
- [ ] Comments and Activity appear merged chronologically in the Issue detail feed; comment create/update/delete each emit Activity rows.
- [ ] Tests: happy-path + one 403 per new endpoint; only the author can edit (403 otherwise); deletion by author / owner / Admin; non-member cannot comment (404 on the Issue).
