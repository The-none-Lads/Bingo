import pytest
from auth.security import (
    hash_password,
    validate_email,
    validate_password_strength,
    validate_username,
    verify_dummy_password,
    verify_password,
)


class TestAuthSecurity:
    """Test Argon2id password hashing, verification, timing defense, and input validation."""

    def test_hash_and_verify_valid_password(self):
        password = "CorrectHorseBatteryStaple123!"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$argon2id$")
        assert verify_password(password, hashed) is True

    def test_verify_invalid_password_fails(self):
        password = "SecretPassword123"
        hashed = hash_password(password)

        assert verify_password("WrongPassword123", hashed) is False
        assert verify_password("", hashed) is False
        assert verify_password(password, "") is False

    def test_password_strength_validation(self):
        # Too short (< 8 chars)
        with pytest.raises(ValueError, match="at least 8 characters"):
            validate_password_strength("short")

        # Too long (> 128 chars)
        with pytest.raises(ValueError, match="cannot exceed 128"):
            validate_password_strength("a" * 129)

        # Invalid type
        with pytest.raises(ValueError, match="must be a string"):
            validate_password_strength(12345678)  # type: ignore

        # Valid lengths
        validate_password_strength("validpassword123")
        validate_password_strength("a" * 128)

    def test_dummy_verification_executes_safely(self):
        # Must execute without raising exceptions
        verify_dummy_password()

    def test_username_validation(self):
        # Valid usernames
        for valid in ["admin", "birk_11", "user-name", "ABC123"]:
            validate_username(valid)

        # Invalid usernames
        for invalid in ["ab", "a" * 33, "user@name", "user name", "user!"]:
            with pytest.raises(ValueError):
                validate_username(invalid)

    def test_email_validation(self):
        # Valid emails
        for valid in ["test@example.com", "user.name+tag@sub.domain.org"]:
            validate_email(valid)

        # Invalid emails
        for invalid in ["not-an-email", "@example.com", "user@", "user @example.com", "a" * 256]:
            with pytest.raises(ValueError):
                validate_email(invalid)
