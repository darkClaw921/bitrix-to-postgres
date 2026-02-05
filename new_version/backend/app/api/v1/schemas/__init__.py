"""API v1 Pydantic schemas."""

from app.api.v1.schemas.common import (
    ErrorResponse,
    HealthResponse,
    PaginationParams,
    SuccessResponse,
)
from app.api.v1.schemas.sync import (
    EntityStats,
    SyncConfigItem,
    SyncConfigResponse,
    SyncConfigUpdateRequest,
    SyncHistoryResponse,
    SyncLogEntry,
    SyncStartRequest,
    SyncStartResponse,
    SyncStatsResponse,
    SyncStatusItem,
    SyncStatusResponse,
)
from app.api.v1.schemas.webhooks import (
    RegisteredWebhook,
    WebhookEventData,
    WebhookListResponse,
    WebhookRegistration,
    WebhookRegistrationResponse,
    WebhookResponse,
)

__all__ = [
    # Common
    "ErrorResponse",
    "HealthResponse",
    "PaginationParams",
    "SuccessResponse",
    # Sync
    "EntityStats",
    "SyncConfigItem",
    "SyncConfigResponse",
    "SyncConfigUpdateRequest",
    "SyncHistoryResponse",
    "SyncLogEntry",
    "SyncStartRequest",
    "SyncStartResponse",
    "SyncStatsResponse",
    "SyncStatusItem",
    "SyncStatusResponse",
    # Webhooks
    "RegisteredWebhook",
    "WebhookEventData",
    "WebhookListResponse",
    "WebhookRegistration",
    "WebhookRegistrationResponse",
    "WebhookResponse",
]
