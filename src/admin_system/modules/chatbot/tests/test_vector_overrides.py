
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
class TestVectorServiceOverrides:
    """Test functionality of keyword overrides in VectorService."""
    
    async def test_keyword_override(self):
        """Test that '制度' triggers override and fetches SOP-020."""
        from modules.chatbot.services.vector_service import VectorService
        from modules.chatbot.models import SOPDocument
        
        # Mock dependencies
        mock_settings = MagicMock()
        mock_settings.embedding_dimension = 384
        
        # We need to mock ConfigLoader since VectorService constructor uses it
        with pytest.MonkeyPatch.context() as m:
            # Mock ConfigLoader to avoid reading real config files
            MockConfigLoader = MagicMock()
            MockConfigLoader.return_value.get.return_value = {} # Return empty config
            m.setattr("core.app_context.ConfigLoader", MockConfigLoader)
            
            service = VectorService(settings=mock_settings)
            
            # Mock DB session
            mock_db = AsyncMock()
            mock_result = MagicMock()
            
            # Mock found document
            # Need datetime for schema validation
            from datetime import datetime
            now = datetime.now()
            
            mock_doc = SOPDocument(
                id="test-uuid",
                sop_id="SOP-020",
                title="制度說明",
                content="這是關於制度的說明內容",
                is_published=True,
                created_at=now,
                updated_at=now,
                metadata_={}  # Ensure metadata is present
            )
            mock_result.scalar_one_or_none.return_value = mock_doc
            mock_db.execute.return_value = mock_result
            
            # Execute search with keyword
            response = await service.search("制度", mock_db)
            
            # Verify
            assert len(response.results) == 1
            # SOPDocumentResponse schema doesn't export sop_id by default, verify title instead
            assert response.results[0].document.title == "制度說明"
            assert response.results[0].similarity_score == 1.0
            
            # Verify DB was queried for specific SOP ID
            # Extract the compiled query or check call arguments
            # Since we can't easily check the SQL string, we trust the result flow

    async def test_fuzzy_keyword_override(self):
        """Test that partial match triggers override (e.g. '請問公司制度' triggers '制度')."""
        from modules.chatbot.services.vector_service import VectorService
        from modules.chatbot.models import SOPDocument
        from datetime import datetime
        
        with pytest.MonkeyPatch.context() as m:
            MockConfigLoader = MagicMock()
            MockConfigLoader.return_value.get.return_value = {}
            m.setattr("core.app_context.ConfigLoader", MockConfigLoader)
            
            service = VectorService()
            mock_db = AsyncMock()
            mock_result = MagicMock()
            now = datetime.now()
            
            mock_doc = SOPDocument(
                id="test-uuid-2",
                sop_id="SOP-020",
                title="制度說明",
                content="...",
                is_published=True,
                created_at=now,
                updated_at=now,
                metadata_={}
            )
            mock_result.scalar_one_or_none.return_value = mock_doc
            mock_db.execute.return_value = mock_result
            
            # Execute search with sentence containing keyword
            response = await service.search("我想請問關於公司的制度說明", mock_db)
            
            # Verify it hit the override
            assert len(response.results) == 1
            assert response.results[0].document.title == "制度說明"
            assert response.results[0].similarity_score == 1.0

    async def test_keyword_override_not_found(self):
        """Test fallback when override target is missing."""
        from modules.chatbot.services.vector_service import VectorService
        
        with pytest.MonkeyPatch.context() as m:
            MockConfigLoader = MagicMock()
            MockConfigLoader.return_value.get.return_value = {} 
            m.setattr("core.app_context.ConfigLoader", MockConfigLoader)
            
            service = VectorService()
            
            # Mock DB returning None for SOP-020
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            
            # Mock vector search fallback
            service._execute_vector_search = AsyncMock(return_value=[])
            service.generate_embedding = MagicMock(return_value=[0.1]*384)
            
            # Execute search
            await service.search("制度", mock_db)
            
            # Verify fallback to vector search
            service._execute_vector_search.assert_called_once()
