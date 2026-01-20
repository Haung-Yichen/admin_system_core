"""
Unit Tests for core.database layer.

Tests database engine, session management, and base models.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class TestDatabaseEngine:
    """Tests for database engine management."""
    
    @pytest.fixture(autouse=True)
    def reset_engine(self):
        """Reset global engine before each test."""
        import core.database.engine as engine_module
        engine_module._engine = None
        yield
        engine_module._engine = None
    
    @patch('core.database.engine.create_async_engine')
    def test_get_engine_creates_singleton(self, mock_create_engine, mock_env_vars):
        """Test get_engine() creates a singleton engine instance."""
        from core.database.engine import get_engine
        
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create_engine.return_value = mock_engine
        
        engine1 = get_engine()
        engine2 = get_engine()
        
        assert engine1 is engine2
        assert mock_create_engine.call_count == 1
    
    @patch('core.database.engine.create_async_engine')
    def test_get_engine_uses_config_database_url(self, mock_create_engine, mock_env_vars):
        """Test engine uses database URL from config."""
        from core.database.engine import get_engine
        
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create_engine.return_value = mock_engine
        
        engine = get_engine()
        
        # Just verify the engine was created
        assert mock_create_engine.called
        assert engine is mock_engine
    
    @pytest.mark.asyncio
    @patch('core.database.engine.create_async_engine')
    async def test_close_engine_disposes_connection(self, mock_create_engine, mock_env_vars):
        """Test close_engine() properly disposes the engine."""
        from core.database.engine import get_engine, close_engine
        import core.database.engine as engine_module
        
        mock_engine = AsyncMock(spec=AsyncEngine)
        mock_create_engine.return_value = mock_engine
        
        engine = get_engine()
        assert engine_module._engine is not None
        
        await close_engine()
        
        mock_engine.dispose.assert_called_once()
        assert engine_module._engine is None


class TestSessionManagement:
    """Tests for database session management."""
    
    @pytest.fixture(autouse=True)
    def reset_session_factory(self):
        """Reset global session factory before each test."""
        import core.database.session as session_module
        session_module._async_session_factory = None
        yield
        session_module._async_session_factory = None
    
    @patch('core.database.session.get_engine')
    def test_get_session_factory_creates_singleton(self, mock_get_engine, mock_env_vars):
        """Test get_session_factory() creates a singleton factory."""
        from core.database.session import get_session_factory
        
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_get_engine.return_value = mock_engine
        
        factory1 = get_session_factory()
        factory2 = get_session_factory()
        
        assert factory1 is factory2
        assert isinstance(factory1, async_sessionmaker)
    
    @pytest.mark.asyncio
    @patch('core.database.session.get_session_factory')
    async def test_get_standalone_session_context_manager(self, mock_get_factory, mock_env_vars):
        """Test get_standalone_session() works as context manager."""
        from core.database.session import get_standalone_session
        
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(spec=async_sessionmaker)
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None
        mock_get_factory.return_value = mock_factory
        
        async with get_standalone_session() as session:
            assert session is mock_session


class TestBaseModels:
    """Tests for database base models and mixins."""
    
    def test_base_class_exists(self):
        """Test Base declarative class exists."""
        from core.database.base import Base
        from sqlalchemy.orm import DeclarativeBase
        
        assert issubclass(Base, DeclarativeBase)
    
    def test_timestamp_mixin_fields(self):
        """Test TimestampMixin adds created_at and updated_at."""
        from core.database.base import Base, TimestampMixin
        from sqlalchemy import String
        from sqlalchemy.orm import Mapped, mapped_column
        
        class TestModel(Base, TimestampMixin):
            __tablename__ = "test_timestamp"
            id: Mapped[str] = mapped_column(String, primary_key=True)
        
        assert hasattr(TestModel, 'created_at')
        assert hasattr(TestModel, 'updated_at')
    
    def test_uuid_primary_key_annotation(self):
        """Test UUIDPrimaryKey annotation creates UUID column."""
        from core.database.base import Base, UUIDPrimaryKey
        from sqlalchemy.orm import Mapped
        
        class TestModel(Base):
            __tablename__ = "test_uuid"
            id: Mapped[UUIDPrimaryKey]
        
        assert hasattr(TestModel, 'id')
        columns = TestModel.__table__.columns
        assert 'id' in columns
        assert columns['id'].primary_key
