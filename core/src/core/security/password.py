"""Password module."""

from passlib.context import CryptContext

pwd_ctx = CryptContext(
    schemes=["argon2"],
    default="argon2",
    # Explicitly pick Argon2id and tune the costs
    argon2__type="ID",  # ensure the id variant
    argon2__memory_cost=64_000,  # KiB  →  64 MiB
    argon2__time_cost=3,  # iterations
    argon2__parallelism=1,
    argon2__salt_size=16,  # bytes
)


def hash_password(password: str) -> str:
    """Hash a password.

    Args:
        password: The password to hash.

    Returns:
        The hashed password.

    """
    return pwd_ctx.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password.

    Args:
        password: The password to verify.
        hashed_password: The stored hash to verify against.

    Returns:
        True if the password is verified, False otherwise.

    """
    ok, _ = pwd_ctx.verify_and_update(password, hashed_password)
    return ok
