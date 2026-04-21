"""Stage history entity model."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class StageHistory(BitrixEntity):
    """Bitrix24 Stage History entity (crm.stagehistory.list).

    Represents a record of stage/status transition for CRM entities.
    Each record tracks when an entity (deal/lead) moved between stages.

    TYPE_ID values:
    - 1: Entity creation
    - 2: Intermediate stage transition
    - 3: Final stage transition
    - 5: Funnel change

    For deals: uses STAGE_* fields
    For leads: uses STATUS_* fields
    Semantic IDs: P=intermediate, S=success, F=failure
    """

    # Primary identifier
    history_id: Optional[str] = Field(None, alias="ID")

    # Type of history record
    type_id: Optional[int] = Field(None, alias="TYPE_ID")

    # Owner entity (deal or lead ID)
    owner_id: Optional[str] = Field(None, alias="OWNER_ID")

    # Timestamp when transition occurred
    created_time: Optional[datetime] = Field(None, alias="CREATED_TIME")

    # Deal-specific fields (deals, new invoices, smart processes)
    category_id: Optional[str] = Field(None, alias="CATEGORY_ID")
    stage_semantic_id: Optional[str] = Field(None, alias="STAGE_SEMANTIC_ID")
    stage_id: Optional[str] = Field(None, alias="STAGE_ID")

    # Lead-specific fields (leads, old invoices)
    status_semantic_id: Optional[str] = Field(None, alias="STATUS_SEMANTIC_ID")
    status_id: Optional[str] = Field(None, alias="STATUS_ID")
