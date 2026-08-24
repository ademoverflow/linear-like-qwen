"""Labels router (thin): Team-scoped label management (ticket 05, brief §9)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.label import Label
from core.models.user import User
from core.services import labels as labels_service

router = APIRouter(prefix="/teams/{team_id}/labels", tags=["Labels"])


class LabelCreateRequest(BaseModel):
    """Body for ``POST /teams/{team_id}/labels``."""

    name: str = Field(min_length=1, max_length=50)
    color: str = Field(min_length=7, max_length=7)


class LabelUpdateRequest(BaseModel):
    """Body for ``PATCH /teams/{team_id}/labels/{label_id}``."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, min_length=7, max_length=7)


class LabelResponse(BaseModel):
    """A Label as exposed by the API."""

    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    color: str
    created_at: datetime
    updated_at: datetime


def label_response(label: Label) -> LabelResponse:
    """Build a LabelResponse from a Label."""
    return LabelResponse(
        id=label.id,
        team_id=label.team_id,
        name=label.name,
        color=label.color,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


@router.get("")
async def list_team_labels(
    team_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[LabelResponse]:
    """List a Team's Labels (Team member or Admin; non-members get 404)."""
    labels = await labels_service.list_team_labels(session, user=user, team_id=team_id)
    return [label_response(label) for label in labels]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team_label(
    team_id: uuid.UUID,
    payload: LabelCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LabelResponse:
    """Create a Label in a Team (Team owner or Admin; 403 otherwise)."""
    label = await labels_service.create_team_label(
        session, user=user, team_id=team_id, name=payload.name, color=payload.color
    )
    return label_response(label)


@router.patch("/{label_id}")
async def update_team_label(
    team_id: uuid.UUID,
    label_id: uuid.UUID,
    payload: LabelUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LabelResponse:
    """Rename and/or recolor a Label (Team owner or Admin; 403 otherwise)."""
    changes = {
        name: getattr(payload, name)
        for name in payload.model_fields_set
        if name in labels_service.LABEL_UPDATE_FIELDS
    }
    label = await labels_service.update_team_label(
        session,
        user=user,
        team_id=team_id,
        label_id=label_id,
        changes=changes,
    )
    return label_response(label)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_label(
    team_id: uuid.UUID,
    label_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a Label and its links to Issues (Team owner or Admin)."""
    await labels_service.delete_team_label(session, user=user, team_id=team_id, label_id=label_id)
