"""Development seed: a realistic demo Workspace in one command (ticket 11, brief §9).

``make seed`` runs this module (``python -m core.seed``) and creates an Admin,
the Teams ``ENG`` and ``DSGN``, four Users with memberships, and 40 Issues
spread across every State category and priority, with Labels, Markdown
Comments, parent/child links and archived Issues.

The seed is idempotent: every entity is looked up by its natural key before
creation (``User.email``, ``Team.key``, ``Membership (user, team)``,
``Label (team, name)``, ``Issue (team, title)``, ``Comment (issue, author,
body)``) and a run that finds everything changes nothing (no new rows, no
``updated_at`` bumps; ADR 0008). The Admin password is generated and printed
once, on first creation only; pre-existing Users are never reset.
"""

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import engine
from core.domain.authz import Role
from core.domain.workflow import DEFAULT_WORKFLOW_STATES, Category, WorkflowStateRule
from core.models.comment import Comment
from core.models.issue import Issue
from core.models.issue_label import IssueLabel
from core.models.label import Label
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.models.workspace import Workspace
from core.security.password import hash_password
from core.services.comments import create_comment
from core.services.issues import archive_issue, create_issue, transition_issue
from core.services.teams import create_team

ADMIN_EMAIL = "admin@example.com"
# Known dev password for the four seeded Users; printed when they are created.
USER_PASSWORD = "password123"  # noqa: S105  # known dev password, printed at seed time


@dataclass(frozen=True)
class SeedUser:
    """A seeded (non-Admin) User."""

    email: str
    display_name: str


USERS: tuple[SeedUser, ...] = (
    SeedUser("ada@example.com", "Ada Lovelace"),
    SeedUser("grace@example.com", "Grace Hopper"),
    SeedUser("alan@example.com", "Alan Turing"),
    SeedUser("margaret@example.com", "Margaret Hamilton"),
)

# (key, name, description) for the two seeded Teams (brief §2).
TEAMS: tuple[tuple[str, str, str], ...] = (
    ("ENG", "Engineering", "Everything engineering: platform, API and the app itself."),
    ("DSGN", "Design", "Product design: UI, research and the design system."),
)

TEAM_LABELS: dict[str, tuple[tuple[str, str], ...]] = {
    "ENG": (
        ("bug", "#f87171"),
        ("feature", "#4cb371"),
        ("improvement", "#f2c94c"),
        ("performance", "#60a5fa"),
        ("security", "#a78bfa"),
    ),
    "DSGN": (
        ("ui", "#4cb371"),
        ("ux", "#f2c94c"),
        ("research", "#60a5fa"),
        ("design-system", "#a78bfa"),
    ),
}


@dataclass(frozen=True)
class SeedComment:
    """A seeded Comment: the author (by email) and the Markdown body."""

    author_email: str
    body: str


@dataclass(frozen=True)
class SeedIssue:
    """One seeded Issue from the dataset (ticket 11).

    ``state`` is a canonical default Workflow State name (brief §4.1),
    resolved to the Team's actual State (falling back to the first State of
    the same category). ``labels`` reference Team Labels by name, ``comments``
    their authors by email, and ``parent`` another dataset title of the same
    Team (parents must come first in the dataset).
    """

    team: str
    title: str
    state: str
    priority: str
    creator: str
    assignee: str
    labels: tuple[str, ...] = ()
    description: str | None = None
    due_in_days: int | None = None
    estimate: int | None = None
    parent: str | None = None
    archived: bool = False
    comments: tuple[SeedComment, ...] = ()


_ADA = "ada@example.com"
_GRACE = "grace@example.com"
_ALAN = "alan@example.com"
_MARGARET = "margaret@example.com"

