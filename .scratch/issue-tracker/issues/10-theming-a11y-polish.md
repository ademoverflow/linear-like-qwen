# 10: Theming & a11y polish

**What to build:** The final experience layer: the CSS-variable token system with light/dark
(system default + per-user override), the fixed visual rules, full accessibility, skeletons
and empty states, and 768px responsiveness.

**Blocked by:** 09 (Search, keyboard shortcuts & My Issues)

**Status:** done

- [x] Light/dark via one CSS-variable token layer; respects `prefers-color-scheme`; a manual override is persisted per User (via the auth profile endpoint) and applied.
- [x] One accent colour; state categories use the fixed semantic colours (backlog grey, unstarted neutral, started amber, completed green, canceled muted red) and a State's own colour is used for the dot only; priority glyphs are consistent across list, board and detail.
- [x] Full keyboard reachability, visible focus rings, ARIA roles on board columns/cards, and colour is never the only carrier of meaning.
- [x] Empty states everywhere ("No issues yet — press C"); skeletons instead of spinners; responsive to 768px (sidebar → drawer, Issue detail panel → full page).
- [x] Tests: render tests for theme switching (system / light / dark) and the 768px layout; ARIA role assertions on board columns and cards.

## Decisions (recorded during Phase 3)

- **Theming strategy (ADR 0014)**: class-based dark mode via
  `@custom-variant dark (&:where(.dark, .dark *))` plus a semantic token
  layer in the Tailwind 4 `@theme` block of `webapp/src/styles.css`. The
  `.dark` class on `<html>` is set by (a) a pre-paint inline script in
  `webapp/index.html` (reads a localStorage mirror, falls back to
  `prefers-color-scheme` — avoids a flash of the wrong theme; the recorded
  trade-off vs `useLayoutEffect`, which would paint once with the wrong
  theme) and (b) the `useThemePreference` hook owned by `AppShell`
  (applies at runtime, follows OS setting changes via a matchMedia
  "change" listener while on "system").
- **Persistence**: a new nullable `users.theme` column (NULL = "system").
  "System" is the *absence* of a preference, so existing Users default to
  system without a backfill and the stored form is system → NULL
  (`core/src/core/domain/profile.py`). `PATCH /auth/me` accepts
  `display_name`, `avatar_url`, `theme` (brief §9) — `theme` outside
  `{system, light, dark}` → 400 `ValidationError` (ADR 0003); `null`
  theme resets to system. Every mutation returns the updated `me`
  (brief §9); `GET /auth/me` gains the normalised `theme`.
- **Authoritative value (ADR 0004)**: `GET /auth/me` — no separate
  theming endpoint. The localStorage mirror (`theme-preference`) exists
  only so the pre-paint script can pick the theme before the profile
  loads; `AppShell` syncs the hook from `me.theme` once the profile loads,
  and the switcher writes the updated `me` back into the auth cache on
  success (no refetch).
- **Theme switcher placement**: a row in the sidebar footer (System /
  Light / Dark as `Monitor` / `Sun` / `Moon`, `aria-pressed`,
  `role="group"` "Theme") — the sidebar is the always-visible profile
  surface and no settings page is needed. Collapsed sidebar: one button
  that cycles System → Light → Dark.
- **Token migration scope**: the base neutral colours were migrated to
  tokens across 31 files (`bg-white` → `bg-surface`, `bg-neutral-50` →
  `bg-canvas`, `border-neutral-200` → `border-line`,
  `text-neutral-900/700` → `text-foreground`, `text-neutral-500/600` →
  `text-muted`, `text-neutral-400` → `text-faint`,
  `hover:bg-neutral-100` → `hover:bg-surface-subtle` + opacity variants).
  Deliberately left as-is: control borders
  (`border-neutral-300 dark:border-neutral-700`), `text-red-*` error
  colours, the inverted Toast surface, the Avatar placeholder, kbd
  borders, and the Dialog container's intentional `outline-none` (a
  programmatically-focused panel that must not take the ring).
- **Category colours**: fixed, theme-invariant semantic tokens in
  `@theme`: backlog `#a2a2a2`, unstarted `#737373`, started `#f2c94c`,
  completed `#4cb371`, canceled `#d98c8c`. A State's own `color` is now
  drawn **dot-only**: `StateDot` is the single place a State colour is
  rendered (with the category token as fallback). Audit: all 7 dot sites
  (IssueCard, Board ×3, IssueDetailPanel, TeamIssues, SearchOverlay) were
  already dots; they now all use `StateDot`.
