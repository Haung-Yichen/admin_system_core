"""
Compliance Tests for Administrative Module.

Tests to verify:
1. PII fields are properly encrypted in the database
2. Blind index (primary_email_hash) enables exact-match lookups
3. AccountSyncService correctly computes primary_email_hash during sync
4. LeaveService._get_account_by_email uses hash-based lookup

These tests validate the security compliance updates per module-development.md.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from core.security import generate_blind_index, EncryptedType


# =============================================================================
# Test: primary_email_hash computation
# =============================================================================


class TestPrimaryEmailHashComputation:
    """Tests for blind index hash generation in AccountSyncService."""

    def test_compute_primary_email_hash_single_email(self):
        """Should hash the single email correctly."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        service = AccountSyncService()
        emails = "test@example.com"
        
        result = service._compute_primary_email_hash(emails)
        expected = generate_blind_index("test@example.com")
        
        assert result == expected
        assert len(result) == 64  # SHA256 hex is 64 chars

    def test_compute_primary_email_hash_multiple_emails(self):
        """Should only hash the first (primary) email."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        service = AccountSyncService()
        emails = "primary@example.com, secondary@example.com, third@example.com"
        
        result = service._compute_primary_email_hash(emails)
        expected = generate_blind_index("primary@example.com")
        
        assert result == expected

    def test_compute_primary_email_hash_with_whitespace(self):
        """Should strip whitespace and lowercase before hashing."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        service = AccountSyncService()
        
        # Different formats should produce the same hash
        hash1 = service._compute_primary_email_hash("  Test@Example.COM  ")
        hash2 = service._compute_primary_email_hash("test@example.com")
        hash3 = service._compute_primary_email_hash("TEST@EXAMPLE.COM, other@example.com")
        
        assert hash1 == hash2
        assert hash2 == hash3

    def test_compute_primary_email_hash_empty_string(self):
        """Should return None for empty string."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        service = AccountSyncService()
        
        assert service._compute_primary_email_hash("") is None
        assert service._compute_primary_email_hash(None) is None

    def test_compute_primary_email_hash_whitespace_only(self):
        """Should return None for whitespace-only emails."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        service = AccountSyncService()
        
        # Just whitespace after split
        assert service._compute_primary_email_hash("   ") is None


# =============================================================================
# Test: map_record_to_dict includes primary_email_hash
# =============================================================================


