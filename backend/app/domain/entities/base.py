"""Base entity classes for Bitrix24 CRM entities."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class BitrixEntity(BaseModel):
    """Base class for all Bitrix24 CRM entities.

    Supports both standard fields and dynamic user fields (UF_*).
    """

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for UF_* user fields
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    # Core identifiers
    id: str = Field(..., description="Bitrix24 entity ID")

    # Audit fields
    date_create: Optional[datetime] = Field(None, alias="DATE_CREATE")
    date_modify: Optional[datetime] = Field(None, alias="DATE_MODIFY")
    created_by_id: Optional[str] = Field(None, alias="CREATED_BY_ID")
    modify_by_id: Optional[str] = Field(None, alias="MODIFY_BY_ID")
    assigned_by_id: Optional[str] = Field(None, alias="ASSIGNED_BY_ID")

    def get_user_fields(self) -> dict[str, Any]:
        """Extract all user fields (UF_*) from the entity."""
        return {
            k: v for k, v in self.model_extra.items() if k.upper().startswith("UF_")
        }

    def to_db_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary for database storage.

        - Converts field names to lowercase
        - Includes all extra fields (UF_*)
        """
        data = self.model_dump(by_alias=False, exclude_none=False)
        # Add extra fields (UF_* etc.)
        data.update(self.model_extra or {})
        # Convert all keys to lowercase for PostgreSQL
        return {k.lower(): v for k, v in data.items()}


class EntityType:
    """Enum-like class for entity types."""

    DEAL = "deal"
    CONTACT = "contact"
    LEAD = "lead"
    COMPANY = "company"
    USER = "user"
    TASK = "task"
    CALL = "call"
    STAGE_HISTORY_DEAL = "stage_history_deal"
    STAGE_HISTORY_LEAD = "stage_history_lead"

    # CRM entity types (use crm.* API namespace)
    _CRM_TYPES = {DEAL, CONTACT, LEAD, COMPANY}

    @classmethod
    def all(cls) -> list[str]:
        """Return all entity types."""
        return [
            cls.DEAL,
            cls.CONTACT,
            cls.LEAD,
            cls.COMPANY,
            cls.USER,
            cls.TASK,
            cls.CALL,
            cls.STAGE_HISTORY_DEAL,
            cls.STAGE_HISTORY_LEAD,
        ]

    @classmethod
    def is_crm(cls, entity_type: str) -> bool:
        """Check if entity type belongs to CRM namespace."""
        return entity_type in cls._CRM_TYPES

    @classmethod
    def get_bitrix_prefix(cls, entity_type: str) -> str:
        """Get Bitrix API prefix for entity type."""
        prefixes = {
            cls.DEAL: "crm.deal",
            cls.CONTACT: "crm.contact",
            cls.LEAD: "crm.lead",
            cls.COMPANY: "crm.company",
            cls.USER: "user",
            cls.TASK: "tasks.task",
            cls.CALL: "voximplant.statistic",
            cls.STAGE_HISTORY_DEAL: "crm.stagehistory",
            cls.STAGE_HISTORY_LEAD: "crm.stagehistory",
        }
        return prefixes.get(entity_type, f"crm.{entity_type}")

    @classmethod
    def get_table_name(cls, entity_type: str) -> str:
        """Get PostgreSQL table name for entity type."""
        # stage_history types already include prefix in name
        if entity_type.startswith("stage_history_"):
            return entity_type + "s"

        table_names = {
            cls.USER: "bitrix_users",
            cls.TASK: "bitrix_tasks",
            cls.CALL: "bitrix_calls",
        }
        return table_names.get(entity_type, f"crm_{entity_type}s")