- **Priority glyphs**: one shared `PriorityGlyph` (lucide) across list
  (`IssueCard`), board (card + drag handle) and the detail panel (where a
  labelled `Select` shows the text); it carries `role="img"` +
  `aria-label` + `title`, so colour is never the only carrier of meaning.
- **Focus rings**: one global `:focus-visible` rule from the token layer
  (accent, visible in light and dark); the `focus:outline-none`
  swallowers were removed from inputs, selects, the shared `SELECT_CLASS`,
  the settings tabs and the search input.
- **Board ARIA**: columns are `role="group"` named `"{State} ({count})"`
  (replacing the previous implicit `region` — one less landmark per
  column); the card list is a named `<ul>` (`"{State} Issues"`); cards
  are `listitem` **named by author** (`"ENG-1: Set up the core loop"`)
  because ARIA computes a listitem's name from author only, never
  content. The roles do not disturb dnd-kit (refs/draggables unchanged).
- **768px seam**: `useMediaQuery("(min-width: 768px)")` (new hook; jsdom
  has no `window.matchMedia` — the hook reports no-match when it is
  missing, tests stub it via `src/test/media.ts`, setup default =
  desktop). Below 768px: the static sidebar is hidden, a narrow header
  with an "Open sidebar" button appears, and the sidebar renders inside
  `SidebarDrawer` (`role="dialog"`, `aria-modal`, Esc via a **document**
  capture listener, backdrop click closes, focus moves in and returns to
  the trigger on close); drawer navigation closes it (`onNavigate`). The
  Issue detail list column is desktop-only (`{isDesktop && …}`) — below
  768px the panel is the full page and back navigation is the existing
  "‹ ENG / Issues" link in the panel header (no new control).
- **No Activity rows for profile updates**: Activity is append-only per
  Issue (`issue_id` NOT NULL) — a profile change is not an Issue Activity.
  **No new authz `Action`**: `PATCH /auth/me` is self-profile only (the
  auth dependency is the check; verified against `domain/authz.py`).
- **Empty-state / skeleton audits**: the Team Issues list and the Board
  already had "No Issues yet" + "Press C to create the first one" (the `C`
  shortcut, ticket 09) — copy kept; My Issues keeps "No Issues assigned
  to you"; the IssueFeed is effectively never empty (an Issue always has
  its creation Activity) — its empty branch is kept as a safety net.
  Skeleton audit: `Skeleton` (pulse) is used for every loading state; no
  spinners found.
- **Pre-existing test made deterministic**: the IssueDetail
  "shows identifier/title" test asserted on content that could match
  twice; it now waits for exactly 2 matches (it passed by luck before).
  The Board ARIA tests moved from `region` to `group` + count, and the
  listitem assertion gained the author-name check.

## Shipped (Phase 3)

- `core/src/core/domain/profile.py` (new, pure, ADR 0004):
  `THEME_CHOICES`, `validate_theme` (None → system; invalid → 400),
  `theme_to_storage` / `theme_from_storage` (system ↔ NULL),
  `normalize_display_name` / `normalize_avatar_url` (strip; blank/None
  clears; max 100/500 → 400).
- `core/src/core/models/user.py`: `theme: str | None` (max 16).
- Migration `7af5d82c30af`: adds/drops only `users.theme` (autogen's
  spurious hand-created-index drops trimmed; upgrade → downgrade →
  upgrade verified; head is now `7af5d82c30af`).
- `core/src/core/services/auth.py`: `update_me` (re-loads the User inside
  one transaction, unknown field → 400, flush + refresh) and
  `PROFILE_FIELDS`.
- `core/src/core/routers/auth.py`: `PATCH /api/v1/auth/me` (partial
  update of `display_name`, `avatar_url`, `theme` → the updated `me`);
  `MeResponse.theme` normalised.
- `core/tests/domain/test_profile.py` (12): the pure profile rules
  (choices, None/invalid theme, storage mapping both ways, trim/clear/
  length limits).
- `core/tests/test_auth.py` (+7, now 21): `GET /auth/me` defaults theme
  to system; PATCH unauthenticated → 401; theme persisted and returned;
  invalid theme → 400 envelope; display_name/avatar trim and clear;
  partial update keeps the other fields; null theme resets to system.
- `webapp/src/styles.css`: `@custom-variant dark`, the `@theme` token
  layer (neutral scale, accent, focus ring, fixed category colours), the
  `.dark` overrides, the global `:focus-visible` ring.
