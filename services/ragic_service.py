"""
Ragic Service - Ragic Database API integration.
Provides CRUD operations for Ragic sheets.
Documentation: https://www.ragic.com/intl/en/doc-api
"""
from typing import Any, Dict, List, Optional
import logging

import httpx

from core.app_context import ConfigLoader


class RagicService:
    """
    Service for interacting with Ragic Database API.
    """
    
    def __init__(self, config: ConfigLoader) -> None:
        self._config = config
        self._logger = logging.getLogger(__name__)
        
        self._api_key: str = config.get("ragic.api_key", "")
        self._base_url: str = config.get("ragic.base_url", "").rstrip("/")
        
        # HTTP client
        self._client = httpx.AsyncClient(
            timeout=30.0
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with API key."""
        return {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json"
        }
    
    def is_configured(self) -> bool:
        """Check if Ragic service is properly configured."""
        return bool(self._api_key and self._base_url)
    
    def _build_url(self, sheet_path: str, record_id: Optional[int] = None) -> str:
        """Build the API URL for a sheet/record."""
        url = f"{self._base_url}/{sheet_path}"
        if record_id:
            url = f"{url}/{record_id}"
        return url
    
    async def get_records(
        self, 
        sheet_path: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch records from a Ragic sheet.
        
        Args:
            sheet_path: Path to the sheet (e.g., "forms/1")
            filters: Optional filter criteria (field_id: value)
            limit: Maximum number of records
            offset: Starting offset for pagination
            
        Returns:
            List of record dictionaries
        """
        if not self.is_configured():
            self._logger.warning("Ragic service not configured")
            return []
        
        url = self._build_url(sheet_path)
        params: Dict[str, Any] = {
            "api": "",
            "limit": limit,
            "offset": offset
        }
        
        # Add filters as query params
        if filters:
            for field_id, value in filters.items():
                params[f"where_{field_id}"] = value
        
        try:
            response = await self._client.get(
                url, 
                params=params,
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                # Ragic returns dict with record_id as keys
                if isinstance(data, dict):
                    return list(data.values())
                return data
            else:
                self._logger.error(f"Get records failed: {response.status_code}")
                return []
                
        except Exception as e:
            self._logger.error(f"Get records error: {e}")
            return []
    
    async def get_record(
        self, 
        sheet_path: str, 
        record_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single record by ID.
        
        Args:
            sheet_path: Path to the sheet
            record_id: The record ID
            
        Returns:
            Record dictionary or None
        """
        if not self.is_configured():
            return None
        
        url = self._build_url(sheet_path, record_id)
        
        try:
            response = await self._client.get(
                url,
                params={"api": ""},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self._logger.error(f"Get record failed: {response.status_code}")
                return None
                
        except Exception as e:
            self._logger.error(f"Get record error: {e}")
            return None
    
    async def create_record(
        self, 
        sheet_path: str, 
        data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Create a new record in a Ragic sheet.
        
        Args:
            sheet_path: Path to the sheet
            data: Record data (field_id: value)
            
        Returns:
            New record ID or None
        """
        if not self.is_configured():
            return None
        
        url = self._build_url(sheet_path)
        
        try:
            response = await self._client.post(
                url,
                params={"api": ""},
                json=data,
                headers=self._get_headers()
            )
            
            if response.status_code in (200, 201):
                result = response.json()
                # Ragic returns the new record ID
                if isinstance(result, dict) and "_ragicId" in result:
                    return result["_ragicId"]
                return None
            else:
                self._logger.error(f"Create record failed: {response.status_code}")
                return None
                
        except Exception as e:
            self._logger.error(f"Create record error: {e}")
            return None
    
    async def update_record(
        self, 
        sheet_path: str, 
        record_id: int,
        data: Dict[str, Any]
    ) -> bool:
        """
        Update an existing record.
        
        Args:
            sheet_path: Path to the sheet
            record_id: The record ID to update
            data: Updated field data
            
        Returns:
            bool: True if successful
        """
        if not self.is_configured():
            return False
        
        url = self._build_url(sheet_path, record_id)
        
        try:
            response = await self._client.post(
                url,
                params={"api": ""},
                json=data,
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                self._logger.info(f"Record {record_id} updated")
                return True
            else:
                self._logger.error(f"Update failed: {response.status_code}")
                return False
                
        except Exception as e:
            self._logger.error(f"Update record error: {e}")
            return False
    
    async def delete_record(
        self, 
        sheet_path: str, 
        record_id: int
    ) -> bool:
        """
        Delete a record.
        
        Args:
            sheet_path: Path to the sheet
            record_id: The record ID to delete
            
        Returns:
            bool: True if successful
        """
        if not self.is_configured():
            return False
        
        url = self._build_url(sheet_path, record_id)
        
        try:
            response = await self._client.delete(
                url,
                params={"api": ""},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                self._logger.info(f"Record {record_id} deleted")
                return True
            else:
                self._logger.error(f"Delete failed: {response.status_code}")
                return False
                
        except Exception as e:
            self._logger.error(f"Delete record error: {e}")
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
