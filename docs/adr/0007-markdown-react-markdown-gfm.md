# 0007 — Markdown: `react-markdown` + `remark-gfm` + `rehype-sanitize`, full GFM

**Status**: accepted

## Context

Issue descriptions and Comments are Markdown (brief §2, §3.1). The renderer and
sanitiser had to be proposed in Phase 1 (brief §7). Maintainer asked for full
Markdown support.

## Decision

- Render client-side with `react-markdown` (no `dangerouslySetInnerHTML`).
- Full GFM via `remark-gfm`: tables, task lists, strikethrough, autolinks.
- Sanitise with `rehype-sanitize` against an explicit allowlist (HTML tags stripped
  by default; no raw HTML, no `javascript:` URLs).

## Considered Options

- `marked` + DOMPurify: imperative pipeline requiring `dangerouslySetInnerHTML`.
- A minimal custom renderer: would need to grow into GFM anyway.

## Consequences

- Three new `webapp` dependencies (maintainer sign-off given in Phase 1).
- The sanitize allowlist lives in `webapp/src/lib/` and gets a unit test; preview
  mode reuses the same pipeline as edit mode's preview pane.
