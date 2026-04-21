"""Deal entity model."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from app.domain.entities.base import BitrixEntity


class Deal(BitrixEntity):
    """Bitrix24 Deal (CRM Deal) entity.

    Standard fields from crm.deal.fields.
    User fields (UF_*) are stored in model_extra.
    """

    # Basic info
    title: Optional[str] = Field(None, alias="TITLE")
    type_id: Optional[str] = Field(None, alias="TYPE_ID")
    category_id: Optional[str] = Field(None, alias="CATEGORY_ID")
    stage_id: Optional[str] = Field(None, alias="STAGE_ID")
    stage_semantic_id: Optional[str] = Field(None, alias="STAGE_SEMANTIC_ID")

    # Status flags
    is_new: Optional[str] = Field(None, alias="IS_NEW")
    is_recurring: Optional[str] = Field(None, alias="IS_RECURRING")
    is_return_customer: Optional[str] = Field(None, alias="IS_RETURN_CUSTOMER")
    is_repeated_approach: Optional[str] = Field(None, alias="IS_REPEATED_APPROACH")
    closed: Optional[str] = Field(None, alias="CLOSED")
    opened: Optional[str] = Field(None, alias="OPENED")

    # Financial
    probability: Optional[int] = Field(None, alias="PROBABILITY")
    currency_id: Optional[str] = Field(None, alias="CURRENCY_ID")
    opportunity: Optional[Decimal] = Field(None, alias="OPPORTUNITY")
    is_manual_opportunity: Optional[str] = Field(None, alias="IS_MANUAL_OPPORTUNITY")
    tax_value: Optional[Decimal] = Field(None, alias="TAX_VALUE")

    # Relations
    company_id: Optional[str] = Field(None, alias="COMPANY_ID")
    contact_id: Optional[str] = Field(None, alias="CONTACT_ID")
    contact_ids: Optional[list[str]] = Field(None, alias="CONTACT_IDS")
    quote_id: Optional[str] = Field(None, alias="QUOTE_ID")
    lead_id: Optional[str] = Field(None, alias="LEAD_ID")

    # Dates
    begindate: Optional[datetime] = Field(None, alias="BEGINDATE")
    closedate: Optional[datetime] = Field(None, alias="CLOSEDATE")

    # Description
    comments: Optional[str] = Field(None, alias="COMMENTS")
    additional_info: Optional[str] = Field(None, alias="ADDITIONAL_INFO")

    # Source tracking
    source_id: Optional[str] = Field(None, alias="SOURCE_ID")
    source_description: Optional[str] = Field(None, alias="SOURCE_DESCRIPTION")

    # UTM
    utm_source: Optional[str] = Field(None, alias="UTM_SOURCE")
    utm_medium: Optional[str] = Field(None, alias="UTM_MEDIUM")
    utm_campaign: Optional[str] = Field(None, alias="UTM_CAMPAIGN")
    utm_content: Optional[str] = Field(None, alias="UTM_CONTENT")
    utm_term: Optional[str] = Field(None, alias="UTM_TERM")

    # Location
    location_id: Optional[str] = Field(None, alias="LOCATION_ID")

    # External integration
    originator_id: Optional[str] = Field(None, alias="ORIGINATOR_ID")
    origin_id: Optional[str] = Field(None, alias="ORIGIN_ID")

    # Activity tracking
    last_activity_time: Optional[datetime] = Field(None, alias="LAST_ACTIVITY_TIME")
    last_activity_by: Optional[str] = Field(None, alias="LAST_ACTIVITY_BY")
    moved_by_id: Optional[str] = Field(None, alias="MOVED_BY_ID")
    moved_time: Optional[datetime] = Field(None, alias="MOVED_TIME")

    @field_validator('opportunity', 'tax_value', mode='before')
    @classmethod
    def convert_string_to_decimal(cls, v):
        """Convert string numbers to Decimal."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            try:
                return Decimal(v)
            except (ValueError, TypeError):
                return None
        return v