# 40 Issues: 20 per Team, across all five State categories and all five
# priorities, with Labels, Comments, parent/child links, due dates, estimates
# and two archived Issues.
ISSUES: tuple[SeedIssue, ...] = (
    # --- ENG (20) ----------------------------------------------------------
    SeedIssue(
        team="ENG",
        title="Set up the core loop",
        state="Done",
        priority="high",
        creator=_ADA,
        assignee=_ADA,
        labels=("feature",),
        description="Register, log in, create the first Team and file the first "
        "Issue: the end-to-end core loop.",
        estimate=8,
        comments=(
            SeedComment(
                _ADA,
                "Core loop is live end to end: register, login, create Team, file the first Issue.",
            ),
        ),
    ),
    SeedIssue(
        team="ENG",
        title="Bootstrap registration creates the workspace Admin",
        state="Done",
        priority="urgent",
        creator=_GRACE,
        assignee=_ADA,
        labels=("feature", "security"),
    ),
    SeedIssue(
        team="ENG",
        title="JWT access token uses the user id as subject",
        state="Done",
        priority="medium",
        creator=_ADA,
        assignee=_ALAN,
    ),
    SeedIssue(
        team="ENG",
        title="Team creation seeds the default Workflow",
        state="Done",
        priority="high",
        creator=_ALAN,
        assignee=_GRACE,
        labels=("feature",),
    ),
    SeedIssue(
        team="ENG",
        title="Issue numbers allocated under a row lock",
        state="Done",
        priority="urgent",
        creator=_GRACE,
        assignee=_ADA,
        labels=("performance",),
        description="The number comes from teams.next_issue_number while the Team "
        "row is locked, so concurrent creates never collide (ADR 0010).",
        estimate=5,
    ),
    SeedIssue(
        team="ENG",
        title="List Issues with filters and cursor pagination",
        state="Done",
        priority="medium",
        creator=_ADA,
        assignee=_GRACE,
        labels=("feature",),
    ),
    SeedIssue(
        team="ENG",
        title="Issue detail with inline title edit",
        state="Done",
        priority="high",
        creator=_GRACE,
        assignee=_ALAN,
        labels=("feature",),
    ),
    SeedIssue(
        team="ENG",
        title="Board view with drag and drop transitions",
        state="Done",
        priority="high",
        creator=_ALAN,
        assignee=_GRACE,
        labels=("feature",),
        estimate=13,
    ),
    SeedIssue(
        team="ENG",
        title="Comments with Markdown rendering",
        state="Done",
        priority="medium",
        creator=_ADA,
        assignee=_ALAN,
        labels=("feature",),
    ),
    SeedIssue(
        team="ENG",
        title="Archive, restore and hard delete",
        state="Done",
        priority="high",
        creator=_GRACE,
        assignee=_ADA,
        estimate=8,
    ),
    SeedIssue(
        team="ENG",
        title="Global search across the user's Teams",
        state="In Progress",
        priority="high",
        creator=_ALAN,
        assignee=_GRACE,
        labels=("feature",),
        due_in_days=7,
        estimate=8,
        comments=(
            SeedComment(
                _GRACE,
                "Search matches identifier and title substrings across all of the user's Teams.",
            ),
        ),
    ),
    SeedIssue(
        team="ENG",
        title="Search keyboard navigation",
        state="In Progress",
        priority="medium",
        creator=_ADA,
        assignee=_ALAN,
        parent="Global search across the user's Teams",
    ),
    SeedIssue(
        team="ENG",
        title="My Issues aggregation across Teams",
        state="In Progress",
        priority="medium",
        creator=_GRACE,
        assignee=_ADA,
        labels=("feature",),
    ),
    SeedIssue(
        team="ENG",
        title="Optimistic concurrency on Issue updates",
        state="In Review",
        priority="urgent",
        creator=_ADA,
        assignee=_ALAN,
        labels=("performance",),
        estimate=5,
        comments=(
            SeedComment(
                _ALAN, "409s now carry the server-side timestamp; the client refetches and toasts."
            ),
            SeedComment(_GRACE, "Nice. The optimistic rollback feels smooth."),
        ),
    ),
    SeedIssue(
        team="ENG",
        title="Rate limit login attempts",
        state="Todo",
        priority="high",
        creator=_GRACE,
        assignee=_ADA,
        labels=("security",),
        due_in_days=14,
        estimate=3,
        comments=(
            SeedComment(
                _ADA, "In-process limiter: 10 attempts per 15 minutes per email and IP (ADR 0009)."
            ),
        ),
    ),
    SeedIssue(
        team="ENG",
        title="Bulk operations for Issues",
        state="Todo",
        priority="medium",
        creator=_ADA,
        assignee=_GRACE,
        labels=("feature",),
        estimate=8,
    ),
    SeedIssue(
        team="ENG",
        title="Theme preference per user",
        state="Backlog",
        priority="low",
        creator=_ADA,
        assignee=_ALAN,
        estimate=3,
    ),
    SeedIssue(
        team="ENG",
        title="Dark mode contrast pass",
        state="Backlog",
        priority="low",
        creator=_MARGARET,
        assignee=_GRACE,
        estimate=3,
    ),
    SeedIssue(
        team="ENG",
        title="Empty states for list views",
        state="Backlog",
        priority="none",
        creator=_ALAN,
        assignee=_ADA,
    ),
    SeedIssue(
        team="ENG",
        title="Legacy session token cleanup",
        state="Canceled",
        priority="none",
        creator=_GRACE,
        assignee=_ALAN,
        archived=True,
        comments=(SeedComment(_GRACE, "Superseded by the JWT switch; nothing left to clean up."),),
    ),
    # --- DSGN (20) ---------------------------------------------------------
    SeedIssue(
        team="DSGN",
        title="Design system foundation: tokens and type scale",
        state="Done",
        priority="high",
        creator=_MARGARET,
        assignee=_MARGARET,
        labels=("design-system",),
        estimate=13,
        comments=(
            SeedComment(
                _MARGARET,
                "Tokens live in the @theme block; every screen reads from the token layer.",
            ),
        ),
    ),
    SeedIssue(
        team="DSGN",
        title="Component library: Button, Input, Select",
        state="Done",
        priority="high",
        creator=_ADA,
        assignee=_MARGARET,
        labels=("ui", "design-system"),
        estimate=13,
    ),
    SeedIssue(
        team="DSGN",
        title="Button, Input and Select states",
        state="Done",
        priority="medium",
        creator=_MARGARET,
        assignee=_MARGARET,
        labels=("ui",),
        parent="Component library: Button, Input, Select",
    ),
    SeedIssue(
        team="DSGN",
        title="Issue detail layout: properties column",
        state="Done",
        priority="medium",
        creator=_MARGARET,
        assignee=_ADA,
        labels=("ui",),
        estimate=5,
    ),
    SeedIssue(
        team="DSGN",
        title="Empty states and skeletons",
        state="Done",
        priority="low",
        creator=_ADA,
        assignee=_MARGARET,
        labels=("ui",),
    ),
    SeedIssue(
        team="DSGN",
        title="Onboarding flow for new users",
        state="Done",
        priority="high",
        creator=_GRACE,
        assignee=_MARGARET,
        labels=("ux",),
        estimate=8,
    ),
    SeedIssue(
        team="DSGN",
        title="Keyboard-first navigation model",
        state="Done",
        priority="urgent",
        creator=_MARGARET,
        assignee=_ALAN,
        labels=("ux",),
    ),
    SeedIssue(
        team="DSGN",
        title="Notification preferences screen",
        state="In Progress",
        priority="medium",
        creator=_ALAN,
        assignee=_MARGARET,
        labels=("ux",),
        estimate=5,
    ),
    SeedIssue(
        team="DSGN",
        title="Notification preferences: email digest",
        state="Todo",
        priority="medium",
        creator=_ALAN,
        assignee=_MARGARET,
        parent="Notification preferences screen",
    ),
    SeedIssue(
        team="DSGN",
        title="Mobile layout at the 768px breakpoint",
        state="In Progress",
        priority="high",
        creator=_MARGARET,
        assignee=_MARGARET,
        labels=("ui",),
        due_in_days=10,
        estimate=8,
        comments=(
            SeedComment(_MARGARET, "Below 768px the Issue detail panel becomes the full page."),
        ),
    ),
    SeedIssue(
        team="DSGN",
        title="Colour and contrast audit",
        state="In Review",
        priority="medium",
        creator=_MARGARET,
        assignee=_ADA,
        labels=("ux", "design-system"),
        estimate=3,
        comments=(SeedComment(_ADA, "Contrast ratios verified against WCAG AA for both themes."),),
    ),
    SeedIssue(
        team="DSGN",
        title="Iconography set from lucide",
        state="Todo",
        priority="low",
        creator=_ALAN,
        assignee=_MARGARET,
        labels=("design-system",),
    ),
    SeedIssue(
        team="DSGN",
        title="Typography scale for dense list views",
        state="Todo",
        priority="medium",
        creator=_ADA,
        assignee=_MARGARET,
        estimate=3,
    ),
    SeedIssue(
        team="DSGN",
        title="Search overlay visual design",
        state="Todo",
        priority="high",
        creator=_ADA,
        assignee=_MARGARET,
        labels=("ui", "ux"),
        due_in_days=5,
        estimate=5,
    ),
    SeedIssue(
        team="DSGN",
        title="Error and toasting patterns",
        state="Backlog",
        priority="medium",
        creator=_MARGARET,
        assignee=_ADA,
        labels=("ui",),
    ),
    SeedIssue(
        team="DSGN",
        title="Dark theme visual pass",
        state="Backlog",
        priority="medium",
        creator=_ALAN,
        assignee=_MARGARET,
        labels=("design-system",),
        estimate=3,
    ),
    SeedIssue(
        team="DSGN",
        title="Accessibility audit: focus and ARIA",
        state="Backlog",
        priority="urgent",
        creator=_ADA,
        assignee=_ALAN,
        labels=("ux",),
        due_in_days=21,
        estimate=8,
        comments=(
            SeedComment(
                _ALAN,
                "Board columns and list items carry proper ARIA roles; "
                "colour is never the only carrier of meaning.",
            ),
        ),
    ),
    SeedIssue(
        team="DSGN",
        title="Voice-over pass on the board",
        state="Backlog",
        priority="high",
        creator=_ADA,
        assignee=_MARGARET,
        labels=("ux",),
        estimate=5,
    ),
    SeedIssue(
        team="DSGN",
        title="Brand guidelines doc",
        state="Backlog",
        priority="none",
        creator=_MARGARET,
        assignee=_ADA,
    ),
    SeedIssue(
        team="DSGN",
        title="Legacy widget redesign",
        state="Canceled",
        priority="low",
        creator=_GRACE,
        assignee=_MARGARET,
        archived=True,
    ),
)

