"""
Ragic HTTP Service.

Low-level HTTP client for Ragic API communication.
This is the unified service that replaces both:
- core/services/ragic.py (employee verification)
- services/ragic_service.py (generic CRUD)
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from core.app_context import ConfigLoader

logger = logging.getLogger(__name__)


class RagicService:
    """
    Unified Ragic API HTTP client.
    
    Provides low-level CRUD operations for any Ragic sheet.
    Higher-level operations should use RagicRepository.
    
    Args:
        api_key: Ragic API key. If not provided, loads from config.
        base_url: Ragic base URL. If not provided, loads from config.
        timeout: HTTP request timeout in seconds.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        # Load from config if not provided
        if not api_key or not base_url:
            config = ConfigLoader()
            config.load()
            ragic_config = config.get("ragic", {})
            
            self._api_key = api_key or ragic_config.get("api_key", "")
            self._base_url = (base_url or ragic_config.get("base_url", "https://ap13.ragic.com")).rstrip("/")
        else:
            self._api_key = api_key
            self._base_url = base_url.rstrip("/")
        
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Basic {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return bool(self._api_key and self._base_url)
    
    def _build_url(self, sheet_path: str, record_id: Optional[int] = None) -> str:
        """Build API URL for a sheet/record."""
        # Ensure sheet_path starts with /
        if not sheet_path.startswith("/"):
            sheet_path = f"/{sheet_path}"
        
        url = f"{self._base_url}{sheet_path}"
        if record_id:
            url = f"{url}/{record_id}"
        return url
    
    def _build_full_url(self, full_url: str, record_id: Optional[int] = None) -> str:
        """Build API URL from a full URL (for module-specific configs)."""
        if record_id:
            return f"{full_url}/{record_id}"
        return full_url
    
    # =========================================================================
    # Schema Introspection
    # =========================================================================
    
    async def get_form_schema(
        self,
        sheet_path: Optional[str] = None,
        full_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch form schema (field definitions) from Ragic.
        
        Ragic API: Append '?info=1' to get form schema instead of data.
        
        Args:
            sheet_path: Path to the sheet (e.g., "/forms/1").
            full_url: Full URL to the Ragic form (alternative to sheet_path).
        
        Returns:
            dict containing form field definitions.
            
        Raises:
            ValueError: If neither sheet_path nor full_url is provided.
            httpx.HTTPError: If API request fails.
        """
        if not sheet_path and not full_url:
            raise ValueError("Either sheet_path or full_url must be provided")
        
        if not self.is_configured() and not full_url:
            logger.warning("Ragic service not configured")
            return {}
        
        url = full_url if full_url else self._build_url(sheet_path)
        
        try:
            client = self._get_client()
            response = await client.get(url, params={"info": "1"})
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ragic schema API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch form schema from Ragic: {e}")
            raise
    
    async def get_records_by_url(
        self,
        full_url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch records from a Ragic form using full URL.
        
        This is useful for module-specific configurations where the full URL
        is stored in settings instead of just the sheet path.
        
        Args:
            full_url: Full URL to the Ragic form.
            params: Optional query parameters (e.g., {"naming": "EID"}).
        
        Returns:
            List of record dictionaries with '_ragicId' included.
        """
        if not self._api_key:
            logger.warning("Ragic API key not configured")
            return []
        
        query_params = params or {}
        
        try:
            client = self._get_client()
            response = await client.get(full_url, params=query_params)
            response.raise_for_status()
            
            data = response.json()
            
            # Ragic returns dict with record_id as keys
            if isinstance(data, dict):
                records = []
                for ragic_id, record in data.items():
                    if ragic_id == "_metaData":
                        continue  # Skip metadata
                    if isinstance(record, dict):
                        record["_ragicId"] = int(ragic_id)
                        records.append(record)
                return records
            return data if isinstance(data, list) else []
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ragic API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch records from Ragic: {e}")
            return []
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    async def get_records(
        self,
        sheet_path: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Fetch records from a Ragic sheet.
        
        Args:
            sheet_path: Path to the sheet (e.g., "/forms/1").
            filters: Optional filter criteria (field_id: value).
            limit: Maximum number of records.
            offset: Starting offset for pagination.
        
        Returns:
            List of record dictionaries.
        """
        if not self.is_configured():
            logger.warning("Ragic service not configured")
            return []
        
        url = self._build_url(sheet_path)
        params: Dict[str, Any] = {
            "api": "",
            "limit": limit,
            "offset": offset,
        }
        
        # Add filters as query params
        if filters:
            for field_id, value in filters.items():
                params[f"where_{field_id}"] = value
        
        try:
            client = self._get_client()
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Ragic returns dict with record_id as keys
            if isinstance(data, dict):
                return list(data.values())
            return data if isinstance(data, list) else []
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ragic API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch records from Ragic: {e}")
            return []
    
    async def get_record(
        self,
        sheet_path: str,
        record_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single record by ID.
        
        Args:
            sheet_path: Path to the sheet.
            record_id: The record ID.
        
        Returns:
            Record dictionary or None.
        """
        if not self.is_configured():
            return None
        
        url = self._build_url(sheet_path, record_id)
        
        try:
            client = self._get_client()
            response = await client.get(url, params={"api": ""})
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get record {record_id}: {e}")
            return None
    
    async def create_record(
        self,
        sheet_path: str,
        data: Dict[str, Any],
    ) -> Optional[int]:
        """
        Create a new record in a Ragic sheet.
        
        Args:
            sheet_path: Path to the sheet.
            data: Record data (field_id: value).
        
        Returns:
            New record ID or None on failure.
        """
        if not self.is_configured():
            return None
        
        url = self._build_url(sheet_path)
        
        try:
            client = self._get_client()
            response = await client.post(url, params={"api": ""}, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # Ragic returns the new record ID
            if isinstance(result, dict) and "_ragicId" in result:
                return result["_ragicId"]
            return None
            
        except Exception as e:
            logger.error(f"Failed to create record: {e}")
            return None
    
    async def update_record(
        self,
        sheet_path: str,
        record_id: int,
        data: Dict[str, Any],
    ) -> bool:
        """
        Update an existing record.
        
        Args:
            sheet_path: Path to the sheet.
            record_id: The record ID to update.
            data: Updated field data.
        
        Returns:
            True if successful.
        """
        if not self.is_configured():
            return False
        
        url = self._build_url(sheet_path, record_id)
        
        try:
            client = self._get_client()
            response = await client.post(url, params={"api": ""}, json=data)
            response.raise_for_status()
            
            logger.debug(f"Record {record_id} updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update record {record_id}: {e}")
            return False
    
    async def delete_record(
        self,
        sheet_path: str,
        record_id: int,
    ) -> bool:
        """
        Delete a record.
        
        Args:
            sheet_path: Path to the sheet.
            record_id: The record ID to delete.
        
        Returns:
            True if successful.
        """
        if not self.is_configured():
            return False
        
        url = self._build_url(sheet_path, record_id)
        
        try:
            client = self._get_client()
            response = await client.delete(url, params={"api": ""})
            response.raise_for_status()
            
            logger.debug(f"Record {record_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete record {record_id}: {e}")
            return False

    # =========================================================================
    # Full URL Operations (for module-specific configurations)
    # =========================================================================
    
    async def create_record_by_url(
        self,
        full_url: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new record using full URL.
        
        This is useful for module-specific configurations where the full URL
        is stored in settings instead of just the sheet path.
        
        Args:
            full_url: Full URL to the Ragic form.
            data: Record data (field_id: value).
        
        Returns:
            Response dict containing '_ragicId' or None on failure.
        """
        if not self._api_key:
            logger.warning("Ragic API key not configured")
            return None
        
        try:
            client = self._get_client()
            response = await client.post(full_url, json=data)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"Record created successfully: {result.get('_ragicId')}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ragic API error creating record: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create record: {e}")
            return None


# =============================================================================
# Singleton Access
# =============================================================================

_ragic_service: Optional[RagicService] = None


def get_ragic_service() -> RagicService:
    """
    Get singleton instance of RagicService.
    
    Returns:
        RagicService instance.
    """
    global _ragic_service
    if _ragic_service is None:
        _ragic_service = RagicService()
    return _ragic_service


def reset_ragic_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _ragic_service
    _ragic_service = None
