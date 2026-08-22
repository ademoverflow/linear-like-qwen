# 0003 — `/api/v1` prefix and a single error envelope driven by `DomainError`

**Status**: accepted

## Decision

- All resource routers mount on `api_router = APIRouter(prefix="/api/v1")` in `core.main`.
  `/health` stays unversioned.
- `core.domain.errors.DomainError` and its subclasses (`ValidationError` 400,
  `ForbiddenError` 403, `NotFoundError` 404, `ConflictError` 409, `RuleViolationError` 422)
  carry their status code. One exception handler in `core.main` renders
  `{"error": {"code", "message", "details"?}}`.
- Services raise `DomainError`s; routers never construct error responses by hand and never
  leak SQLAlchemy messages. FastAPI's own 401/422 (auth, request validation) keep their default
  shape; the frontend client treats any non-`{"error": …}` body as `http_error`.
- `webapp/src/api/client.ts` is the only place `fetch` is called. It prefixes `/api/v1`,
  sends `credentials: "include"` (cookie is cross-origin in dev) and throws `ApiError`.

## Consequences

- Adding a resource = router + `api_router.include_router(...)` + one `api/<resource>.ts`.
- Frontend `VITE_API_URL` is required (`webapp/.env.example`).
