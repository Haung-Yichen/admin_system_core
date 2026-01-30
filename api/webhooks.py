"""
Unified Webhook Router.

Handles incoming webhooks from external services (Ragic, LINE, etc.)
and dispatches them to the appropriate module/service.

Endpoints:
    POST /webhooks/ragic?source={key}  - Ragic form webhooks
    POST /webhooks/ragic/sync          - Trigger full sync
    GET  /webhooks/ragic/status        - Get all sync service statuses
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from pydantic import BaseModel

from core.ragic.sync_base import get_sync_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =============================================================================
# Response Models
# =============================================================================


class WebhookResponse(BaseModel):
    """Standard webhook response."""
    success: bool
    message: str
    ragic_id: Optional[int] = None
    source: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    services: list[dict[str, Any]]


class SyncTriggerResponse(BaseModel):
    """Response for manual sync trigger."""
    success: bool
    message: str
    results: Optional[dict[str, Any]] = None


# =============================================================================
# Ragic Webhook Endpoints
# =============================================================================


@router.post("/ragic", response_model=WebhookResponse)
async def ragic_webhook(
    request: Request,
    source: str = Query(..., description="Sync service key (e.g., 'chatbot_sop')"),
) -> WebhookResponse:
    """
    Handle Ragic webhook notifications.
    
    Ragic sends webhooks when records are created, updated, or deleted.
    The payload is form-urlencoded with field IDs as keys.
    
    Query Parameters:
        source: The sync service key to dispatch to.
    
    Expected Form Fields:
        _ragicId: Record ID in Ragic
        action (optional): "create", "update", or "delete"
    """
    try:
        # Parse form data
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"Received Ragic webhook for '{source}': {data}")
        
        # Extract ragic_id
        ragic_id = data.get("_ragicId") or data.get("ragicId") or data.get("id")
        
        if not ragic_id:
            logger.warning("Webhook missing ragic_id")
            raise HTTPException(status_code=400, detail="Missing ragic_id")
        
        try:
            ragic_id = int(ragic_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid ragic_id format")
        
        # Determine action
        action = str(data.get("action", "update")).lower()
        
        # Dispatch to sync manager
        sync_manager = get_sync_manager()
        
        # Verify service exists
        if not sync_manager.get_service(source):
            raise HTTPException(
                status_code=404,
                detail=f"Sync service '{source}' not found. "
                       f"Available: {[s['key'] for s in sync_manager.list_services()]}"
            )
        
        result = await sync_manager.handle_webhook(source, ragic_id, action)
        
        if result and result.errors == 0:
            if result.deleted > 0:
                return WebhookResponse(
                    success=True,
                    message=f"Deleted record {ragic_id}",
                    ragic_id=ragic_id,
                    source=source,
                )
            else:
                return WebhookResponse(
                    success=True,
                    message=f"Synced record {ragic_id}",
                    ragic_id=ragic_id,
                    source=source,
                )
        else:
            return WebhookResponse(
                success=False,
                message=f"Failed to process record {ragic_id}",
                ragic_id=ragic_id,
                source=source,
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ragic/sync", response_model=SyncTriggerResponse)
async def trigger_sync(
    source: Optional[str] = Query(None, description="Specific service to sync, or all if omitted"),
) -> SyncTriggerResponse:
    """
    Manually trigger a Ragic data sync.
    
    Query Parameters:
        source: Optional. Specific service key to sync.
                If omitted, syncs all registered services.
    
    Note: This endpoint starts sync in-place (not background).
          For large datasets, this may take time.
    """
    try:
        sync_manager = get_sync_manager()
        
        if source:
            # Sync specific service
            if not sync_manager.get_service(source):
                raise HTTPException(
                    status_code=404,
                    detail=f"Sync service '{source}' not found"
                )
            
            result = await sync_manager.sync_service(source)
            
            return SyncTriggerResponse(
                success=result.errors == 0 if result else False,
                message=f"Sync completed for '{source}'",
                results={source: result.to_dict()} if result else None,
            )
        else:
            # Sync all services
            results = await sync_manager.sync_all(auto_only=False)
            
            return SyncTriggerResponse(
                success=all(r.errors == 0 for r in results.values()),
                message=f"Synced {len(results)} service(s)",
                results={k: v.to_dict() for k, v in results.items()},
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Sync trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ragic/status", response_model=SyncStatusResponse)
async def get_sync_status() -> SyncStatusResponse:
    """
    Get status of all registered Ragic sync services.
    
    Returns:
        List of all sync services with their current status,
        last sync time, and last sync result.
    """
    sync_manager = get_sync_manager()
    services = sync_manager.list_services()
    
    return SyncStatusResponse(services=services)


@router.get("/ragic/services")
async def list_available_services() -> dict[str, Any]:
    """
    List available webhook sources for Ragic configuration.
    
    Returns webhook URL format and available sources.
    """
    sync_manager = get_sync_manager()
    services = sync_manager.list_services()
    
    return {
        "webhook_url_format": "/api/webhooks/ragic?source={source_key}",
        "available_sources": [
            {
                "key": s["key"],
                "name": s["name"],
                "module": s["module"],
                "webhook_url": f"/api/webhooks/ragic?source={s['key']}",
            }
            for s in services
        ],
        "note": "Configure this URL in Ragic form settings under 'Webhooks' or 'API Actions'",
    }
