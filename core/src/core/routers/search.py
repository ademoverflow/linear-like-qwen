"""Search router (thin): global Issue search across the user's Teams."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.user import User
from core.routers.issues import IssueResponse, issue_response
from core.services import search as search_service

router = APIRouter(prefix="/search", tags=["Search"])


class SearchIssueResponse(IssueResponse):
    """A search hit with the Team's key and name (ticket 09)."""

    team_key: str
    team_name: str


class SearchResponse(BaseModel):
    """The search results: one capped page, no cursor."""

    issues: list[SearchIssueResponse]


@router.get("")
async def search(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str | None, Query()] = None,
) -> SearchResponse:
    """Search Issue identifiers and titles across the user's Teams.

    Membership scope only (an Admin does not search Teams they are not a
    member of); archived Issues and archived Teams are excluded; a fixed
    cap of 50 hits, no cursor (ticket 09).
    """
    results = await search_service.search_issues(session, user=user, raw_query=q)
    return SearchResponse(
        issues=[
            SearchIssueResponse(
                **issue_response(issue, team.key).model_dump(),
                team_key=team.key,
                team_name=team.name,
            )
            for issue, team in results
        ]
    )