_STATE_CATEGORIES: dict[str, Category] = {
    rule.name: rule.category for rule in DEFAULT_WORKFLOW_STATES
}


@dataclass
class SeedReport:
    """What a seed run created (the CLI prints it; the tests assert on it)."""

    admin_created: bool = False
    admin_password: str | None = None
    users_created: int = 0
    team_keys: list[str] = field(default_factory=list)
    states_created: int = 0
    memberships_created: int = 0
    labels_created: int = 0
    issues_created: int = 0
    issues_archived: int = 0
    comments_created: int = 0
    issue_labels_created: int = 0
    total_users: int = 0
    total_issues: int = 0
    total_comments: int = 0


@dataclass
class SeedContext:
    """Shared lookups of one seed run (Users, Teams, States, Labels, report)."""

    session: AsyncSession
    report: SeedReport
    admin: User
    users: dict[str, User] = field(default_factory=dict)
    teams: dict[str, Team] = field(default_factory=dict)
    team_states: dict[str, dict[str, WorkflowState]] = field(default_factory=dict)
    team_labels: dict[tuple[str, str], Label] = field(default_factory=dict)


def generate_admin_password() -> str:
    """Generate the Admin password (printed once, on first creation)."""
    return secrets.token_urlsafe(12)


async def seed(session: AsyncSession) -> SeedReport:
    """Create (or top up) the demo Workspace; idempotent (ticket 11).

    Every step owns a single transaction (the house service shape): a lookup
    and the conditional write happen inside one ``session.begin()``, so no
    read is ever left in a transaction that a later service call would find
    open.

    Args:
        session: The database session (each step owns its transaction).

    Returns:
        A report of what was created this run.

    """
    report = SeedReport()
    await _ensure_workspace(session)
    admin = await _ensure_admin(session, report)
    ctx = SeedContext(session=session, report=report, admin=admin)
    await _ensure_users(ctx)
    await _ensure_teams(ctx)
    await _ensure_team_states(ctx)
    await _ensure_memberships(ctx)
    await _ensure_labels(ctx)
    await _ensure_issues(ctx)
    report.total_users = len((await ctx.session.exec(select(User))).all())
    report.total_issues = len((await ctx.session.exec(select(Issue))).all())
    report.total_comments = len((await ctx.session.exec(select(Comment))).all())
    return report