class TestAccountSyncMapRecordToDict:
    """Tests for AccountSyncService.map_record_to_dict with blind index."""

    @pytest.fixture
    def sample_ragic_record(self):
        """Sample Ragic record with email data."""
        return {
            "_ragicId": 12345,
            "1005971": "12345",      # RAGIC_ID
            "1005972": "ACC001",     # ACCOUNT_ID
            "1005975": "Test User",  # NAME
            "1005974": "1",          # STATUS
            "1005977": "user@company.com, backup@company.com",  # EMAILS
            "1005986": "02-1234-5678",  # PHONES
            "1005987": "0912-345-678",  # MOBILES
        }

    @pytest.mark.asyncio
    async def test_map_record_includes_primary_email_hash(self, sample_ragic_record):
        """map_record_to_dict should include computed primary_email_hash."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        with patch("modules.administrative.services.account_sync.get_ragic_registry") as mock_registry:
            # Mock registry to return field IDs
            mock_reg = MagicMock()
            mock_reg.get_field_id.side_effect = lambda form, name: {
                "RAGIC_ID": "1005971",
                "ACCOUNT_ID": "1005972",
                "NAME": "1005975",
                "STATUS": "1005974",
                "EMAILS": "1005977",
                "PHONES": "1005986",
                "MOBILES": "1005987",
            }.get(name, "")
            mock_registry.return_value = mock_reg
            
            service = AccountSyncService()
            result = await service.map_record_to_dict(sample_ragic_record)
        
        assert result is not None
        assert "primary_email_hash" in result
        
        # Verify hash matches expected value
        expected_hash = generate_blind_index("user@company.com")
        assert result["primary_email_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_map_record_no_emails(self):
        """map_record_to_dict should set primary_email_hash to None when no emails."""
        from modules.administrative.services.account_sync import AccountSyncService
        
        record = {
            "_ragicId": 99999,
            "1005971": "99999",
            "1005972": "ACC999",
            "1005975": "No Email User",
            "1005974": "1",
            "1005977": "",  # Empty emails
        }
        
        with patch("modules.administrative.services.account_sync.get_ragic_registry") as mock_registry:
            mock_reg = MagicMock()
            mock_reg.get_field_id.side_effect = lambda form, name: {
                "RAGIC_ID": "1005971",
                "ACCOUNT_ID": "1005972",
                "NAME": "1005975",
                "STATUS": "1005974",
                "EMAILS": "1005977",
            }.get(name, "")
            mock_registry.return_value = mock_reg
            
            service = AccountSyncService()
            result = await service.map_record_to_dict(record)
        
        assert result is not None
        assert result.get("primary_email_hash") is None


# =============================================================================
# Test: LeaveService._get_account_by_email uses hash lookup
# =============================================================================


class TestLeaveServiceEmailLookup:
    """Tests for LeaveService email lookup using blind index."""

    @pytest.fixture
    def mock_account(self):
        """Create a mock AdministrativeAccount."""
        account = MagicMock()
        account.ragic_id = 12345
        account.account_id = "ACC001"
        account.name = "Test Employee"
        account.emails = "test@company.com, backup@company.com"
        account.primary_email_hash = generate_blind_index("test@company.com")
        account.status = True
        return account

    @pytest.mark.asyncio
    async def test_get_account_by_email_uses_hash(self, mock_account, mock_admin_settings):
        """Should use primary_email_hash for exact match lookup."""
        from modules.administrative.services.leave import LeaveService
        from modules.administrative.models import AdministrativeAccount
        
        # Setup mock db session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute.return_value = mock_result
        
        service = LeaveService(settings=mock_admin_settings)
        
        # Call with the email
        result = await service._get_account_by_email("test@company.com", mock_db)
        
        # Verify the query was made
        mock_db.execute.assert_called_once()
        
        # Verify result
        assert result == mock_account

    @pytest.mark.asyncio
    async def test_get_account_by_email_case_insensitive(self, mock_account, mock_admin_settings):
        """Email lookup should be case-insensitive via hash."""
        from modules.administrative.services.leave import LeaveService
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute.return_value = mock_result
        
        service = LeaveService(settings=mock_admin_settings)
        
        # Different case should find the same account
        result = await service._get_account_by_email("TEST@COMPANY.COM", mock_db)
        
        assert result == mock_account

    @pytest.mark.asyncio
    async def test_get_account_by_email_not_found(self, mock_admin_settings):
        """Should raise EmployeeNotFoundError when not found."""
        from modules.administrative.services.leave import LeaveService, EmployeeNotFoundError
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        service = LeaveService(settings=mock_admin_settings)
        
        with pytest.raises(EmployeeNotFoundError) as exc_info:
            await service._get_account_by_email("unknown@example.com", mock_db)
        
        assert "unknown@example.com" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_account_by_email_strips_whitespace(self, mock_account, mock_admin_settings):
        """Email lookup should strip whitespace."""
        from modules.administrative.services.leave import LeaveService
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute.return_value = mock_result
        
        service = LeaveService(settings=mock_admin_settings)
        
        # Whitespace should be stripped
        result = await service._get_account_by_email("  test@company.com  ", mock_db)
        
        assert result == mock_account


# =============================================================================
# Test: AdministrativeAccount model has encrypted fields
# =============================================================================


class TestAdministrativeAccountEncryption:
    """Tests to verify AdministrativeAccount uses EncryptedType for PII."""

    def test_model_has_encrypted_id_card_number(self):
        """id_card_number should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["id_card_number"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_emails(self):
        """emails should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["emails"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_phones(self):
        """phones should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["phones"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_mobiles(self):
        """mobiles should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["mobiles"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_household_address(self):
        """household_address should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["household_address"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_mailing_address(self):
        """mailing_address should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["mailing_address"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_emergency_contact(self):
        """emergency_contact should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["emergency_contact"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_encrypted_emergency_phone(self):
        """emergency_phone should use EncryptedType."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["emergency_phone"]
        assert isinstance(column.type, EncryptedType)

    def test_model_has_primary_email_hash_index(self):
        """primary_email_hash should be indexed for efficient lookup."""
        from modules.administrative.models import AdministrativeAccount
        
        column = AdministrativeAccount.__table__.columns["primary_email_hash"]
        assert column.index is True


# =============================================================================
# Test: Schemas are properly defined
# =============================================================================


class TestLeaveSchemas:
    """Tests to verify schemas are properly defined and importable."""

    def test_schemas_importable_from_module(self):
        """All schemas should be importable from schemas module."""
        from modules.administrative.schemas import (
            ErrorResponse,
            LeaveInitRequest,
            LeaveInitResponse,
            LeaveSubmitRequest,
            LeaveSubmitResponse,
            LeaveTypeOption,
            LeaveTypesResponse,
            WorkdayItem,
            WorkdaysRequest,
            WorkdaysResponse,
        )
        
        # Verify they are Pydantic models
        from pydantic import BaseModel
        
        assert issubclass(LeaveTypeOption, BaseModel)
        assert issubclass(LeaveTypesResponse, BaseModel)
        assert issubclass(LeaveInitResponse, BaseModel)
        assert issubclass(LeaveInitRequest, BaseModel)
        assert issubclass(LeaveSubmitRequest, BaseModel)
        assert issubclass(LeaveSubmitResponse, BaseModel)
        assert issubclass(WorkdayItem, BaseModel)
        assert issubclass(WorkdaysRequest, BaseModel)
        assert issubclass(WorkdaysResponse, BaseModel)
        assert issubclass(ErrorResponse, BaseModel)

    def test_leave_init_response_fields(self):
        """LeaveInitResponse should have required fields."""
        from modules.administrative.schemas import LeaveInitResponse
        
        # Create instance to verify fields
        response = LeaveInitResponse(
            name="Test User",
            email="test@example.com",
            sales_dept="Sales",
            sales_dept_manager="Manager",
            direct_supervisor="Supervisor",
        )
        
        assert response.name == "Test User"
        assert response.email == "test@example.com"
        assert response.sales_dept == "Sales"

    def test_leave_submit_request_validation(self):
        """LeaveSubmitRequest should validate input."""
        from modules.administrative.schemas import LeaveSubmitRequest
        from pydantic import ValidationError
        
        # Valid request
        request = LeaveSubmitRequest(
            leave_dates=["2026-02-02", "2026-02-03"],
            reason="Personal matters",
            leave_type="特休",
        )
        assert len(request.leave_dates) == 2
        
        # Invalid: empty reason
        with pytest.raises(ValidationError):
            LeaveSubmitRequest(
                leave_dates=["2026-02-02"],
                reason="",
                leave_type="特休",
            )
