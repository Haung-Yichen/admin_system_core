
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import uuid
import logging

# Set up logging for the test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# We need to mock the imports that might cause issues (like SentenceTransformer or database connections)
# if they strictly require dependencies or config that isn't present in the test env.
# However, let's try to import the service directly first.
# If this fails, we will need to mock more aggressively.

try:
    from modules.chatbot.services.vector_service import VectorService
    from modules.chatbot.models import SOPDocument
    from modules.chatbot.schemas import SearchResponse
except ImportError as e:
    logger.error(f"Import failed: {e}")
    # Fallback/Mock classes for the purpose of verifying the logic structure if imports fail
    # This assumes the user wants verification of the logic I see in the file, even if I can't fully run it.
    raise e

@pytest.mark.asyncio
async def test_keyword_override():
    """
    Test that specific keywords trigger the override logic in VectorService.search
    """
    
    # Mock dependencies
    # 1. ConfigLoader
    # 2. get_chatbot_settings
    # 3. SentenceTransformer (heavy model loading)
    
    with patch('modules.chatbot.services.vector_service.ConfigLoader') as MockConfigLoader, \
         patch('modules.chatbot.services.vector_service.get_chatbot_settings'), \
         patch('modules.chatbot.services.vector_service.SentenceTransformer'):
        
        # Setup config mock
        mock_config_instance = MockConfigLoader.return_value
        mock_config_instance.get.return_value = {}  # Empty dict or minimal config
        
        # Initialize service
        service = VectorService()
        
        # Mock AsyncSession
        mock_db = AsyncMock()
        
        # Scenario 1: Target SOP found
        # ----------------------------
        # Function to generate a mock result that behaves like SQLAlchemy result
        def create_mock_result(doc):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = doc
            return mock_result

        # Simple Mock class to behave like the SQLAlchemy object but without overhead
        class MockSOPDocument:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        # Set up the document
        sop_020 = MockSOPDocument(
            id=str(uuid.uuid4()), # Response expects str, or UUID that converts to str. Use str to be safe.
            sop_id="SOP-020",
            title="Company Regulations",
            content="Details about company regulations and systems (制度).",
            is_published=True,
            metadata_={},
            tags=[],
            category="General",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        # Mocking db.execute to return our doc when queried
        mock_db.execute.return_value = create_mock_result(sop_020)
        
        # Test Query 1: Exact keyword "制度"
        query1 = "制度"
        logger.info(f"Testing query: {query1}")
        response1 = await service.search(query=query1, db=mock_db)
        
        assert len(response1.results) == 1
        assert response1.results[0].document.sop_id == "SOP-020"
        assert response1.results[0].similarity_score == 1.0
        logger.info("Test Query 1 Passed: Override triggered.")

        # Test Query 2: Fuzzy keyword "我想查詢制度" (Contains "制度")
        query2 = "我想查詢制度"
        logger.info(f"Testing query: {query2}")
        response2 = await service.search(query=query2, db=mock_db)
        
        assert len(response2.results) == 1
        assert response2.results[0].document.sop_id == "SOP-020"
        assert response2.results[0].similarity_score == 1.0
        logger.info("Test Query 2 Passed: Override triggered (fuzzy match).")

        # Test Query 3: Long keyword "制度查詢" (Should prioritize longer match if logic exists)
        # Note: In the code, KEYWORD_OVERRIDES were sorted by length reverse=True
        query3 = "請幫我做制度查詢"
        logger.info(f"Testing query: {query3}")
        response3 = await service.search(query=query3, db=mock_db)
        
        assert len(response3.results) == 1
        assert response3.results[0].document.sop_id == "SOP-020"
        logger.info("Test Query 3 Passed: Override triggered (long keyword).")
        
        # Scenario 2: No Override
        # -----------------------
        # Query that does not contain keywords
        query4 = "如何請假"
        
        # We need to mock _execute_vector_search since override won't trigger
        service._execute_vector_search = AsyncMock()
        service._execute_vector_search.return_value = [] # Return empty list for simplicity
        
        # Mock generate_embedding to avoid error
        service.generate_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])
        
        logger.info(f"Testing query: {query4}")
        response4 = await service.search(query=query4, db=mock_db)
        
        # Check that vector search was called
        service._execute_vector_search.assert_called_once()
        logger.info("Test Query 4 Passed: Normal search triggered.")
        
