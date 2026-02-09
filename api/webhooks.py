"""
Unified Webhook Router.

Handles incoming webhooks from external services (Ragic, LINE, etc.)
and dispatches them to the appropriate module/service.

Security:
    Webhook endpoints support multiple verification strategies:
    
    1. HMAC-SHA256 (Legacy/GitHub style):
       - Header: X-Hub-Signature-256: sha256=<signature>
       - Or URL token: ?token=<secret>
       
    2. RSA-SHA256 (Ragic style):
       - JSON body with embedded signature
       - Format: {"data": [...], "signature": "<base64>"}
    
    Configure secrets via environment variables:
    - WEBHOOK_DEFAULT_SECRET: Default secret for HMAC webhooks
    - WEBHOOK_SECRET_RAGIC: Source-specific secret for Ragic (HMAC mode)

Endpoints:
    POST /webhooks/ragic?source={key}  - Ragic form webhooks (JSON, RSA-verified)
    POST /webhooks/ragic/sync          - Trigger full sync (requires auth)
    GET  /webhooks/ragic/status        - Get all sync service statuses
"""

import json
import logging
import secrets
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from core.dependencies import HttpClientDep
from core.ragic.sync_base import get_sync_manager
from core.ragic.registry import get_ragic_registry
from core.security.webhook import (
    WebhookAuthContext,
    WebhookAuthResult,
    WebhookVerifierFactory,
    VerifierType,
    get_verifier_factory,
)

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
# Dependencies
# =============================================================================


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    
    Handles X-Forwarded-For header for reverse proxy setups.
    
    Args:
        request: The FastAPI Request object.
    
    Returns:
        str: The client IP address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_webhook_verifier_factory() -> WebhookVerifierFactory:
    """
    FastAPI dependency for webhook verifier factory.
    
    Returns:
        WebhookVerifierFactory: The singleton verifier factory.
    """
    return get_verifier_factory()


# Type alias for dependency injection
VerifierFactoryDep = Annotated[WebhookVerifierFactory, Depends(get_webhook_verifier_factory)]


# =============================================================================
# Ragic Webhook Endpoints
# =============================================================================


@router.post("/ragic", response_model=WebhookResponse)
async def ragic_webhook(
    request: Request,
    http_client: HttpClientDep,
    verifier_factory: VerifierFactoryDep,
    source: str = Query(..., description="Webhook source identifier (e.g., 'chatbot_sop')"),
) -> WebhookResponse:
    """
    Handle Ragic webhook notifications with RSA-SHA256 verification.
    
    Ragic sends webhooks in JSON format with embedded RSA signature:
    {
        "data": [
            {"_ragicId": 123, "field1": "value1", ...}
        ],
        "signature": "<base64-encoded-rsa-signature>"
    }
    
    Security:
        This endpoint uses RSA-SHA256 signature verification.
        The signature is embedded in the JSON body (not in headers).
        Public key is loaded from resources/certs/ragic_public_key.pem.
    
    Query Parameters:
        source: The sync service key to dispatch to (e.g., 'chatbot_sop').
    
    Request Body (JSON):
        data: List of record objects from Ragic.
        signature: Base64-encoded RSA-SHA256 signature of normalized data.
    
    Args:
        request: The FastAPI Request object.
        http_client: HTTP client for external API calls.
        verifier_factory: Factory for webhook verifiers.
        source: The sync service key from query parameters.
    
    Returns:
        WebhookResponse: Result of webhook processing.
    
    Raises:
        HTTPException: On authentication failure or processing error.
    """
    client_ip = get_client_ip(request)
    
    logger.info(
        f"Received Ragic webhook request. source={source}, ip={client_ip}"
    )
    
    # Get the RSA verifier for Ragic webhooks
    verifier = verifier_factory.get_verifier(VerifierType.RAGIC_RSA)
    
    # Verify the webhook signature
    auth_context: WebhookAuthContext = await verifier.verify(request)
    
    # Handle authentication failures
    if not auth_context.verified:
        _handle_auth_failure(auth_context, source, client_ip)
    
    logger.info(
        f"Authenticated Ragic webhook. source={source}, ip={client_ip}"
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
        
        # Extract data from verified payload
        payload_data = auth_context.payload_data or {}
        data_list = payload_data.get("data", [])
        
        if not data_list:
            # Try to parse body again if payload_data is empty
            try:
                body = await request.body()
                json_body = json.loads(body)
                data_list = json_body.get("data", [])
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse webhook body. source={source}, ip={client_ip}, error={e}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON payload"
                )
        
        logger.debug(f"Processing {len(data_list)} record(s) from Ragic webhook")
        
        # Dispatch to sync manager
        sync_manager = get_sync_manager()
        
        # Verify service exists
        if not sync_manager.get_service(source):
            available_services = [s['key'] for s in sync_manager.list_services()]
            logger.warning(
                f"Unknown sync service. source={source}, available={available_services}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sync service '{source}' not found. "
                       f"Available: {available_services}"
            )
        
        # Process each record in the data list
        if not data_list:
            # No data - trigger full sync instead
            logger.info(
                f"Webhook has no data records, triggering full sync. source={source}"
            )
            result = await sync_manager.sync_service(source, http_client)
            
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
        
        # Process the first record (Ragic typically sends one record per webhook)
        record = data_list[0] if isinstance(data_list, list) else data_list
        
        # Extract ragic_id from record
        ragic_id = (
            record.get("_ragicId") or 
            record.get("ragicId") or 
            record.get("id")
        )
        
        if not ragic_id:
            logger.info(
                f"Webhook record missing ragic_id, triggering full sync. source={source}"
            )
            result = await sync_manager.sync_service(source, http_client)
            
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
        except (ValueError, TypeError) as e:
            logger.error(
                f"Invalid ragic_id format. source={source}, ragic_id={ragic_id}, error={e}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ragic_id format"
            )
        
        # Determine action from record
        action = str(record.get("action", "update")).lower()
        
        result = await sync_manager.handle_webhook(source, ragic_id, http_client, action)
        
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
        logger.exception(
            f"Webhook processing error. source={source}, ip={client_ip}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _handle_auth_failure(
    auth_context: WebhookAuthContext,
    source: str,
    client_ip: str,
) -> None:
    """
    Handle webhook authentication failure by logging and raising HTTPException.
    
    Args:
        auth_context: The authentication context with failure details.
        source: The webhook source identifier.
        client_ip: The client IP address.
    
    Raises:
        HTTPException: Always raises with appropriate status code.
    """
    logger.warning(
        f"Webhook authentication failed. "
        f"source={source}, "
        f"result={auth_context.result.value}, "
        f"ip={client_ip}, "
        f"reason={auth_context.error_message}"
    )
    
    # Determine appropriate HTTP status code
    if auth_context.result == WebhookAuthResult.SECRET_NOT_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook not properly configured",
        )
    elif auth_context.result == WebhookAuthResult.PUBLIC_KEY_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification key not configured",
        )
    elif auth_context.result == WebhookAuthResult.INVALID_PAYLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=auth_context.error_message or "Invalid payload format",
        )
    elif auth_context.result in (
        WebhookAuthResult.MISSING_SIGNATURE,
        WebhookAuthResult.MISSING_TOKEN,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
            headers={"WWW-Authenticate": "Signature"},
        )
    else:
        # Invalid credentials - 403 Forbidden
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )


