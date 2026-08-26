"""Search use-case: Issues across the user's Teams (ticket 09, brief §7.2.8)."""

from sqlalchemy import String, case, cast, or_
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.search import SEARCH_RESULT_LIMIT, clean_search_query
from core.models.issue import Issue
from core.models.team import Team
from core.models.user import User
from core.services.issues import user_teams


async def search_issues(
    session: AsyncSession, *, user: User, raw_query: str | None
) -> list[tuple[Issue, Team]]:
    """Search Issue identifiers and titles across the user's Teams.

    The Membership scope is author-relative by definition (ticket 09): the
    caller's own Teams only — a workspace Admin is not searched into Teams
    they do not belong to (ADR 0013 precedent). Matching is case-insensitive:
    a title substring or an identifier substring of the computed
    ``KEY-number`` form (ADR 0010). Archived Issues and Issues of archived
    Teams are excluded. Results are a single capped page (no cursor):
    identifier matches first, then Team key, then Issue number.

    Args:
        session: The database session (read-only; no transaction to own).
        user: The authenticated user performing the search.
        raw_query: The raw query from the request.

    Returns:
        The matching Issues paired with their Teams (State, assignee and
        Labels eager-loaded), up to ``SEARCH_RESULT_LIMIT``.

    Raises:
        ValidationError: If the query is missing or blank.

    """
    query = clean_search_query(raw_query)
    pattern = f"%{query}%"

    team_rows = await user_teams(session, user)
    if not team_rows:
        return []

    # The identifier is computed, never stored (ADR 0010): match the
    # concatenated form so full, partial and bare-number queries all work.
    identifier = Team.key + "-" + cast(Issue.number, String)
    statement = (
        select(Issue)
        .join(Team, Team.id == Issue.team_id)  # type: ignore[arg-type]  # onclause is a Column comparison at runtime
        .where(
            Issue.team_id.in_([team.id for team in team_rows]),  # type: ignore[attr-defined]
            Issue.archived_at.is_(None),  # type: ignore[union-attr]  # SQLModel field is a Column at runtime
            or_(Issue.title.ilike(pattern), identifier.ilike(pattern)),  # type: ignore[attr-defined]
        )
        .options(
            joinedload(Issue.state),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            joinedload(Issue.assignee),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            selectinload(Issue.labels),  # type: ignore[arg-type,attr-defined]  # M2M: selectinload avoids row duplication
        )
        .order_by(
            case((identifier.ilike(pattern), 0), else_=1),
            Team.key,
            Issue.number,  # type: ignore[arg-type]
        )
        .limit(SEARCH_RESULT_LIMIT)
    )
    issues = list((await session.exec(statement)).all())
    teams_by_id = {team.id: team for team in team_rows}
    return [(issue, teams_by_id[issue.team_id]) for issue in issues]
