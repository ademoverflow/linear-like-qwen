# 04: Transitions & Board

**What to build:** Moving an Issue between Workflow States through the single domain code
path (with completed/canceled timestamp rules), and the Kanban Board — one column per
Workflow State, drag a card = transition — with optimistic updates.

**Blocked by:** 03 (Issue detail, edit & Activity)

**Status:** ready-for-agent

- [ ] Any state → any state is permitted; entering a `completed` State sets `completed_at` and clears `canceled_at`; entering `canceled` sets `canceled_at` and clears `completed_at`; leaving either into anything else clears both; every transition emits Activity `issue.state_changed`.
- [ ] Changing the state of an Issue goes through exactly one code path in the domain layer; no generic field update can bypass the transition rules.
- [ ] The Board page renders one column per Workflow State (in position order) for the Team; dragging a card between columns performs the transition via the API; the drop is optimistic with rollback + toast on failure.
- [ ] Board columns and cards carry ARIA roles and are keyboard-operable (dnd-kit keyboard sensor); the state property in the detail panel uses the same transition path.
- [ ] Tests: pure-domain unit tests for the transition rules (full timestamp stamping/clearing matrix, any→any); HTTP: transition happy-path + 403; `completed_at`/`canceled_at` verified through the API response.