@router.post("/ragic/sync", response_model=SyncTriggerResponse)
async def trigger_sync(
    request: Request,
    http_client: HttpClientDep,
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
        key: API key for authentication.
    
    Headers:
        X-API-Key: <api_key>
    
    Note: This endpoint starts sync in-place (not background).
          For large datasets, this may take time.
    
    Args:
        request: The FastAPI Request object.
        http_client: HTTP client for external API calls.
        source: Optional specific service to sync.
        api_key: API key from query parameter.
    
    Returns:
        SyncTriggerResponse: Sync operation result.
    
    Raises:
        HTTPException: On authentication failure or sync error.
    """
    from core.providers import get_configuration_provider
    
    config = get_configuration_provider()
    client_ip = get_client_ip(request)
    
    # Get API key from header or query parameter
    provided_key = api_key or request.headers.get("X-API-Key")
    expected_key = config.get("webhook.default_secret")
    
    if not expected_key:
        logger.error(
            f"Sync endpoint called but no API key configured. ip={client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server"
        )
    
    if not provided_key:
        logger.warning(
            f"Sync endpoint called without API key. ip={client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_key, expected_key):
        logger.warning(
            f"Invalid API key for sync endpoint. ip={client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    logger.info(f"Authenticated sync request. ip={client_ip}")
    
    try:
        sync_manager = get_sync_manager()
        
        if source:
            # Sync specific service
            if not sync_manager.get_service(source):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sync service '{source}' not found"
                )
            
            result = await sync_manager.sync_service(source, http_client)
            
            return SyncTriggerResponse(
                success=result.errors == 0 if result else False,
                message=f"Sync completed for '{source}'",
                results={source: result.to_dict()} if result else None,
            )
        else:
            # Sync all services
            results = await sync_manager.sync_all(http_client, auto_only=False)
            
            return SyncTriggerResponse(
                success=all(r.errors == 0 for r in results.values()),
                message=f"Synced {len(results)} service(s)",
                results={k: v.to_dict() for k, v in results.items()},
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Sync trigger error. ip={client_ip}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/ragic/status", response_model=SyncStatusResponse)
async def get_sync_status() -> SyncStatusResponse:
    """
    Get status of all registered Ragic sync services.
    
    Returns:
        SyncStatusResponse: List of all sync services with their current status,
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
    
    Returns:
        dict: Available webhook sources and URL format.
    """
    sync_manager = get_sync_manager()
    services = sync_manager.list_services()
    
    return {
        "webhook_url_format": "/api/webhooks/ragic?source={source_key}",
        "verification_method": "RSA-SHA256 (body-embedded signature)",
        "payload_format": {
            "content_type": "application/json",
            "structure": {
                "data": "[array of record objects]",
                "signature": "<base64-encoded-rsa-signature>",
            },
        },
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