async def _ensure_workspace(session: AsyncSession) -> None:
    """Create the single Workspace root if it does not exist (brief §2)."""
    async with session.begin():
        workspace = (await session.exec(select(Workspace).limit(1))).first()
        if workspace is None:
            session.add(Workspace())


async def _ensure_admin(session: AsyncSession, report: SeedReport) -> User:
    """Create the workspace Admin directly through the model.

    The register endpoint is closed as soon as any User exists, so the seed
    writes the model itself (Argon2id hash). On re-runs the existing Admin is
    left untouched: no password reset, no reprint.
    """
    async with session.begin():
        admin = (await session.exec(select(User).where(User.email == ADMIN_EMAIL))).one_or_none()
        if admin is not None:
            return admin
        password = generate_admin_password()
        admin = User(
            email=ADMIN_EMAIL,
            hashed_password=hash_password(password),
            display_name="Workspace Admin",
            is_admin=True,
        )
        session.add(admin)
        await session.flush()
        report.admin_created = True
        report.admin_password = password
        return admin


async def _ensure_users(ctx: SeedContext) -> None:
    """Create the four seeded Users (known dev password; printed on creation)."""
    for spec in USERS:
        async with ctx.session.begin():
            user = (
                await ctx.session.exec(select(User).where(User.email == spec.email))
            ).one_or_none()
            if user is not None:
                ctx.users[spec.email] = user
                continue
            user = User(
                email=spec.email,
                hashed_password=hash_password(USER_PASSWORD),
                display_name=spec.display_name,
            )
            ctx.session.add(user)
            await ctx.session.flush()
            ctx.report.users_created += 1
            ctx.users[spec.email] = user


