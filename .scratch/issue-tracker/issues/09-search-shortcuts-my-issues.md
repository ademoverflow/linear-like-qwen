# 09: Search, keyboard shortcuts & My Issues

**What to build:** Global search across the user's Teams (identifier or title substring,
`/` or Cmd/Ctrl+K, arrow keys + Enter), the full keyboard-shortcut set with the `?`
cheat-sheet, and the My Issues view aggregating the user's assigned Issues.

**Blocked by:** 05 (Labels, list filters & bulk operations)

**Status:** ready-for-agent

- [ ] Global search (`/` or Cmd/Ctrl+K) matches Issue identifier or title substring across all Teams the current User belongs to; results are navigable with arrow keys and Enter opens the Issue.
- [ ] My Issues aggregates Issues assigned to the current User across all their Teams.
- [ ] The shortcut set works: `C` new Issue, `J`/`K` or arrows move selection, `Enter` open, `Esc` close, `S` state, `A` assignee, `P` priority, `L` labels, `?` cheat-sheet; none of them fire while focus is in an input, textarea or contenteditable.
- [ ] Tests: search scope (only the user's Teams; identifier and title matches); render tests for the search overlay and shortcut activation/suppression.
