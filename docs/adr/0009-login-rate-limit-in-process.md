# 0009 — Login rate limit: in-process, not distributed

**Status**: accepted

## Context

Brief §5.1: rate-limit `POST /auth/login` with a simple in-process limiter,
10 attempts / 15 min per email and per IP, and note in an ADR that it is not
distributed.

## Decision

- In-process (per-container) limiter in the auth service: two independent budgets —
  10 attempts per 15 min per email, and 10 attempts per 15 min per client IP.
  Exceeding either rejects the login (429, via the error envelope).
- No external store (no Redis): counters live in process memory and reset on
  restart.

## Consequences

- Accepted limitation: with multiple core containers the budget is per container,
  not global. v1 runs a single core container, so this holds; if the API is ever
  scaled horizontally, the limiter must move to a shared store (revisit then).
