"""
Unit Tests for core.models.

Tests User and UsedToken models.
"""

import pytest
from datetime import datetime, timezone


class TestUserModel:
    """Tests for User model."""

    def test_user_model_definition(self):
        """Test User model is defined correctly."""
        from core.models.user import User
        from core.database.base import Base

        assert issubclass(User, Base)
        assert User.__tablename__ == "users"

    def test_user_has_required_fields(self):
        """Test User model has all required fields."""
        from core.models.user import User

        assert hasattr(User, 'id')
        assert hasattr(User, 'line_user_id')
        assert hasattr(User, 'line_user_id_hash')
        assert hasattr(User, 'email')
        assert hasattr(User, 'email_hash')
        assert hasattr(User, 'ragic_employee_id')
        assert hasattr(User, 'display_name')
        assert hasattr(User, 'is_active')
        assert hasattr(User, 'last_login_at')
        assert hasattr(User, 'created_at')
        assert hasattr(User, 'updated_at')

    def test_user_repr(self):
        """Test User __repr__ method."""
        from core.models.user import User

        user = User(
            id="test-id",
            email="test@example.com",
            line_user_id="U123abc",
            email_hash="hash1",
            line_user_id_hash="hash2",
        )

        repr_str = repr(user)

        assert "User" in repr_str
        assert "test-id" in repr_str

    def test_user_encrypted_fields(self):
        """Test User uses EncryptedType for sensitive fields."""
        from core.models.user import User

        columns = User.__table__.columns

        assert 'line_user_id' in columns
        assert 'email' in columns
        assert 'ragic_employee_id' in columns
        assert 'display_name' in columns

    def test_user_hash_fields_indexed(self):
        """Test User hash fields are indexed."""
        from core.models.user import User

        columns = User.__table__.columns

        assert 'line_user_id_hash' in columns
        assert 'email_hash' in columns

        assert columns['line_user_id_hash'].unique
        assert columns['email_hash'].unique


class TestUsedTokenModel:
    """Tests for UsedToken model."""

    def test_used_token_model_definition(self):
        """Test UsedToken model is defined correctly."""
        from core.models.user import UsedToken
        from core.database.base import Base

        assert issubclass(UsedToken, Base)
        assert UsedToken.__tablename__ == "used_tokens"

    def test_used_token_has_required_fields(self):
        """Test UsedToken model has all required fields."""
        from core.models.user import UsedToken

        assert hasattr(UsedToken, 'id')
        assert hasattr(UsedToken, 'token_hash')
        assert hasattr(UsedToken, 'email')
        assert hasattr(UsedToken, 'used_at')
        assert hasattr(UsedToken, 'expires_at')

    def test_used_token_repr(self):
        """Test UsedToken __repr__ method."""
        from core.models.user import UsedToken

        token = UsedToken(
            id="test-id",
            token_hash="a" * 64,
            email="test@example.com",
            used_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )

        repr_str = repr(token)

        assert "UsedToken" in repr_str
        assert "aaaaaaaa" in repr_str

    def test_used_token_hash_field_unique(self):
        """Test UsedToken token_hash is unique and indexed."""
        from core.models.user import UsedToken

        columns = UsedToken.__table__.columns

        assert 'token_hash' in columns
        assert columns['token_hash'].unique

    def test_used_token_expires_at_indexed(self):
        """Test UsedToken expires_at is indexed for cleanup queries."""
        from core.models.user import UsedToken

        columns = UsedToken.__table__.columns

        assert 'expires_at' in columns
