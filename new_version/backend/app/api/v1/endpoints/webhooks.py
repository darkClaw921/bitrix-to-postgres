"""Webhook handler endpoints."""

import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request

from app.config import get_settings
from app.core.logging import get_logger
from app.core.webhooks import extract_event_info, parse_nested_query
from app.domain.services.sync_service import SyncService
from app.infrastructure.bitrix.client import BitrixClient

router = APIRouter()
logger = get_logger(__name__)

# Event type to entity type mapping
EVENT_ENTITY_MAP = {
    "ONCRMDEALUPDATE": "deal",
    "ONCRMDEALADD": "deal",
    "ONCRMDEALDELETE": "deal",
    "ONCRMCONTACTUPDATE": "contact",
    "ONCRMCONTACTADD": "contact",
    "ONCRMCONTACTDELETE": "contact",
    "ONCRMLEADUPDATE": "lead",
    "ONCRMLEADADD": "lead",
    "ONCRMLEADDELETE": "lead",
    "ONCRMCOMPANYUPDATE": "company",
    "ONCRMCOMPANYADD": "company",
    "ONCRMCOMPANYDELETE": "company",
}

# Events that are supported
SUPPORTED_EVENTS = list(EVENT_ENTITY_MAP.keys())


def get_entity_type_from_event(event: str) -> str | None:
    """Extract entity type from event name.

    Args:
        event: Event name (e.g., ONCRMDEALUPDATE)

    Returns:
        Entity type or None
    """
    return EVENT_ENTITY_MAP.get(event.upper())


def is_delete_event(event: str) -> bool:
    """Check if event is a delete event.

    Args:
        event: Event name

    Returns:
        True if delete event
    """
    return event.upper().endswith("DELETE")


async def process_webhook_event(event_data: dict[str, Any]) -> dict[str, Any]:
    """Process a single webhook event.

    Args:
        event_data: Parsed event data

    Returns:
        Processing result
    """
    event_type, entity_id = extract_event_info(event_data)

    if not event_type:
        logger.warning("No event type in webhook data")
        return {"status": "ignored", "reason": "no_event_type"}

    entity_type = get_entity_type_from_event(event_type)
    if not entity_type:
        logger.warning("Unsupported event type", event_type=event_type)
        return {"status": "ignored", "reason": "unsupported_event"}

    if not entity_id:
        logger.warning("No entity ID in webhook data", event_type=event_type)
        return {"status": "ignored", "reason": "no_entity_id"}

    logger.info(
        "Processing webhook event",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    try:
        bitrix_client = BitrixClient()
        sync_service = SyncService(bitrix_client=bitrix_client)

        if is_delete_event(event_type):
            result = await sync_service.delete_entity_by_id(entity_type, entity_id)
        else:
            result = await sync_service.sync_entity_by_id(entity_type, entity_id)

        return result

    except Exception as e:
        logger.error(
            "Webhook processing failed",
            event_type=event_type,
            entity_id=entity_id,
            error=str(e),
        )
        return {"status": "error", "error": str(e)}


@router.post("/bitrix")
async def handle_bitrix_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Handle incoming Bitrix24 webhook events.

    Bitrix24 sends webhooks as URL-encoded form data with nested keys.
    This endpoint parses the data and processes the event asynchronously.

    Returns immediately with 200 OK to Bitrix24, processes in background.
    """
    body = await request.body()
    body_str = body.decode("utf-8")

    logger.debug("Received webhook", body=body_str[:500])

    event_data = parse_nested_query(body_str)
    event_type, entity_id = extract_event_info(event_data)

    logger.info(
        "Webhook received",
        event_type=event_type,
        entity_id=entity_id,
    )

    # Process in background to return quickly to Bitrix
    background_tasks.add_task(process_webhook_event, event_data)

    return {
        "status": "accepted",
        "event": event_type,
        "entity_id": entity_id,
    }


@router.post("/register")
async def register_webhooks(
    handler_base_url: str | None = None,
) -> dict:
    """Register webhooks with Bitrix24 via event.bind.

    Args:
        handler_base_url: Base URL for webhook handlers.
            If not provided, uses settings.

    Returns:
        Registration result with list of registered events
    """
    settings = get_settings()

    # Build handler URL
    base_url = handler_base_url or f"http://localhost:{settings.port}"
    webhook_url = f"{base_url}/api/v1/webhooks/bitrix"

    logger.info("Registering webhooks", handler_url=webhook_url)

    bitrix_client = BitrixClient()
    registered_events = []
    failed_events = []

    for event in SUPPORTED_EVENTS:
        success = await bitrix_client.register_webhook(event, webhook_url)
        if success:
            registered_events.append(event)
        else:
            failed_events.append(event)

    logger.info(
        "Webhook registration complete",
        registered=len(registered_events),
        failed=len(failed_events),
    )

    return {
        "status": "completed",
        "handler_url": webhook_url,
        "registered": registered_events,
        "failed": failed_events,
    }


@router.delete("/unregister")
async def unregister_webhooks(
    handler_base_url: str | None = None,
) -> dict:
    """Unregister all webhooks from Bitrix24.

    Args:
        handler_base_url: Base URL used for webhook handlers

    Returns:
        Unregistration result
    """
    settings = get_settings()

    base_url = handler_base_url or f"http://localhost:{settings.port}"
    webhook_url = f"{base_url}/api/v1/webhooks/bitrix"

    logger.info("Unregistering webhooks", handler_url=webhook_url)

    bitrix_client = BitrixClient()
    unregistered_events = []

    for event in SUPPORTED_EVENTS:
        success = await bitrix_client.unregister_webhook(event, webhook_url)
        if success:
            unregistered_events.append(event)

    return {
        "status": "completed",
        "unregistered": unregistered_events,
    }


@router.get("/registered")
async def get_registered_webhooks() -> dict:
    """Get list of currently registered webhooks in Bitrix24.

    Returns:
        List of registered event handlers
    """
    bitrix_client = BitrixClient()
    webhooks = await bitrix_client.get_registered_webhooks()

    return {
        "webhooks": webhooks,
        "count": len(webhooks) if isinstance(webhooks, list) else 0,
    }
