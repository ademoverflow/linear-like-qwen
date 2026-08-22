# 0012 — Invitations are workspace-level; membership is granted by Team owners

**Status**: accepted

## Context

Brief §2 defines an Invitation with no `team_id`; §5.3 places invitations under
Admin user management; §5.2 gives Team owners "manage members". The Phase 1 grill
confirmed this reading.

## Decision

- An Invitation is a workspace-level registration token: `email`, `token`
  (random, hashed at rest), `invited_by`, `expires_at` (now + 7 days),
  `accepted_at?`. One active invitation per email; re-inviting replaces the token
  (the old one stops working).
- Bootstrap register (empty `users` table) or invited register both join the
  workspace; neither joins a Team.
- Team membership is separate: Team owners add existing Users to their Team and
  set the `owner`/`member` role.

## Consequences

- Admin screens: invite by email, list pending/expired/accepted invitations.
- Team settings (owner): member management from the workspace user list.
- If per-team invitations are ever wanted, add a `team_id` to the model — the
  current shape does not preclude it.
