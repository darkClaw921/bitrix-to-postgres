"""Pydantic schemas for webhook endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class WebhookEventData(BaseModel):
    """Parsed Bitrix24 webhook event data."""

    event: str = Field(..., description="Event type (e.g., ONCRMDEALUPDATE)")
    entity_type: Optional[str] = Field(None, description="Entity type")
    entity_id: Optional[str] = Field(None, description="Entity ID")
    domain: Optional[str] = Field(None, description="Bitrix24 domain")
    raw_data: dict[str, Any] = Field(default_factory=dict)


class WebhookResponse(BaseModel):
    """Response for webhook handling."""

    status: str = Field("received", description="Status: received, processed, error")
    event: Optional[str] = None
    entity_id: Optional[str] = None
    message: Optional[str] = None


class WebhookRegistration(BaseModel):
    """Request to register a webhook."""

    event: str = Field(..., description="Event name to register")
    handler_url: str = Field(..., description="URL to receive webhook calls")


class WebhookRegistrationResponse(BaseModel):
    """Response for webhook registration."""

    status: str = Field(..., description="registered, already_exists, failed")
    event: str
    handler_url: str
    message: Optional[str] = None


class RegisteredWebhook(BaseModel):
    """Information about a registered webhook."""

    event: str
    handler: str
    connector_id: Optional[str] = None


class WebhookListResponse(BaseModel):
    """Response listing registered webhooks."""

    webhooks: list[RegisteredWebhook]
    total: int
