import re
import argon2
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# OWASP Recommended Argon2id Parameters:
# - Memory cost: 64 MB (65536 KiB)
# - Time cost: 3 iterations
# - Parallelism: 4 threads
# - Hash length: 32 bytes
# - Salt length: 16 bytes
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID,
)

# Pre-computed dummy Argon2id hash for constant-time dummy verification when user is not found
_DUMMY_HASH = _hasher.hash("constant_time_dummy_password_for_timing_defense_12345")


def validate_password_strength(password: str) -> None:
    """
    Validate password strength requirements:
    - Minimum length: 8 characters
    - Maximum length: 128 characters (DoS protection against long password hashing)
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(password) > 128:
        raise ValueError("Password cannot exceed 128 characters.")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using Argon2id.
    Note: In Python, string objects are immutable and memory zeroization cannot be guaranteed.
    Security is maintained by minimizing variable lifetime, never persisting plaintext,
    and using vetted Argon2id parameters.
    """
    validate_password_strength(password)
    return _hasher.hash(password)


def hash_game_password(password: str) -> str:
    """Hash a game party access password or PIN (4-128 characters) using Argon2id."""
    if not isinstance(password, str) or len(password) < 4 or len(password) > 128:
        raise ValueError("Game password must be between 4 and 128 characters long.")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against an Argon2id hash.
    Returns True if valid, False otherwise.
    """
    if not password or not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_password() -> None:
    """
    Execute a dummy password verification against a static hash.
    Used when a requested username/email does not exist, eliminating timing side-channels.
    """
    try:
        _hasher.verify(_DUMMY_HASH, "wrong_dummy_password_input")
    except VerifyMismatchError:
        pass


def validate_username(username: str) -> None:
    """Validate username format: 3-32 alphanumeric, underscores, hyphens."""
    if not isinstance(username, str) or not re.match(r"^[a-zA-Z0-9_-]{3,32}$", username):
        raise ValueError("Username must be between 3 and 32 alphanumeric characters, underscores, or hyphens.")


def validate_email(email: str) -> None:
    """Validate email format."""
    if not isinstance(email, str) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or len(email) > 255:
        raise ValueError("Invalid email address format.")
