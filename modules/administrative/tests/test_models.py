"""
Unit Tests for Administrative Models.

Tests for AdministrativeEmployee and AdministrativeDepartment SQLAlchemy models.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from modules.administrative.models.employee import AdministrativeEmployee
from modules.administrative.models.department import AdministrativeDepartment


class TestAdministrativeEmployeeModel:
    """Tests for AdministrativeEmployee model."""

    def test_tablename(self):
        """Test table name is correct."""
        assert AdministrativeEmployee.__tablename__ == "administrative_employee"

    def test_required_fields(self):
        """Test required fields exist."""
        columns = AdministrativeEmployee.__table__.columns

        assert "email" in columns
        assert "name" in columns
        assert "department_name" in columns
        assert "supervisor_email" in columns
        assert "ragic_id" in columns

    def test_primary_key(self):
        """Test email is primary key."""
        pk = AdministrativeEmployee.__table__.primary_key
        assert len(pk.columns) == 1
        assert pk.columns.keys()[0] == "email"

    def test_repr(self):
        """Test string representation."""
        employee = AdministrativeEmployee(
            email="test@example.com",
            name="Test User",
            ragic_id=1
        )

        repr_str = repr(employee)
        assert "test@example.com" in repr_str
        assert "Test User" in repr_str

    def test_nullable_fields(self):
        """Test nullable fields."""
        columns = AdministrativeEmployee.__table__.columns

        # department_name and supervisor_email should be nullable
        assert columns["department_name"].nullable is True
        assert columns["supervisor_email"].nullable is True

        # email and name should not be nullable
        assert columns["email"].nullable is False
        assert columns["name"].nullable is False

    def test_indexed_fields(self):
        """Test indexed fields."""
        columns = AdministrativeEmployee.__table__.columns

        # department_name and ragic_id should be indexed
        assert columns["department_name"].index is True
        assert columns["ragic_id"].index is True

    def test_ragic_id_unique(self):
        """Test ragic_id has unique constraint."""
        columns = AdministrativeEmployee.__table__.columns
        assert columns["ragic_id"].unique is True


class TestAdministrativeDepartmentModel:
    """Tests for AdministrativeDepartment model."""

    def test_tablename(self):
        """Test table name is correct."""
        assert AdministrativeDepartment.__tablename__ == "administrative_department"

    def test_required_fields(self):
        """Test required fields exist."""
        columns = AdministrativeDepartment.__table__.columns

        assert "name" in columns
        assert "manager_email" in columns
        assert "ragic_id" in columns

    def test_primary_key(self):
        """Test name is primary key."""
        pk = AdministrativeDepartment.__table__.primary_key
        assert len(pk.columns) == 1
        assert pk.columns.keys()[0] == "name"

    def test_repr(self):
        """Test string representation."""
        department = AdministrativeDepartment(
            name="Engineering",
            manager_email="manager@example.com",
            ragic_id=1
        )

        repr_str = repr(department)
        assert "Engineering" in repr_str
        assert "manager@example.com" in repr_str

    def test_nullable_fields(self):
        """Test nullable fields."""
        columns = AdministrativeDepartment.__table__.columns

        # manager_email should be nullable
        assert columns["manager_email"].nullable is True

        # name should not be nullable
        assert columns["name"].nullable is False

    def test_ragic_id_unique_and_indexed(self):
        """Test ragic_id has unique and index constraint."""
        columns = AdministrativeDepartment.__table__.columns
        assert columns["ragic_id"].unique is True
        assert columns["ragic_id"].index is True


class TestTimestampMixin:
    """Tests for TimestampMixin inheritance."""

    def test_employee_has_timestamp_fields(self):
        """Test employee model has timestamp fields from mixin."""
        columns = AdministrativeEmployee.__table__.columns

        # TimestampMixin adds created_at and updated_at
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_department_has_timestamp_fields(self):
        """Test department model has timestamp fields from mixin."""
        columns = AdministrativeDepartment.__table__.columns

        assert "created_at" in columns
        assert "updated_at" in columns


class TestModelInstantiation:
    """Tests for model object creation."""

    def test_create_employee_minimal(self):
        """Test creating employee with minimal fields."""
        employee = AdministrativeEmployee(
            email="test@example.com",
            name="Test User",
            ragic_id=123
        )

        assert employee.email == "test@example.com"
        assert employee.name == "Test User"
        assert employee.ragic_id == 123
        assert employee.department_name is None
        assert employee.supervisor_email is None

    def test_create_employee_full(self):
        """Test creating employee with all fields."""
        employee = AdministrativeEmployee(
            email="test@example.com",
            name="Test User",
            department_name="Engineering",
            supervisor_email="manager@example.com",
            ragic_id=123
        )

        assert employee.email == "test@example.com"
        assert employee.name == "Test User"
        assert employee.department_name == "Engineering"
        assert employee.supervisor_email == "manager@example.com"
        assert employee.ragic_id == 123

    def test_create_department_minimal(self):
        """Test creating department with minimal fields."""
        department = AdministrativeDepartment(
            name="Engineering",
            ragic_id=1
        )

        assert department.name == "Engineering"
        assert department.ragic_id == 1
        assert department.manager_email is None

    def test_create_department_full(self):
        """Test creating department with all fields."""
        department = AdministrativeDepartment(
            name="Engineering",
            manager_email="eng_manager@example.com",
            ragic_id=1
        )

        assert department.name == "Engineering"
        assert department.manager_email == "eng_manager@example.com"
        assert department.ragic_id == 1
