# 0015 — Focus ring: text-entry controls use the border affordance

**Status**: accepted

## Context

ADR 0014 established one global visible focus ring — `:focus-visible {
outline: 2px solid var(--color-focus-ring); outline-offset: 2px; }` — for
every interactive element, and removed the `focus:outline-none`
swallowers from inputs, selects, settings tabs and the search input.

Per the CSS `:focus-visible` spec, **text-entry controls always match
`:focus-visible` while focused**, regardless of modality (keyboard, mouse
or script `.focus()`). Two visible consequences:

- The global search overlay input is borderless by design. As soon as the
  overlay opens and focuses the input, the accent outline renders as a
  floating blue rectangle inside the dialog header — it looked like a
  broken double border.
- Every bordered text input (Login, Register, Team Settings, Issue Detail
  inline edits, Markdown editor) already styles its own focus affordance
  (`focus:border-accent`), so keyboard focus showed *both* the outline
  and the accent border — a double decoration.

## Decision

- **The global `:focus-visible` ring stays for discrete controls**
  (buttons, links, checkboxes, radios, selects, board cards, tabs): for
  one-shot controls the ring is the focus cue.
- **Text-entry controls are exempt**: `input` (untyped plus the typed
  text-entry family: `text`, `search`, `url`, `tel`, `email`, `password`,
  `number`, `date`, `datetime-local`, `month`, `week`, `time`) and
  `textarea` get `outline: none` on `:focus-visible` in `styles.css`.
  Their visible focus indicator is the existing `focus:border-accent`
  border change, so the visible-focus requirement of brief §7.4 still
  holds.
- **The search input is intentionally ringless** (Linear-style): it sits
  in an `aria-modal` dialog that is itself the focus context; the open
  overlay, the backdrop and the blinking caret locate the focus.

## Considered Options

- **Suppress only on the search input** (`focus:outline-none` on that one
  field): fixes the visible bug but leaves the double decoration on every
  form field, and resurrects the per-site swallowers ADR 0014
  deliberately removed.
- **A subtle custom cue on the search input** (1px accent underline /
  faint tint): rejected — the modal is already a strong focus indicator
  and an extra cue would be noise in the most transient view of the app
  (maintainer decision).
- **Drop the global rule entirely, per-element rings only**: the ring
  would have to be re-added at every discrete-control site (buttons,
  links, cards, …); a far larger diff for no gain.

## Consequences

- Supersedes the "one global focus ring" clause of ADR 0014; the rest of
  that ADR (class-based dark mode, token layer, `users.theme`) stands.
- Any new text-entry control must carry `focus:border-accent` — the
  global rule no longer backstops it (all current ones do, via the
  shared `lib/styles.ts` class, `Input` and the per-field class strings).
- The exemption is an explicit text-entry whitelist, not a catch-all:
  checkbox/radio and any future non-text input types keep the ring.
- No component changes: `SearchOverlay` is covered by the
  `input:not([type])` exemption; no new dependencies.
