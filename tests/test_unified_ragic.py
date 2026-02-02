"""
Unit Tests for Unified Ragic Services.

Tests all Ragic API functionality in:
- core/services/ragic.py (RagicService - Employee verification)

Sync services are tested separately in:
- modules/administrative/tests/test_ragic_sync.py (Integration tests)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date
import httpx


# =============================================================================
# Core RagicService Tests (Employee Verification)
# =============================================================================

class TestCoreRagicServiceInit:
    """Tests for core EmployeeVerificationService initialization."""

    def test_init_loads_config(self, mock_env_vars):
        """Test service initializes with config."""
        from core.services.ragic import EmployeeVerificationService
        
        service = EmployeeVerificationService()
        
        # Note: EmployeeVerificationService doesn't have _base_url or _api_key
        # It uses local database cache instead of direct Ragic API calls
        assert service._field_config is not None

    def test_field_config_loaded(self, mock_env_vars):
        """Test field configuration is loaded."""
        from core.services.ragic import EmployeeVerificationService
        
        service = EmployeeVerificationService()
        
        assert service._field_config is not None
        assert service._field_config.email_id is not None


class TestCoreRagicServiceFieldMatching:
    """Tests for field value extraction and fuzzy matching."""

    @pytest.fixture
    def ragic_service(self, mock_env_vars):
        """Create EmployeeVerificationService instance."""
        from core.services.ragic import EmployeeVerificationService
        return EmployeeVerificationService()

    def test_get_field_value_exact_match(self, ragic_service):
        """Test exact field ID matching."""
        record = {"1005977": "test@example.com", "1005975": "Test User"}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value == "test@example.com"

    def test_get_field_value_underscore_prefix(self, ragic_service):
        """Test field ID with underscore prefix."""
        record = {"_1005977": "test@example.com"}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value == "test@example.com"

    def test_get_field_value_fuzzy_match(self, ragic_service):
        """Test fuzzy name matching for Chinese field names."""
        record = {"E-mail": "test@example.com"}
        fuzzy_names = ["E-mail", "?��??�件", "email"]
        
        value = ragic_service._get_field_value(record, "nonexistent", fuzzy_names)
        
        assert value == "test@example.com"

    def test_get_field_value_strips_whitespace(self, ragic_service):
        """Test that returned values are stripped."""
        record = {"1005977": "  test@example.com  "}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value == "test@example.com"

    def test_get_field_value_returns_none_for_empty(self, ragic_service):
        """Test empty string returns None."""
        record = {"1005977": ""}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value is None

    def test_fuzzy_match_threshold(self, ragic_service):
        """Test fuzzy matching with threshold."""
        assert ragic_service._fuzzy_match("email", "Email", 0.8) is True
        assert ragic_service._fuzzy_match("E-mail", "email", 0.8) is True
        assert ragic_service._fuzzy_match("totally_different", "email", 0.8) is False


class TestCoreRagicServiceEmployeeVerification:
    """Tests for employee verification methods."""

    @pytest.fixture
    def ragic_service(self, mock_env_vars):
        """Create EmployeeVerificationService instance."""
        from core.services.ragic import EmployeeVerificationService
        return EmployeeVerificationService()

    @pytest.mark.asyncio
    async def test_verify_email_exists_found(
        self, ragic_service, mock_async_db_session
    ):
        """Test email verification when employee exists in local DB."""
        from modules.administrative.models.account import AdministrativeAccount
        
        account = MagicMock(spec=AdministrativeAccount)
        account.ragic_id = 1
        account.account_id = "acc1"
        account.name = "Alice Chen"
        account.emails = "alice@example.com"
        account.employee_id = "E001"
        account.status = True
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [account]
        mock_async_db_session.execute.return_value = mock_result
        
        with patch('core.services.ragic.get_standalone_session', return_value=mock_async_db_session):
            result = await ragic_service.verify_email_exists("alice@example.com")
        
        assert result is not None
        assert result.email == "alice@example.com"
        assert result.name == "Alice Chen"

    @pytest.mark.asyncio
    async def test_verify_email_exists_not_found(
        self, ragic_service, mock_async_db_session
    ):
        """Test email verification when employee does not exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_async_db_session.execute.return_value = mock_result
        
        with patch('core.services.ragic.get_standalone_session', return_value=mock_async_db_session):
            result = await ragic_service.verify_email_exists("nonexistent@example.com")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_email_case_insensitive(
        self, ragic_service, mock_async_db_session
    ):
        """Test email verification is case insensitive."""
        from modules.administrative.models.account import AdministrativeAccount
        
        account = MagicMock(spec=AdministrativeAccount)
        account.ragic_id = 1
        account.account_id = "acc1"
        account.name = "Alice Chen"
        account.emails = "ALICE@EXAMPLE.COM"
        account.employee_id = "E001"
        account.status = True
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [account]
        mock_async_db_session.execute.return_value = mock_result
        
        with patch('core.services.ragic.get_standalone_session', return_value=mock_async_db_session):
            result = await ragic_service.verify_email_exists("alice@example.com")
        
        assert result is not None
        assert result.email == "ALICE@EXAMPLE.COM"

    @pytest.mark.asyncio
    async def test_get_employee_by_id_found(
        self, ragic_service, mock_async_db_session
    ):
        """Test employee lookup by employee ID."""
        from modules.administrative.models.account import AdministrativeAccount
        
        account = MagicMock(spec=AdministrativeAccount)
        account.ragic_id = 1
        account.name = "User"
        account.emails = "test@example.com"
        account.employee_id = "E001"
        account.status = True
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_async_db_session.execute.return_value = mock_result
        
        with patch('core.services.ragic.get_standalone_session', return_value=mock_async_db_session):
            result = await ragic_service.get_employee_by_id("E001")
            
            assert result is not None
            assert result.employee_id == "E001"

    @pytest.mark.asyncio
    async def test_get_all_employees_success(self, ragic_service, mock_async_db_session):
        """Test fetching all employees from local DB."""
        from modules.administrative.models.account import AdministrativeAccount
        
        account1 = MagicMock(spec=AdministrativeAccount)
        account1.ragic_id = 1
        account1.emails = "test@example.com"
        
        account2 = MagicMock(spec=AdministrativeAccount)
        account2.ragic_id = 2
        account2.emails = "test2@example.com"
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [account1, account2]
        mock_async_db_session.execute.return_value = mock_result
        
        with patch('core.services.ragic.get_standalone_session', return_value=mock_async_db_session):
            result = await ragic_service.get_all_employees()
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_all_employees_api_error(self, ragic_service, mock_async_db_session):
        """Test handling of DB errors."""
        mock_async_db_session.execute.side_effect = Exception("DB connection failed")
        
        with patch('core.services.ragic.get_standalone_session', return_value=mock_async_db_session):
            # The current implementation might raise the exception or return empty
            # Checking implementation: it just executes query. It doesn't wrap in try-except block in get_all_employees (line 115)
            # So it should raise
             with pytest.raises(Exception, match="DB connection failed"):
                await ragic_service.get_all_employees()


class TestCoreRagicServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_employee_verification_service_returns_singleton(self, mock_env_vars):
        """Test singleton returns same instance."""
        import core.services.ragic as ragic_module
        ragic_module._verification_service = None
        
        from core.services.ragic import get_employee_verification_service
        
        service1 = get_employee_verification_service()
        service2 = get_employee_verification_service()
        
        assert service1 is service2
