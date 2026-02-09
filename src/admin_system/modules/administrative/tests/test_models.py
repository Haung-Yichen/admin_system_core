"""
Unit Tests for Administrative Models.

Tests for AdministrativeAccount SQLAlchemy model.
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch, AsyncMock

from modules.administrative.models.account import AdministrativeAccount


class TestAdministrativeAccountModel:
    """Tests for AdministrativeAccount model."""

    def test_tablename(self):
        """Test table name is correct."""
        assert AdministrativeAccount.__tablename__ == "administrative_accounts"

    def test_required_fields(self):
        """Test required fields exist."""
        columns = AdministrativeAccount.__table__.columns

        # Primary identification
        assert "ragic_id" in columns
        assert "account_id" in columns
        assert "name" in columns
        assert "status" in columns
        
        # Contact info
        assert "emails" in columns
        assert "phones" in columns
        assert "mobiles" in columns
        
        # Organization
        assert "org_code" in columns
        assert "org_name" in columns
        assert "rank_code" in columns
        
        # Dates
        assert "approval_date" in columns
        assert "resignation_date" in columns

    def test_primary_key(self):
        """Test ragic_id is primary key."""
        pk = AdministrativeAccount.__table__.primary_key
        assert len(pk.columns) == 1
        assert pk.columns.keys()[0] == "ragic_id"

    def test_repr(self):
        """Test string representation."""
        account = AdministrativeAccount(
            ragic_id=12345,
            account_id="A001",
            name="Test User",
            status=True
        )

        repr_str = repr(account)
        assert "12345" in repr_str
        assert "A001" in repr_str
        assert "Test User" in repr_str
        assert "Active" in repr_str

    def test_repr_disabled(self):
        """Test string representation for disabled account."""
        account = AdministrativeAccount(
            ragic_id=12345,
            account_id="A001",
            name="Test User",
            status=False
        )

        repr_str = repr(account)
        assert "Disabled" in repr_str

    def test_nullable_fields(self):
        """Test nullable fields."""
        columns = AdministrativeAccount.__table__.columns

        # These should be nullable
        assert columns["id_card_number"].nullable is True
        assert columns["employee_id"].nullable is True
        assert columns["org_code"].nullable is True
        assert columns["org_name"].nullable is True
        assert columns["emails"].nullable is True
        assert columns["phones"].nullable is True
        assert columns["resignation_date"].nullable is True

        # These should NOT be nullable
        assert columns["ragic_id"].nullable is False
        assert columns["account_id"].nullable is False
        assert columns["name"].nullable is False
        assert columns["status"].nullable is False

    def test_indexed_fields(self):
        """Test indexed fields."""
        columns = AdministrativeAccount.__table__.columns

        # These should be indexed for performance
        assert columns["account_id"].index is True
        assert columns["name"].index is True
        assert columns["status"].index is True
        assert columns["org_code"].index is True
        assert columns["rank_code"].index is True

    def test_unique_account_id(self):
        """Test account_id has unique constraint."""
        columns = AdministrativeAccount.__table__.columns
        assert columns["account_id"].unique is True


class TestAccountProperties:
    """Tests for AdministrativeAccount computed properties."""

    def test_is_active_true(self):
        """Test is_active returns True for active account without resignation."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            resignation_date=None
        )
        assert account.is_active is True

    def test_is_active_false_status(self):
        """Test is_active returns False when status is False."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=False,
            resignation_date=None
        )
        assert account.is_active is False

    def test_is_active_false_resigned(self):
        """Test is_active returns False when resigned."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            resignation_date=date(2024, 1, 1)
        )
        assert account.is_active is False

    def test_primary_email_single(self):
        """Test primary_email with single email."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            emails="test@example.com"
        )
        assert account.primary_email == "test@example.com"

    def test_primary_email_multiple(self):
        """Test primary_email with comma-separated emails."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            emails="primary@example.com, secondary@example.com"
        )
        assert account.primary_email == "primary@example.com"

    def test_primary_email_none(self):
        """Test primary_email returns None when empty."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            emails=None
        )
        assert account.primary_email is None

    def test_primary_phone(self):
        """Test primary_phone with comma-separated phones."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            phones="02-12345678, 03-87654321"
        )
        assert account.primary_phone == "02-12345678"

    def test_primary_mobile(self):
        """Test primary_mobile with comma-separated mobiles."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            mobiles="0912-345678, 0923-456789"
        )
        assert account.primary_mobile == "0912-345678"


class TestTimestampMixin:
    """Tests for TimestampMixin inheritance."""

    def test_account_has_timestamp_fields(self):
        """Test account model has timestamp fields from mixin."""
        columns = AdministrativeAccount.__table__.columns

        # TimestampMixin adds created_at and updated_at
        assert "created_at" in columns
        assert "updated_at" in columns


class TestModelInstantiation:
    """Tests for model object creation."""

    def test_create_account_minimal(self):
        """Test creating account with minimal fields."""
        account = AdministrativeAccount(
            ragic_id=123,
            account_id="A001",
            name="Test User",
            status=True
        )

        assert account.ragic_id == 123
        assert account.account_id == "A001"
        assert account.name == "Test User"
        assert account.status is True
        assert account.emails is None
        assert account.org_code is None

    def test_create_account_full(self):
        """Test creating account with many fields."""
        account = AdministrativeAccount(
            ragic_id=123,
            account_id="A001",
            name="Test User",
            status=True,
            id_card_number="A123456789",
            employee_id="E001",
            gender="男",
            birthday=date(1990, 1, 15),
            emails="test@example.com, test2@example.com",
            phones="02-12345678",
            mobiles="0912-345678",
            org_code="ORG001",
            org_name="總公司",
            rank_code="R01",
            rank_name="經理",
            approval_date=date(2020, 1, 1),
            effective_date=date(2020, 1, 15),
            assessment_rate=0.8,
            bank_name="中國信託",
            bank_branch_code="0001",
            bank_account="1234567890",
        )

        assert account.ragic_id == 123
        assert account.account_id == "A001"
        assert account.name == "Test User"
        assert account.id_card_number == "A123456789"
        assert account.employee_id == "E001"
        assert account.gender == "男"
        assert account.birthday == date(1990, 1, 15)
        assert account.primary_email == "test@example.com"
        assert account.org_code == "ORG001"
        assert account.org_name == "總公司"
        assert account.rank_code == "R01"
        assert account.rank_name == "經理"
        assert account.assessment_rate == 0.8
        assert account.bank_name == "中國信託"

    def test_license_fields(self):
        """Test license-related fields."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            life_license_number="L12345",
            life_registration_date=date(2020, 1, 1),
            property_license_number="P12345",
            property_registration_date=date(2020, 6, 1),
            ah_license_number="AH12345",
            investment_registration_date=date(2021, 1, 1),
        )

        assert account.life_license_number == "L12345"
        assert account.life_registration_date == date(2020, 1, 1)
        assert account.property_license_number == "P12345"
        assert account.ah_license_number == "AH12345"
        assert account.investment_registration_date == date(2021, 1, 1)

    def test_qualification_fields(self):
        """Test qualification-related fields."""
        account = AdministrativeAccount(
            ragic_id=1,
            account_id="A001",
            name="Test",
            status=True,
            traditional_annuity_qualification=True,
            variable_annuity_qualification=True,
            structured_bond_qualification=False,
            app_enabled=True,
        )

        assert account.traditional_annuity_qualification is True
        assert account.variable_annuity_qualification is True
        assert account.structured_bond_qualification is False
        assert account.app_enabled is True
