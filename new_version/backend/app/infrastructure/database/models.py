"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.connection import Base


class SyncConfig(Base):
    """Synchronization configuration per entity type."""

    __tablename__ = "sync_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SyncLog(Base):
    """Synchronization history logs."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # full/incremental/webhook
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # pending/running/completed/failed
    records_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class SyncState(Base):
    """State tracking for incremental synchronization."""

    __tablename__ = "sync_state"

    entity_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_modified_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    last_bitrix_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AIChart(Base):
    """AI-generated chart saved by user."""

    __tablename__ = "ai_charts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    chart_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    chart_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    sql_query: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PublishedDashboard(Base):
    """Published dashboard with password protection."""

    __tablename__ = "published_dashboards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    refresh_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=10, server_default="10", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardChart(Base):
    """Chart placement within a published dashboard."""

    __tablename__ = "dashboard_charts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dashboard_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("published_dashboards.id", ondelete="CASCADE"), nullable=False
    )
    chart_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_charts.id", ondelete="CASCADE"), nullable=False
    )
    title_override: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    layout_x: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    layout_y: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    layout_w: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    layout_h: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class DashboardLink(Base):
    """Link between dashboards for tab navigation."""

    __tablename__ = "dashboard_links"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "linked_dashboard_id", name="uq_dashboard_linked"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dashboard_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("published_dashboards.id", ondelete="CASCADE"), nullable=False
    )
    linked_dashboard_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("published_dashboards.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class DashboardSelector(Base):
    """Selector (filter control) on a dashboard."""

    __tablename__ = "dashboard_selectors"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "name", name="uq_dashboard_selector_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dashboard_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("published_dashboards.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    selector_type: Mapped[str] = mapped_column(String(30), nullable=False)
    operator: Mapped[str] = mapped_column(String(30), nullable=False, server_default="equals")
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class SelectorChartMapping(Base):
    """Mapping between a selector and a chart on the dashboard."""

    __tablename__ = "selector_chart_mappings"
    __table_args__ = (
        UniqueConstraint("selector_id", "dashboard_chart_id", name="uq_selector_chart_mapping"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    selector_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dashboard_selectors.id", ondelete="CASCADE"), nullable=False
    )
    dashboard_chart_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dashboard_charts.id", ondelete="CASCADE"), nullable=False
    )
    target_column: Mapped[str] = mapped_column(String(255), nullable=False)
    target_table: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    operator_override: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class SchemaDescription(Base):
    """AI-generated or raw schema descriptions for the database."""

    __tablename__ = "schema_descriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    entity_filter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    include_related: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChartPromptTemplate(Base):
    """System prompt template for AI chart generation."""

    __tablename__ = "chart_prompt_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
