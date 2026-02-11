"""Pydantic schemas for sync endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SyncConfigItem(BaseModel):
    """Configuration for a single entity type."""

    entity_type: str = Field(..., description="Entity type (deal, contact, lead, company)")
    enabled: bool = Field(True, description="Whether sync is enabled")
    sync_interval_minutes: int = Field(30, ge=5, le=1440, description="Sync interval")
    webhook_enabled: bool = Field(True, description="Whether webhooks are enabled")
    last_sync_at: Optional[datetime] = Field(None, description="Last sync timestamp")


class SyncConfigResponse(BaseModel):
    """Response for sync configuration."""

    entities: list[SyncConfigItem]
    default_interval_minutes: int = Field(30)


class SyncConfigUpdateRequest(BaseModel):
    """Request to update sync configuration."""

    entity_type: str = Field(..., description="Entity type to update")
    enabled: Optional[bool] = None
    sync_interval_minutes: Optional[int] = Field(None, ge=5, le=1440)
    webhook_enabled: Optional[bool] = None


class SyncStartRequest(BaseModel):
    """Request to start sync."""

    sync_type: str = Field("full", description="Sync type: full or incremental")


class SyncStartResponse(BaseModel):
    """Response for sync start."""

    status: str = Field(..., description="Status: started, already_running, already_queued")
    entity: str
    sync_type: str
    task_id: Optional[str] = Field(None, description="Queue task ID")
    message: Optional[str] = None


class SyncStatusItem(BaseModel):
    """Status of sync for one entity."""

    entity_type: str
    status: str = Field(..., description="idle, running, completed, failed")
    last_sync_type: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    records_synced: Optional[int] = None
    error_message: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Overall sync status response."""

    overall_status: str = Field(..., description="idle, running")
    entities: list[SyncStatusItem]


class SyncLogEntry(BaseModel):
    """Single sync log entry."""

    id: int
    entity_type: str
    sync_type: str
    status: str
    records_processed: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SyncHistoryResponse(BaseModel):
    """Response for sync history."""

    history: list[SyncLogEntry]
    total: int
    page: int = 1
    per_page: int = 50


class EntityStats(BaseModel):
    """Statistics for a single entity type."""

    count: int = Field(0, description="Total records count")
    last_sync: Optional[datetime] = None
    last_modified: Optional[datetime] = None


class SyncStatsResponse(BaseModel):
    """Response for sync statistics."""

    entities: dict[str, EntityStats]
    total_records: int = 0
