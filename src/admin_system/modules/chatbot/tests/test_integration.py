"""
Integration Tests for Chatbot Module.

Tests actual connectivity to external services:
1. Database (PostgreSQL with pgvector)
2. Ragic API (Employee data)
3. LINE API (Messaging)
4. Vector search functionality

Run with: pytest modules/chatbot/tests/test_integration.py -v -s
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure pytest-asyncio to use function-scoped event loop
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_db_session_state():
    """Reset the global DB session state before each test to avoid stale connections."""
    # Reset before test
    import core.database.engine as engine_module
    import core.database.session as session_module
    engine_module._engine = None
    session_module._async_session_factory = None
    yield
    # Optional: cleanup after test (not strictly necessary for tests)


class TestDatabaseConnectivity:
    """Test database connection and basic operations."""

    @pytest.mark.asyncio
    async def test_database_connection(self):
        """DB-01: Verify database connection works."""
        from core.database import get_standalone_session
        from sqlalchemy import text

        async with get_standalone_session() as session:
            # Execute a simple query
            result = await session.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            assert row is not None
            assert row.test == 1
            print("[PASS] Database connection successful")

    @pytest.mark.asyncio
    async def test_database_can_read_tables(self):
        """DB-02: Verify SOP documents table is readable."""
        from core.database import get_standalone_session
        from modules.chatbot.models import SOPDocument
        from sqlalchemy import select, func

        async with get_standalone_session() as session:
            # Count SOP documents
            result = await session.execute(
                select(func.count()).select_from(SOPDocument)
            )
            count = result.scalar()
            print(f"[PASS] SOP Documents count: {count}")
            assert count is not None  # Just verify query works

    @pytest.mark.asyncio
    async def test_database_can_read_users(self):
        """DB-03: Verify users table is readable."""
        from core.database import get_standalone_session
        from modules.chatbot.models import User
        from sqlalchemy import select, func

        async with get_standalone_session() as session:
            result = await session.execute(select(func.count()).select_from(User))
            count = result.scalar()
            print(f"[PASS] Users count: {count}")
            assert count is not None


class TestRagicAPIConnectivity:
    """Test Ragic API connectivity and employee data retrieval."""

    @pytest.mark.asyncio
    async def test_ragic_get_all_employees(self):
        """
        RAGIC-01: Verify Ragic API can read /HSIBAdmSys/-3/4 employee sheet.
        Expects: 150+ employee records.
        """
        from core.services.ragic import get_employee_verification_service

        service = get_employee_verification_service()
        employees = await service.get_all_employees()

        print(f"")
        print(f"[INFO] Ragic Employee Data:")
        print(f"       Total employees fetched: {len(employees)}")

        # Verify we have 150+ employees
        assert len(employees) >= 150, (
            f"Expected 150+ employees, got {len(employees)}. "
            "Check Ragic API connection and sheet path."
        )

        # Print sample employee for verification
        if employees:
            sample = employees[0]
            print(f"       Sample record keys: {list(sample.keys())[:5]}...")
            print("[PASS] Ragic API connectivity verified - 150+ employees found")

    @pytest.mark.asyncio
    async def test_ragic_field_parsing(self):
        """RAGIC-02: Verify Ragic field parsing (email, name, door_access_id)."""
        from core.services.ragic import get_employee_verification_service

        service = get_employee_verification_service()
        employees = await service.get_all_employees()

        if not employees:
            pytest.skip("No employees found in Ragic")

        # Check that we can parse at least one employee properly
        parsed_count = 0
        for record in employees[:10]:  # Check first 10
            # Retrieve fields directly from the dictionary (already parsed by service)
            email = record.get("emails", "")
            name = record.get("name", "Unknown")
            
            if email or name != "Unknown":
                parsed_count += 1

        print(f"[PASS] Successfully verified {parsed_count}/10 employee records")
        assert parsed_count > 0, "Could not verify any employee records"


class TestLineAPIConnectivity:
    """Test LINE API connectivity."""

    def test_line_service_is_configured(self):
        """LINE-01: Verify LINE Bot credentials are configured."""
        from modules.chatbot.services.line_service import get_line_service

        service = get_line_service()
        is_configured = service.is_configured()

        print(f"")
        print(f"[INFO] LINE API Configuration:")
        print(f"       Credentials configured: {is_configured}")

        assert is_configured, (
            "LINE Bot credentials not configured. "
            "Check SOP_BOT_LINE_CHANNEL_SECRET and SOP_BOT_LINE_CHANNEL_ACCESS_TOKEN"
        )
        print("[PASS] LINE API credentials verified")

    @pytest.mark.asyncio
    async def test_line_api_get_bot_info(self):
        """
        LINE-02: Verify LINE API connectivity.
        Tests by calling LINE API to get Bot info.
        """
        import httpx
        from modules.chatbot.core.config import get_chatbot_settings

        settings = get_chatbot_settings()
        access_token = settings.line_channel_access_token.get_secret_value()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.line.me/v2/bot/info",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            print(f"")
            print(f"[INFO] LINE Bot Info API Response:")
            print(f"       Status code: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                print(f"       Bot name: {data.get('displayName', 'N/A')}")
                print(f"       Bot ID: {data.get('userId', 'N/A')}")
                print("[PASS] LINE API connectivity verified")
            else:
                print(f"       Error: {resp.text}")

            assert resp.status_code == 200, (
                f"LINE API returned {resp.status_code}. "
                "Check access token validity."
            )


class TestVectorSearchFunctionality:
    """Test vector embedding and search functionality."""

    @pytest.mark.asyncio
    async def test_vector_service_initialization(self):
        """VECTOR-01: Verify vector service can initialize."""
        from modules.chatbot.services.vector_service import get_vector_service

        service = get_vector_service()
        assert service is not None
        print("[PASS] Vector service initialized")

    @pytest.mark.asyncio
    async def test_embedding_generation(self):
        """VECTOR-02: Verify embedding generation works."""
        from modules.chatbot.services.vector_service import get_vector_service

        service = get_vector_service()

        test_text = "This is a test document for embedding verification"
        embedding = service.generate_embedding(test_text)

        print(f"")
        print(f"[INFO] Embedding Generation:")
        print(f"       Input text length: {len(test_text)}")
        print(f"       Embedding dimension: {len(embedding)}")
        print(f"       First 5 values: {embedding[:5]}")

        # Verify embedding dimension
        assert len(embedding) > 0, "Embedding should not be empty"
        assert all(isinstance(v, (float, int)) for v in embedding)
        print("[PASS] Embedding generation verified")

    @pytest.mark.asyncio
    async def test_vector_search(self):
        """VECTOR-03: Verify vector search works (requires DB with SOP docs)."""
        from modules.chatbot.services.vector_service import get_vector_service
        from core.database import get_standalone_session

        service = get_vector_service()

        async with get_standalone_session() as session:
            # Search for a general term
            results = await service.search(
                query="SOP procedure",
                db=session,
                top_k=5,
            )

            print(f"")
            print(f"[INFO] Vector Search Results:")
            print(f"       Query: 'SOP procedure'")
            print(f"       Results found: {len(results.results)}")
            print(f"       Search time: {results.search_time_ms:.2f}ms")

            for i, result in enumerate(results.results, 1):
                # SearchResult contains document object, title is inside document
                print(f"       [{i}] {result.document.title} (score: {result.similarity_score:.3f})")

            # Just verify search works, even if no results
            assert results is not None
            print("[PASS] Vector search functionality verified")


class TestEndToEndIntegration:
    """End-to-end integration tests combining multiple services."""

    @pytest.mark.asyncio
    async def test_full_service_stack(self):
        """E2E-01: Integration test - verify all services work together."""
        from core.services import RagicService
        from modules.chatbot.services import (
            LineService,
            VectorService,
        )
        from core.database import get_standalone_session

        print("")
        print("[INFO] Full Service Stack Test:")

        # 1. Database
        async with get_standalone_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.fetchone() is not None
            print("       [OK] Database: Connected")

        # 2. Ragic
        ragic = RagicService()
        employees = await ragic.get_all_employees()
        print(f"       [OK] Ragic: {len(employees)} employees loaded")

        # 3. LINE
        line = LineService()
        print(f"       [OK] LINE: Configured = {line.is_configured()}")

        # 4. Vector
        vector = VectorService()
        emb = vector.generate_embedding("test")
        print(f"       [OK] Vector: Embedding dim = {len(emb)}")

        print("")
        print("[PASS] All services operational!")


# Allow running with: python -m pytest ... or directly
if __name__ == "__main__":
    print("=" * 60)
    print("Chatbot Module Integration Tests")
    print("=" * 60)

    # Run with asyncio for async tests
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
    ])
