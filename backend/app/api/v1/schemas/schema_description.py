"""Pydantic schemas for schema description endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    """Column metadata from information_schema."""

    name: str
    data_type: str
    is_nullable: bool
    column_default: Optional[str] = None
    description: Optional[str] = None


class TableInfo(BaseModel):
    """Table metadata with columns."""

    table_name: str
    columns: list[ColumnInfo]
    row_count: Optional[int] = None


class SchemaTablesResponse(BaseModel):
    """Raw table list with columns (no AI)."""

    tables: list[TableInfo]


class SchemaDescriptionResponse(BaseModel):
    """AI-generated markdown description of the DB schema."""

    id: int
    tables: list[TableInfo]
    markdown: str
    entity_filter: Optional[str] = None
    include_related: bool = True
    created_at: datetime
    updated_at: datetime


class SchemaDescriptionUpdate(BaseModel):
    """Request to update a schema description."""

    markdown: str


class SchemaDescriptionListItem(BaseModel):
    """Schema description list item."""

    id: int
    entity_filter: Optional[str] = None
    include_related: bool
    created_at: datetime
    updated_at: datetime


class SchemaDescriptionListResponse(BaseModel):
    """List of saved schema descriptions."""

    items: list[SchemaDescriptionListItem]
    total: int