async def _ensure_teams(ctx: SeedContext) -> None:
    """Create the ENG and DSGN Teams (default Workflow, owner Membership).

    A Team that already exists is kept as-is, including its Workflow and
    ownership; only missing Teams are created (the Admin becomes owner).
    """
    for key, name, description in TEAMS:
        team = None
        async with ctx.session.begin():
            team = (await ctx.session.exec(select(Team).where(Team.key == key))).one_or_none()
        if team is None:
            team = await create_team(
                ctx.session, user=ctx.admin, name=name, key=key, description=description
            )
            ctx.report.team_keys.append(key)
        ctx.teams[key] = team


async def _ensure_team_states(ctx: SeedContext) -> None:
    """Guarantee every Team's Workflow covers all five State categories.

    A Team created through the normal flow already has the six default States
    (brief §4.1); if a State was deleted in the editor, the first canonical
    State of the missing category is appended so the seeded Issues have a
    home in every category.
    """
    for key, team in ctx.teams.items():
        async with ctx.session.begin():
            workflow = (
                await ctx.session.exec(select(Workflow).where(Workflow.team_id == team.id))
            ).one()
            states = list(
                await ctx.session.exec(
                    select(WorkflowState)
                    .where(WorkflowState.workflow_id == workflow.id)
                    .order_by(WorkflowState.position)  # type: ignore[attr-defined,arg-type]  # SQLModel field is a Column at runtime
                )
            )
            covered = {state.category for state in states}
            missing: list[WorkflowStateRule] = []
            for rule in DEFAULT_WORKFLOW_STATES:
                if rule.category not in covered and rule.category not in {
                    r.category for r in missing
                }:
                    missing.append(rule)
            next_position = max((state.position for state in states), default=-1) + 1
            new_states: list[WorkflowState] = []
            for rule in missing:
                state = WorkflowState(
                    workflow_id=workflow.id,
                    name=rule.name,
                    category=rule.category,
                    color=rule.color,
                    position=next_position,
                )
                ctx.session.add(state)
                new_states.append(state)
                next_position += 1
            if new_states:
                await ctx.session.flush()
                ctx.report.states_created += len(new_states)
            states.extend(new_states)
        ctx.team_states[key] = {state.name: state for state in states}


async def _ensure_memberships(ctx: SeedContext) -> None:
    """Give every seeded User a member Membership in both Teams."""
    for user in ctx.users.values():
        for team in ctx.teams.values():
            async with ctx.session.begin():
                membership = (
                    await ctx.session.exec(
                        select(Membership).where(
                            Membership.user_id == user.id, Membership.team_id == team.id
                        )
                    )
                ).first()
                if membership is None:
                    ctx.session.add(
                        Membership(user_id=user.id, team_id=team.id, role=Role.MEMBER.value)
                    )
                    await ctx.session.flush()
                    ctx.report.memberships_created += 1


