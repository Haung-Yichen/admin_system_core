"""
Ragic HTTP Service.

Low-level HTTP client for Ragic API communication.
This is the unified service that replaces both:
- core/services/ragic.py (employee verification)
- services/ragic_service.py (generic CRUD)

Design Principles:
    RagicService requires httpx.AsyncClient via EXPLICIT dependency injection.
    It does NOT fetch clients from global state or thread-local storage.
    The HTTP client lifecycle is managed by the caller.
    
    Usage in FastAPI routes:
        @router.get("/data")
        async def get_data(ragic: RagicServiceDep):
            return await ragic.get_records("/forms/1")
    
    Usage in background tasks:
        from core.http_client import create_standalone_http_client
        
        async with create_standalone_http_client() as http_client:
            service = RagicService(http_client=http_client)
            await service.get_records("/forms/1")
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
        http_client: Shared httpx.AsyncClient (required).
        api_key: Ragic API key. If not provided, loads from config.
        base_url: Ragic base URL. If not provided, loads from config.
        timeout: HTTP request timeout in seconds (for per-request override).
    """
    
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        if http_client is None:
            raise ValueError(
                "http_client is required. Use dependency injection via RagicServiceDep "
                "in FastAPI routes, or create_standalone_http_client() for background tasks."
            )
        
        self._client = http_client
        self._timeout = timeout
        
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
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Ragic API requests."""
        return {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }
    
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return bool(self._api_key and self._base_url)
    
    async def check_connection(self) -> dict:
        """
        Check Ragic API connectivity for dashboard health monitoring.
        
        Performs a lightweight API call to verify:
        1. Network connectivity to Ragic servers
        2. API key validity
        3. Response latency
        
        Returns:
            dict: Health check result with structure:
                {
                    "status": "healthy" | "warning" | "error",
                    "message": "Description of the status",
                    "details": {
                        "Latency": "123ms",
                        "Base URL": "https://ap13.ragic.com",
                        "API Key": "****xxxx",
                    }
                }
        """
        import time
        
        if not self.is_configured():
            return {
                "status": "error",
                "message": "Not configured",
                "details": {
                    "Base URL": self._base_url or "Not set",
                    "API Key": "Not set",
                }
            }
        
        # Mask API key for display (show last 4 chars)
        masked_key = f"****{self._api_key[-4:]}" if len(self._api_key) > 4 else "****"
        
        try:
            start_time = time.time()
            client = self._client
            
            # Use a lightweight request - fetch API info or a small dataset
            # Ragic doesn't have a dedicated health endpoint, so we try to access the base
            response = await client.get(
                self._base_url,
                params={"api": ""},
                headers=self._get_headers(),
                timeout=10.0
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "Connected",
                    "details": {
                        "Latency": f"{latency_ms}ms",
                        "Base URL": self._base_url,
                        "API Key": masked_key,
                    }
                }
            elif response.status_code == 401:
                return {
                    "status": "error",
                    "message": "Authentication failed",
                    "details": {
                        "Latency": f"{latency_ms}ms",
                        "Base URL": self._base_url,
                        "API Key": masked_key,
                        "Error": "Invalid API Key",
                    }
                }
            else:
                return {
                    "status": "warning",
                    "message": f"HTTP {response.status_code}",
                    "details": {
                        "Latency": f"{latency_ms}ms",
                        "Base URL": self._base_url,
                        "API Key": masked_key,
                    }
                }
                
        except Exception as e:
            logger.error(f"Ragic health check failed: {e}")
            return {
                "status": "error",
                "message": "Connection failed",
                "details": {
                    "Base URL": self._base_url,
                    "API Key": masked_key,
                    "Error": str(e)[:50],
                }
            }
    
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
            client = self._client
            response = await client.get(url, params={"info": "1"}, headers=self._get_headers())
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
            client = self._client
            response = await client.get(full_url, params=query_params, headers=self._get_headers())
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
            client = self._client
            response = await client.get(url, params=params, headers=self._get_headers())
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
            client = self._client
            response = await client.get(url, params={"api": "", "naming": "EID"}, headers=self._get_headers())
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
            client = self._client
            response = await client.post(url, params={"api": ""}, json=data, headers=self._get_headers())
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
            client = self._client
            response = await client.post(url, params={"api": ""}, json=data, headers=self._get_headers())
            response.raise_for_status()
            
            logger.debug(f"Record {record_id} updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update record {record_id}: {e}")
            return False
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
            client = self._client
            response = await client.delete(url, params={"api": ""}, headers=self._get_headers())
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
            client = self._client
            response = await client.post(full_url, json=data, headers=self._get_headers())
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


def create_ragic_service(http_client: httpx.AsyncClient) -> RagicService:
    """
    Factory function to create RagicService with HTTP client.
    
    Args:
        http_client: HTTP client instance (REQUIRED).
                    For FastAPI routes, get from HttpClientDep.
                    For background tasks, use create_standalone_http_client().
    
    Returns:
        RagicService instance.
    
    Example:
        # In FastAPI route (dependency injection)
        @router.get("/data")
        async def get_data(http_client: HttpClientDep):
            service = create_ragic_service(http_client)
            return await service.get_records("/forms/1")
        
        # In background task (RAII pattern)
        from core.http_client import create_standalone_http_client
        
        async with create_standalone_http_client() as http_client:
            service = create_ragic_service(http_client)
            await service.sync_data()
    """
    return RagicService(http_client=http_client)

