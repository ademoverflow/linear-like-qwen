"""Label use-cases (ticket 05): Team-scoped label management (brief §5.2, §9)."""

import uuid
from typing import Any, cast

from sqlalchemy import delete, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, Actor, TeamResource, can
from core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from core.domain.labels import validate_label_color, validate_label_name
from core.models.issue_label import IssueLabel
from core.models.label import Label
from core.models.team import Team
from core.models.user import User
from core.services.actors import load_actor

MSG_TEAM_NOT_FOUND = "Team not found"
MSG_LABEL_NOT_FOUND = "Label not found"
MSG_LABEL_NAME_EXISTS = "A Label with this name already exists"
MSG_LABEL_UPDATE_EMPTY = "Provide a name and/or a colour to update"
MSG_LABELS_OWNER_ONLY = "Only a Team owner can manage Labels"

# Canonical update fields for a Label (iterated in the service).
LABEL_UPDATE_FIELDS: tuple[str, ...] = ("name", "color")


async def _visible_team(session: AsyncSession, *, actor: Actor, team_id: uuid.UUID) -> Team:
    """Load a Team the actor may see (non-members get 404, not 403)."""
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    return team


async def list_team_labels(session: AsyncSession, *, user: User, team_id: uuid.UUID) -> list[Label]:
    """List a Team's Labels (Team member or Admin; non-members get 404).

    Args:
        session: The database session.
        user: The authenticated acting user.
        team_id: The Team to list Labels for.

    Returns:
        The Team's Labels, case-insensitively by name.

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor.

    """
    actor = await load_actor(session, user)
    team = await _visible_team(session, actor=actor, team_id=team_id)
    labels = (
        await session.exec(
            select(Label)
            .where(Label.team_id == team.id)
            .order_by(func.lower(Label.name), Label.name)  # type: ignore[attr-defined]
        )
    ).all()
    return list(labels)


async def create_team_label(
    session: AsyncSession,
    *,
    user: User,
    team_id: uuid.UUID,
    name: str,
    color: str,
) -> Label:
    """Create a Label in a Team (Team owner or Admin).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team the Label belongs to.
        name: Label name (1-50 chars, trimmed).
        color: Label colour (6-digit hex).

    Returns:
        The created Label.

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor (non-members get 404, not 403).
        ForbiddenError: If the actor is not a Team owner (or Admin).
        ValidationError: If the name or colour is invalid.
        ConflictError: If the name is already taken in the Team.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _visible_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.LABEL_CREATE, TeamResource(team.id)):
            raise ForbiddenError(MSG_LABELS_OWNER_ONLY)
        clean_name = validate_label_name(name)
        clean_color = validate_label_color(color)
        existing = (
            await session.exec(
                select(Label).where(Label.team_id == team.id, Label.name == clean_name)
            )
        ).first()
        if existing is not None:
            raise ConflictError(MSG_LABEL_NAME_EXISTS)
        label = Label(team_id=team.id, name=clean_name, color=clean_color)
        session.add(label)
        await session.flush()
        await session.refresh(label, ["created_at", "updated_at"])
        return label


async def update_team_label(
    session: AsyncSession,
    *,
    user: User,
    team_id: uuid.UUID,
    label_id: uuid.UUID,
    changes: dict[str, Any],
) -> Label:
    """Rename and/or recolor a Label (Team owner or Admin).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team the Label belongs to.
        label_id: The Label to edit.
        changes: Field name to new value (only ``name``/``color``).

    Returns:
        The updated Label.

    Raises:
        NotFoundError: If the Team or the Label does not exist (a Label of
            another Team is invisible).
        ForbiddenError: If the actor is not a Team owner (or Admin).
        ValidationError: If a new value is invalid or nothing to update was
            sent.
        ConflictError: If the new name is already taken in the Team.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _visible_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.LABEL_EDIT, TeamResource(team.id)):
            raise ForbiddenError(MSG_LABELS_OWNER_ONLY)
        label = (
            await session.exec(
                select(Label)
                .where(Label.id == label_id, Label.team_id == team.id)
                .with_for_update()
            )
        ).one_or_none()
        if label is None:
            raise NotFoundError(MSG_LABEL_NOT_FOUND)
        if not changes:
            raise ValidationError(MSG_LABEL_UPDATE_EMPTY)
        if "name" in changes:
            new_name = validate_label_name(cast("str", changes["name"]))
            if new_name != label.name:
                clash = (
                    await session.exec(
                        select(Label).where(
                            Label.team_id == team.id,
                            Label.name == new_name,
                            Label.id != label.id,
                        )
                    )
                ).first()
                if clash is not None:
                    raise ConflictError(MSG_LABEL_NAME_EXISTS)
                label.name = new_name
        if "color" in changes:
            label.color = validate_label_color(cast("str", changes["color"]))
        await session.flush()
        await session.refresh(label, ["created_at", "updated_at"])
        return label


async def delete_team_label(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, label_id: uuid.UUID
) -> None:
    """Delete a Label (Team owner or Admin).

    Deleting a Label removes its links from every Issue (Linear behaviour);
    no Activity is written (the Issues were not edited).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team the Label belongs to.
        label_id: The Label to delete.

    Raises:
        NotFoundError: If the Team or the Label does not exist (a Label of
            another Team is invisible).
        ForbiddenError: If the actor is not a Team owner (or Admin).

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _visible_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.LABEL_DELETE, TeamResource(team.id)):
            raise ForbiddenError(MSG_LABELS_OWNER_ONLY)
        label = (
            await session.exec(
                select(Label)
                .where(Label.id == label_id, Label.team_id == team_id)
                .with_for_update()
            )
        ).one_or_none()
        if label is None:
            raise NotFoundError(MSG_LABEL_NOT_FOUND)
        await session.execute(delete(IssueLabel).where(IssueLabel.label_id == label.id))  # type: ignore[arg-type]
        await session.delete(label)
        await session.flush()