async def _ensure_labels(ctx: SeedContext) -> None:
    """Create each Team's Labels (lookup-or-create by (team, name))."""
    for key, labels in TEAM_LABELS.items():
        team = ctx.teams[key]
        for name, color in labels:
            async with ctx.session.begin():
                label = (
                    await ctx.session.exec(
                        select(Label).where(Label.team_id == team.id, Label.name == name)
                    )
                ).one_or_none()
                if label is None:
                    label = Label(team_id=team.id, name=name, color=color)
                    ctx.session.add(label)
                    await ctx.session.flush()
                    ctx.report.labels_created += 1
                ctx.team_labels[(key, name)] = label


async def _ensure_issues(ctx: SeedContext) -> None:
    """Create the 40 seeded Issues (idempotent by (team, title, creator)).

    A seeded Issue already in the database is recognised by (team, title)
    **and** a creator among the four seeded Users: only then is a pending
    transition completed, missing Comment and Label links re-created and a
    pending archive finished, so an interrupted run converges on the dataset.
    An Issue with a colliding title created by anyone else is a user Issue
    and is left entirely untouched (no Comments, no Label links, no archive).
    """
    seed_user_ids = {user.id for user in ctx.users.values()}
    for spec in ISSUES:
        team = ctx.teams[spec.team]
        issue = None
        async with ctx.session.begin():
            issue = (
                await ctx.session.exec(
                    select(Issue).where(Issue.team_id == team.id, Issue.title == spec.title)
                )
            ).first()
        if issue is not None and issue.creator_id not in seed_user_ids:
            continue
        if issue is None:
            issue = await _create_seeded_issue(ctx, spec)
            ctx.report.issues_created += 1
        else:
            state = _resolve_state(ctx, spec)
            if issue.state_id != state.id:
                _, issue = await transition_issue(
                    ctx.session,
                    user=ctx.users[spec.assignee],
                    issue_id=issue.id,
                    state_id=state.id,
                    updated_at=issue.updated_at,
                )
        await _ensure_issue_comments(ctx, spec, issue)
        await _ensure_issue_labels(ctx, spec, issue)
        if spec.archived and issue.archived_at is None:
            _, issue = await archive_issue(ctx.session, user=ctx.admin, issue_id=issue.id)
            ctx.report.issues_archived += 1


async def _create_seeded_issue(ctx: SeedContext, spec: SeedIssue) -> Issue:
    """Create one seeded Issue through the services (numbers, Activity).

    ``create_issue`` allocates the per-Team number under the row lock and
    writes the creation Activity (ADR 0010); one transaction then sets the
    remaining fields and Label links (no Activity rows: the seed's field
    setup is not user activity); ``transition_issue`` moves the Issue to its
    target State through the single transition code path (brief §3.3).
    """
    creator = ctx.users[spec.creator]
    assignee = ctx.users[spec.assignee]
    state = _resolve_state(ctx, spec)
    parent_id = None
    if spec.parent is not None:
        parent = None
        async with ctx.session.begin():
            parent = (
                await ctx.session.exec(
                    select(Issue).where(
                        Issue.team_id == ctx.teams[spec.team].id, Issue.title == spec.parent
                    )
                )
            ).first()
        if parent is None:
            msg = f"Seeded parent Issue '{spec.parent}' not found"
            raise RuntimeError(msg)
        parent_id = parent.id

    _, issue = await create_issue(
        ctx.session, user=creator, team_id=ctx.teams[spec.team].id, title=spec.title
    )

    async with ctx.session.begin():
        if spec.description is not None:
            issue.description = spec.description
        if spec.priority != "none":
            issue.priority = spec.priority
        issue.assignee_id = assignee.id
        if spec.due_in_days is not None:
            issue.due_date = datetime.now(UTC).date() + timedelta(days=spec.due_in_days)
        if spec.estimate is not None:
            issue.estimate = spec.estimate
        issue.parent_id = parent_id
        for label_name in spec.labels:
            ctx.session.add(
                IssueLabel(issue_id=issue.id, label_id=ctx.team_labels[(spec.team, label_name)].id)
            )
        ctx.report.issue_labels_created += len(spec.labels)
        await ctx.session.flush()
        await ctx.session.refresh(
            issue, ["state", "assignee", "labels", "created_at", "updated_at"]
        )

    if issue.state_id != state.id:
        _, issue = await transition_issue(
            ctx.session,
            user=assignee,
            issue_id=issue.id,
            state_id=state.id,
            updated_at=issue.updated_at,
        )
    return issue


