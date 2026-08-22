# 10: Theming & a11y polish

**What to build:** The final experience layer: the CSS-variable token system with light/dark
(system default + per-user override), the fixed visual rules, full accessibility, skeletons
and empty states, and 768px responsiveness.

**Blocked by:** 09 (Search, keyboard shortcuts & My Issues)

**Status:** ready-for-agent

- [ ] Light/dark via one CSS-variable token layer; respects `prefers-color-scheme`; a manual override is persisted per User (via the auth profile endpoint) and applied.
- [ ] One accent colour; state categories use the fixed semantic colours (backlog grey, unstarted neutral, started amber, completed green, canceled muted red) and a State's own colour is used for the dot only; priority glyphs are consistent across list, board and detail.
- [ ] Full keyboard reachability, visible focus rings, ARIA roles on board columns/cards, and colour is never the only carrier of meaning.
- [ ] Empty states everywhere ("No issues yet — press C"); skeletons instead of spinners; responsive to 768px (sidebar → drawer, Issue detail panel → full page).
- [ ] Tests: render tests for theme switching (system / light / dark) and the 768px layout; ARIA role assertions on board columns and cards.
