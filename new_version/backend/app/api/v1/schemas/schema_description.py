"""Pydantic schemas for schema description endpoints."""

from typing import Optional

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    """Column metadata from information_schema."""

    name: str
    data_type: str
    is_nullable: bool
    column_default: Optional[str] = None


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

    tables: list[TableInfo]
    markdown: str
