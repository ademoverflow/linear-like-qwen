# 0014 — Theming: class-based dark mode + CSS variable token layer

**Status**: accepted (the "one global focus ring" clause is superseded by 0015)

## Context

Brief §7.4 requires light / dark / **system** themes with a per-User
override, fixed category colours, and a visible focus ring. The webapp
previously used Tailwind's default `dark:` variant, which is
media-query-only (`prefers-color-scheme`): a per-User override could not
win over the system preference, and there was no token layer — colours
were hard-coded utilities across ~30 files (the `.dark .markdown …`
selectors in `styles.css` were dead code, hinting at the intended
class-based strategy).

## Decision

- **Class-based dark mode.** `styles.css` declares
  `@custom-variant dark (&:where(.dark, .dark *));` — the `dark` variant
  follows the `.dark` class on `<html>` instead of the OS media query.
  The class is set by two owners:
  - a pre-paint inline script in `webapp/index.html` (reads the
    localStorage mirror, falls back to `prefers-color-scheme`), so the
    first paint is already in the right theme (no FOUC);
  - the `useThemePreference` hook (`webapp/src/hooks/use-theme.ts`),
    owned by `AppShell`, which applies the preference at runtime and
    follows OS setting changes (matchMedia "change" listener) while on
    "system".
- **A semantic token layer** in the Tailwind 4 `@theme` block of
  `styles.css`: neutral scale (`canvas`, `surface`, `surface-subtle`,
  `line`, `foreground`, `muted`, `faint`), the single accent
  (`--color-accent`) plus `--color-focus-ring`, and the fixed,
  theme-invariant category colours (`--color-cat-backlog` …
  `--color-cat-canceled`). The `.dark {}` block overrides only the
  theme-dependent tokens; everything else is one switch.
- **`users.theme` is nullable; NULL means "system".** The stored form is
  `system` → NULL, `light`/`dark` → the value (`core/src/core/domain/profile.py`).
  "System" is the absence of a preference, so existing Users start as
  system without a backfill, and the column's default state is the
  default behaviour.
- **The authoritative value is `GET /auth/me`** (ADR 0004): no separate
  theming endpoint. The localStorage mirror exists only to let the
  pre-paint script pick the theme before the profile loads; `AppShell`
  syncs the hook from `me.theme` once the profile is in.
- **One global focus ring.** `:focus-visible { outline: 2px solid
  var(--color-focus-ring); outline-offset: 2px; }` for every interactive
  element; the `focus:outline-none` swallowers were removed from inputs,
  selects and the shared select class.
- **A State's own colour is dot-only** (`StateDot`, the single place a
  State colour is drawn); the fixed category colours carry the
  semantic, colour-never-only meaning (names are always rendered).

## Considered Options

- Media-query-only `dark:` (the status quo): cannot honour a per-User
  override — the core requirement.
- A theme library (CSS-in-JS tokens, theme provider package): a new
  dependency for what `@theme` + a class already give (no new deps
  allowed without sign-off).
- `useLayoutEffect` to apply the class: the first React commit paints
  with the wrong theme (FOUC) on every cold load; the pre-paint script
  is ~10 lines of vanilla JS and is the standard fix.
- `users.theme` NOT NULL default `'system'`: would make "user explicitly
  chose system" indistinguishable from "never configured", and needs a
  backfill default for existing rows.

## Consequences

- The base neutral colours were migrated to tokens across 31 files
  (`bg-white` → `bg-surface`, `border-neutral-200` → `border-line`, …);
  control borders (`border-neutral-300 dark:border-neutral-700`), red
  error colours, the inverted Toast surface, the Avatar placeholder and
  kbd borders were left as-is (recorded in the ticket file).
- jsdom has no `window.matchMedia`: tests stub it via
  `webapp/src/test/media.ts` (controllable `systemDark`), with a
  desktop-default stub in `webapp/src/test/setup.ts`.
- The pre-paint script and the hook must stay in sync on the storage key
  and the three values (`system` / `light` / `dark`).
