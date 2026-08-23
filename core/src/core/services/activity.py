"""Activity writing (the only layer that creates Activity rows; brief §2)."""

from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from core.models.activity import Activity


def record_activity(session: Session | AsyncSession, activity: Activity) -> None:
    """Append an Activity row inside the caller's transaction.

    Args:
        session: The open session (the caller owns the transaction).
        activity: The Activity row to append.

    """
    session.add(activity)
