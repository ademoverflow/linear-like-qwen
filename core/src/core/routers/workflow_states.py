"""Workflow States router (thin): Team workflow editing (ticket 08, brief §4.3)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.user import User
from core.models.workflow_state import WorkflowState
from core.services import teams as teams_service
from core.services import workflow_states as states_service

router = APIRouter(prefix="/teams/{team_id}/states", tags=["Workflow States"])


class TeamStateResponse(BaseModel):
    """A Workflow State as exposed by the API (board columns; ADR 0008)."""

    id: uuid.UUID
    name: str
    category: str
    color: str
    position: int
    version: int


class StateCreateRequest(BaseModel):
    """Body for ``POST /teams/{team_id}/states``.

    Category is validated in the domain (one of the five, else 400);
    name and colour are domain-validated too (400).
    """

    name: str = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=16)
    color: str = Field(min_length=7, max_length=7)


class StateUpdateRequest(BaseModel):
    """Body for ``PATCH /teams/{team_id}/states/{state_id}`` (ADR 0008)."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, min_length=7, max_length=7)
    category: str | None = Field(default=None, min_length=1, max_length=16)
    version: int = Field(ge=1)


class StateRefRequest(BaseModel):
    """A State id with the version the client last saw (reorder, ADR 0008)."""

    id: uuid.UUID
    version: int = Field(ge=1)


class StateReorderRequest(BaseModel):
    """Body for ``PATCH /teams/{team_id}/states/reorder`` (full ordered list)."""

    states: list[StateRefRequest] = Field(min_length=1)


class StateDeleteRequest(BaseModel):
    """Body for ``DELETE /teams/{team_id}/states/{state_id}``."""

    version: int = Field(ge=1)
    migrate_to_state_id: uuid.UUID | None = None


def state_response(state: WorkflowState) -> TeamStateResponse:
    """Build a TeamStateResponse from a WorkflowState."""
    return TeamStateResponse(
        id=state.id,
        name=state.name,
        category=state.category,
        color=state.color,
        position=state.position,
        version=state.version,
    )


@router.get("")
async def list_team_states(
    team_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamStateResponse]:
    """List a Team's Workflow States in position order (Team member or Admin)."""
    states = await teams_service.list_team_states(session, user=user, team_id=team_id)
    return [state_response(state) for state in states]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team_state(
    team_id: uuid.UUID,
    payload: StateCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamStateResponse:
    """Add a Workflow State at the end of the Team's Workflow (owner or Admin)."""
    state = await states_service.create_team_state(
        session,
        user=user,
        team_id=team_id,
        name=payload.name,
        category=payload.category,
        color=payload.color,
    )
    return state_response(state)


@router.patch("/reorder")
async def reorder_team_states(
    team_id: uuid.UUID,
    payload: StateReorderRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamStateResponse]:
    """Reorder the Team's Workflow States (full ordered list, owner or Admin)."""
    states = await states_service.reorder_team_states(
        session,
        user=user,
        team_id=team_id,
        states=[states_service.StateRef(id=ref.id, version=ref.version) for ref in payload.states],
    )
    return [state_response(state) for state in states]


@router.patch("/{state_id}")
async def update_team_state(
    team_id: uuid.UUID,
    state_id: uuid.UUID,
    payload: StateUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamStateResponse:
    """Rename / recolor / re-categorise a State with a version echo (ADR 0008)."""
    state = await states_service.update_team_state(
        session,
        user=user,
        team_id=team_id,
        state_id=state_id,
        version=payload.version,
        name=payload.name if "name" in payload.model_fields_set else None,
        color=payload.color if "color" in payload.model_fields_set else None,
        category=payload.category if "category" in payload.model_fields_set else None,
    )
    return state_response(state)


@router.delete("/{state_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_state(
    team_id: uuid.UUID,
    state_id: uuid.UUID,
    payload: StateDeleteRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a State, migrating its Issues if any (owner or Admin)."""
    await states_service.delete_team_state(
        session,
        user=user,
        team_id=team_id,
        state_id=state_id,
        version=payload.version,
        migrate_to_state_id=payload.migrate_to_state_id,
    )