def _resolve_state(ctx: SeedContext, spec: SeedIssue) -> WorkflowState:
    """Resolve a dataset State name to the Team's actual State.

    The dataset uses the canonical default State names (brief §4.1); if the
    Team's Workflow renamed a State, the first State of the same category is
    used instead, so the seed works with any fully covered Workflow.
    """
    states = ctx.team_states[spec.team]
    if spec.state in states:
        return states[spec.state]
    category = _STATE_CATEGORIES[spec.state]
    candidates = sorted(
        (state for state in states.values() if state.category == category),
        key=lambda state: state.position,
    )
    if not candidates:
        msg = f"Team {spec.team} has no State in category {category}"
        raise RuntimeError(msg)
    return candidates[0]


async def _ensure_issue_comments(ctx: SeedContext, spec: SeedIssue, issue: Issue) -> None:
    """Create the Issue's seeded Comments (by (issue, author, body)).

    Archived Issues are skipped: ``create_comment`` refuses them (404), and
    a Comment on an archived Issue would not show in any default view.
    """
    if issue.archived_at is not None:
        return
    for comment_spec in spec.comments:
        author = ctx.users[comment_spec.author_email]
        exists = False
        async with ctx.session.begin():
            existing = (
                await ctx.session.exec(
                    select(Comment).where(
                        Comment.issue_id == issue.id,
                        Comment.author_id == author.id,
                        Comment.body == comment_spec.body,
                    )
                )
            ).first()
            exists = existing is not None
        if not exists:
            await create_comment(
                ctx.session, user=author, issue_id=issue.id, body=comment_spec.body
            )
            ctx.report.comments_created += 1


async def _ensure_issue_labels(ctx: SeedContext, spec: SeedIssue, issue: Issue) -> None:
    """Link the Issue to its seeded Labels (by (issue, label))."""
    for label_name in spec.labels:
        label = ctx.team_labels[(spec.team, label_name)]
        async with ctx.session.begin():
            existing = (
                await ctx.session.exec(
                    select(IssueLabel).where(
                        IssueLabel.issue_id == issue.id, IssueLabel.label_id == label.id
                    )
                )
            ).first()
            if existing is None:
                ctx.session.add(IssueLabel(issue_id=issue.id, label_id=label.id))
                await ctx.session.flush()
                ctx.report.issue_labels_created += 1


def format_report(report: SeedReport) -> str:
    """Render the seed summary for the CLI.

    Args:
        report: What the seed run created.

    Returns:
        The multi-line summary to print.

    """
    admin = (
        f"Admin {ADMIN_EMAIL} created; password (shown once): {report.admin_password}"
        if report.admin_created
        else f"Admin {ADMIN_EMAIL} already exists (password unchanged)"
    )
    users = (
        f"Users: {report.users_created} created (known password: {USER_PASSWORD})"
        if report.users_created
        else "Users: all 4 already exist"
    )
    teams = (
        f"Teams: created {', '.join(report.team_keys)}"
        if report.team_keys
        else "Teams: ENG and DSGN already exist"
    )
    return "\n".join(
        (
            "Seed complete.",
            admin,
            users,
            teams,
            f"States: {report.states_created} added (missing categories covered)",
            f"Issues: {report.issues_created} created, {report.issues_archived} archived, "
            f"{report.total_issues} total",
            f"Labels: {report.labels_created} created, {report.issue_labels_created} "
            f"Issue links added",
            f"Comments: {report.comments_created} created, {report.total_comments} total",
        )
    )


async def run_seed() -> None:
    """Open a session, run the seed and print the summary (CLI entry)."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        report = await seed(session)
    print(format_report(report))  # noqa: T201  # CLI output


def main() -> None:
    """Run the seed against the configured database (``python -m core.seed``)."""
    asyncio.run(run_seed())


if __name__ == "__main__":
    main()