- `webapp/index.html`: the pre-paint theme script (ADR 0014).
- `webapp/src/hooks/use-theme.ts` (new): `useThemePreference` (state from
  the stored mirror, class + mirror on change, matchMedia "change"
  listener while "system") plus `resolveThemePreference`,
  `applyThemePreference`, `readStoredThemePreference`,
  `storeThemePreference`, `THEME_STORAGE_KEY`.
- `webapp/src/hooks/use-media-query.ts` (new): the 768px seam (guards
  missing matchMedia → no match).
- `webapp/src/components/layout/ThemeSwitcher.tsx` (new): System / Light
  / Dark, `aria-pressed`, the collapsed cycling button, mutation
  `updateMe({ theme })` → cache write + `onChange` + error toast.
- `webapp/src/components/layout/SidebarDrawer.tsx` (new): the off-canvas
  sidebar (dialog semantics, Esc on the document capture phase, backdrop
  close, focus restore).
- `webapp/src/components/layout/Sidebar.tsx`: the footer theme row,
  `forceExpanded` / `onNavigate` props, collapse toggle hidden in the
  drawer.
- `webapp/src/components/layout/AppShell.tsx`: owns the theme (syncs from
  `me.theme`), the narrow header + drawer below 768px, a single `<main>`
  (no remount on resize).
- `webapp/src/components/issues/StateDot.tsx` (new): the single place a
  State's colour is drawn; all 7 dot sites migrated.
- `webapp/src/pages/IssueDetail.tsx`: the list column is desktop-only.
- `webapp/src/components/issues/Board.tsx`: `group` / `list` /
  `listitem` roles with the name + count.
- `webapp/src/lib/styles.ts` + `Input` / `Select` / `LabelManager` /
  settings tabs / `SearchOverlay` input: `focus:outline-none` swallowers
  removed (the global ring applies).
- `webapp/src/api/auth.ts`: `Theme`, `themeSchema`, `meSchema.theme`,
  `updateMe`.
- `webapp/src/test/fixtures.ts` (`meFixture.theme = "system"` — every
  test `Me` spreads it), `webapp/src/test/setup.ts` (default matchMedia
  stub: desktop), `webapp/src/test/media.ts` (controllable
  `desktop` / `systemDark` stub, `systemDark.set` fires "change").
- `webapp/src/hooks/use-theme.test.ts` (9): system follows the OS (light
  + dark), explicit preferences ignore the OS, class toggling, the
  storage mirror round-trip + unknown value, mount-time apply,
  follow-on-change while "system", stop-following once explicit.
- `webapp/src/components/layout/ThemeSwitcher.test.tsx` (3): the three
  states + `aria-pressed`, persist via PATCH + apply from the response +
  cache write, error toast.
- `webapp/src/components/layout/AppShell.test.tsx` (+6, now 13): system
  follows the OS setting, an explicit me theme wins, a manual dark
  preference applies, below 768px the drawer (open, contents, Esc
  closes), desktop keeps the static sidebar.
- `webapp/src/pages/IssueDetail.test.tsx` (+1, now 15): below 768px the
  panel is the full page (list column gone); the identifier/title test
  made deterministic.
- `webapp/src/pages/TeamBoard.test.tsx` (updated ARIA tests): columns are
  named groups with counts (scoped to `main` — the sidebar has its own
  Theme group), the card is a listitem named by author.
- `docs/adr/0014-class-based-theming-token-layer.md`.
- `CONTEXT.md`: new glossary term **Theme**.
- Verified: `make check` green (ruff `ALL` + mypy 113 files + biome 86
  files), `make test-core` 400 passed, `make test-webapp` 119 passed,
  `pnpm --filter webapp run build` — no new tsc errors (the 2
  pre-existing Admin errors stay).

## Deferred (later tickets / later work)

- `POST /auth/change-password` (brief §9) — in the brief, not in this
  ticket's checklist; a later ticket.
- Control borders, red error colours, the Toast surface, the Avatar
  placeholder and kbd borders stay on neutral utilities (recorded in
  Decisions).
- The pre-paint script and the theme hook share the storage key and the
  three values by convention (ADR 0014 Consequences).
- No per-Team or per-Issue theme, no high-contrast mode.
- Pre-existing tsc errors in `webapp/src/pages/Admin.tsx` +
  `Admin.test.tsx` (2 errors, files untouched by this ticket) still
  fail `pnpm --filter webapp run build`; everything added here
  type-checks clean.
