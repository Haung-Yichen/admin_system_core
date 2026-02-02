"""
Unified Webhook Router.

Handles incoming webhooks from external services (Ragic, LINE, etc.)
and dispatches them to the appropriate module/service.

Security:
    All webhook endpoints are protected by HMAC-SHA256 signature verification.
    Requests must include either:
    - X-Hub-Signature-256 header: sha256=<signature>
    - URL token parameter: ?token=<secret>
    
    Configure secrets via environment variables:
    - WEBHOOK_DEFAULT_SECRET: Default secret for all webhooks
    - WEBHOOK_SECRET_RAGIC: Source-specific secret for Ragic
    - WEBHOOK_SECRET_CHATBOT_SOP: Source-specific secret for chatbot SOP

Endpoints:
    POST /webhooks/ragic?source={key}  - Ragic form webhooks (authenticated)
    POST /webhooks/ragic/sync          - Trigger full sync (requires auth)
    GET  /webhooks/ragic/status        - Get all sync service statuses
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from core.dependencies import WebhookAuthDep
from core.ragic.sync_base import get_sync_manager
from core.ragic.registry import get_ragic_registry
from core.security.webhook import WebhookAuthContext
from pydantic import BaseModel

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
    auth: WebhookAuthDep,
) -> WebhookResponse:
    """
    Handle Ragic webhook notifications.
    
    Ragic sends webhooks when records are created, updated, or deleted.
    The payload is form-urlencoded with field IDs as keys.
    
    Security:
        This endpoint requires HMAC-SHA256 signature verification.
        Include X-Hub-Signature-256 header or token URL parameter.
    
    Query Parameters:
        source: The sync service key to dispatch to (e.g., 'chatbot_sop')
        token: Optional URL-based authentication token
    
    Headers:
        X-Hub-Signature-256: sha256=<hmac-signature>
    
    Expected Form Fields:
        _ragicId: Record ID in Ragic
        action (optional): "create", "update", or "delete"
    """
    # Auth context is already verified by WebhookAuthDep
    source = auth.source
    client_ip = auth.client_ip
    
    logger.info(
        f"Authenticated webhook request for '{source}' from IP: {client_ip}"
    )
    
    try:
        # Validate source against RagicRegistry webhook keys
        registry = get_ragic_registry()
        form_config = registry.get_form_by_webhook_key(source)
        
        if form_config:
            logger.debug(
                f"Webhook source '{source}' mapped to form '{form_config.form_key}' "
                f"(strategy: {form_config.sync_strategy})"
            )
        
        # Parse form data
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"Received Ragic webhook for '{source}': {data}")
        
        # Dispatch to sync manager
        sync_manager = get_sync_manager()
        
        # Verify service exists
        if not sync_manager.get_service(source):
            raise HTTPException(
                status_code=404,
                detail=f"Sync service '{source}' not found. "
                       f"Available: {[s['key'] for s in sync_manager.list_services()]}"
            )
        
        # Extract ragic_id
        ragic_id = data.get("_ragicId") or data.get("ragicId") or data.get("id")
        
        if not ragic_id:
            # No ragic_id provided - trigger full sync instead
            logger.info(f"Webhook missing ragic_id, triggering full sync for '{source}'")
            result = await sync_manager.sync_service(source)
            
            if result and result.errors == 0:
                return WebhookResponse(
                    success=True,
                    message=f"Full sync completed: {result.synced} records synced",
                    source=source,
                )
            else:
                return WebhookResponse(
                    success=False,
                    message=f"Full sync failed with {result.errors if result else 'unknown'} errors",
                    source=source,
                )
        
        try:
            ragic_id = int(ragic_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid ragic_id format")
        
        # Determine action
        action = str(data.get("action", "update")).lower()
        
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
    request: Request,
    source: Optional[str] = Query(None, description="Specific service to sync, or all if omitted"),
    api_key: Optional[str] = Query(None, description="API key for authentication", alias="key"),
) -> SyncTriggerResponse:
    """
    Manually trigger a Ragic data sync.
    
    Security:
        This endpoint requires authentication via:
        - API key query parameter: ?key=<api_key>
        - X-API-Key header
    
    Query Parameters:
        source: Optional. Specific service key to sync.
                If omitted, syncs all registered services.
        key: API key for authentication
    
    Headers:
        X-API-Key: <api_key>
    
    Note: This endpoint starts sync in-place (not background).
          For large datasets, this may take time.
    """
    from core.providers import get_configuration_provider
    from core.dependencies import _get_client_ip
    
    config = get_configuration_provider()
    client_ip = _get_client_ip(request)
    
    # Get API key from header or query parameter
    provided_key = api_key or request.headers.get("X-API-Key")
    expected_key = config.get("webhook.default_secret")
    
    if not expected_key:
        logger.error(f"Sync endpoint called but no API key configured. IP: {client_ip}")
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server"
        )
    
    if not provided_key:
        logger.warning(f"Sync endpoint called without API key from IP: {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Use constant-time comparison
    import secrets
    if not secrets.compare_digest(provided_key, expected_key):
        logger.warning(f"Invalid API key for sync endpoint from IP: {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    logger.info(f"Authenticated sync request from IP: {client_ip}")
    
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
