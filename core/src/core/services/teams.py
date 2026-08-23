"""Team use-cases (brief §6): creation with Workflow seeding, listing."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, Role, can
from core.domain.errors import ConflictError, ForbiddenError, ValidationError
from core.domain.identifiers import is_valid_team_key
from core.domain.workflow import DEFAULT_WORKFLOW_STATES
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.services.actors import load_actor

MSG_ADMIN_ONLY = "Only workspace admins can create Teams"
MSG_NAME_INVALID = "Team name must be 1-100 characters"
MSG_KEY_INVALID = "Team key must be 2-5 uppercase letters (A-Z)"
MSG_KEY_EXISTS = "A Team with this key already exists"
TEAM_NAME_MAX_LENGTH = 100


async def create_team(
    session: AsyncSession, *, user: User, name: str, key: str, description: str | None
) -> Team:
    """Create a Team with its default Workflow and the owner Membership.

    The creating Admin becomes ``owner``; the six default Workflow States are
    seeded in the same transaction (brief §4.1, ADR 0005).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        name: Team name (1-100 chars, trimmed).
        key: Team key (2-5 uppercase letters, unique, immutable).
        description: Optional description.

    Returns:
        The created Team.

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.
        ValidationError: If the name or key is invalid.
        ConflictError: If the key is already taken.

    """
    name = name.strip()
    if not name or len(name) > TEAM_NAME_MAX_LENGTH:
        raise ValidationError(MSG_NAME_INVALID)
    if not is_valid_team_key(key):
        raise ValidationError(MSG_KEY_INVALID)
    clean_description = description.strip() if description and description.strip() else None

    async with session.begin():
        actor = await load_actor(session, user)
        if not can(actor, Action.TEAM_CREATE, None):
            raise ForbiddenError(MSG_ADMIN_ONLY)
        existing = (await session.exec(select(Team).where(Team.key == key))).first()
        if existing is not None:
            raise ConflictError(MSG_KEY_EXISTS)
        team = Team(name=name, key=key, description=clean_description)
        session.add(team)
        await session.flush()

        workflow = Workflow(team_id=team.id)
        session.add(workflow)
        await session.flush()
        for state_rule in DEFAULT_WORKFLOW_STATES:
            session.add(
                WorkflowState(
                    workflow_id=workflow.id,
                    name=state_rule.name,
                    category=state_rule.category,
                    color=state_rule.color,
                    position=state_rule.position,
                )
            )
        session.add(Membership(user_id=actor.user_id, team_id=team.id, role=Role.OWNER.value))
        await session.flush()
        return team


async def list_teams(session: AsyncSession, *, user: User) -> list[Team]:
    """List the non-archived Teams visible to the actor.

    Admins see all Teams; members see only their own.

    Args:
        session: The database session.
        user: The authenticated acting user.

    Returns:
        The visible Teams, ordered by name.

    """
    actor = await load_actor(session, user)
    statement = (
        select(Team)
        .where(Team.archived_at.is_(None))  # type: ignore[union-attr]
        .order_by(Team.name)
    )
    if not actor.is_admin:
        team_ids = list(actor.team_roles)
        if not team_ids:
            return []
        statement = statement.where(Team.id.in_(team_ids))  # type: ignore[attr-defined]
    return list((await session.exec(statement)).all())
