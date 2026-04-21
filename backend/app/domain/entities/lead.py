"""Lead entity model."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class Lead(BitrixEntity):
    """Bitrix24 Lead (CRM Lead) entity.

    Standard fields from crm.lead.fields.
    User fields (UF_*) are stored in model_extra.
    """

    # Basic info
    title: Optional[str] = Field(None, alias="TITLE")
    status_id: Optional[str] = Field(None, alias="STATUS_ID")
    status_semantic_id: Optional[str] = Field(None, alias="STATUS_SEMANTIC_ID")
    status_description: Optional[str] = Field(None, alias="STATUS_DESCRIPTION")
    is_return_customer: Optional[str] = Field(None, alias="IS_RETURN_CUSTOMER")

    # Name fields
    name: Optional[str] = Field(None, alias="NAME")
    second_name: Optional[str] = Field(None, alias="SECOND_NAME")
    last_name: Optional[str] = Field(None, alias="LAST_NAME")
    honorific: Optional[str] = Field(None, alias="HONORIFIC")
    full_name: Optional[str] = Field(None, alias="FULL_NAME")

    # Company info
    company_title: Optional[str] = Field(None, alias="COMPANY_TITLE")
    company_id: Optional[str] = Field(None, alias="COMPANY_ID")
    contact_id: Optional[str] = Field(None, alias="CONTACT_ID")
    contact_ids: Optional[list[str]] = Field(None, alias="CONTACT_IDS")

    # Work info
    post: Optional[str] = Field(None, alias="POST")

    # Contact info (multifields)
    phone: Optional[list[dict[str, Any]]] = Field(None, alias="PHONE")
    email: Optional[list[dict[str, Any]]] = Field(None, alias="EMAIL")
    web: Optional[list[dict[str, Any]]] = Field(None, alias="WEB")
    im: Optional[list[dict[str, Any]]] = Field(None, alias="IM")

    # Address
    address: Optional[str] = Field(None, alias="ADDRESS")
    address_2: Optional[str] = Field(None, alias="ADDRESS_2")
    address_city: Optional[str] = Field(None, alias="ADDRESS_CITY")
    address_postal_code: Optional[str] = Field(None, alias="ADDRESS_POSTAL_CODE")
    address_region: Optional[str] = Field(None, alias="ADDRESS_REGION")
    address_province: Optional[str] = Field(None, alias="ADDRESS_PROVINCE")
    address_country: Optional[str] = Field(None, alias="ADDRESS_COUNTRY")
    address_country_code: Optional[str] = Field(None, alias="ADDRESS_COUNTRY_CODE")
    address_loc_addr_id: Optional[str] = Field(None, alias="ADDRESS_LOC_ADDR_ID")

    # Financial
    currency_id: Optional[str] = Field(None, alias="CURRENCY_ID")
    opportunity: Optional[Decimal] = Field(None, alias="OPPORTUNITY")
    is_manual_opportunity: Optional[str] = Field(None, alias="IS_MANUAL_OPPORTUNITY")

    # Status
    opened: Optional[str] = Field(None, alias="OPENED")

    # Description
    comments: Optional[str] = Field(None, alias="COMMENTS")

    # Source tracking
    source_id: Optional[str] = Field(None, alias="SOURCE_ID")
    source_description: Optional[str] = Field(None, alias="SOURCE_DESCRIPTION")

    # UTM
    utm_source: Optional[str] = Field(None, alias="UTM_SOURCE")
    utm_medium: Optional[str] = Field(None, alias="UTM_MEDIUM")
    utm_campaign: Optional[str] = Field(None, alias="UTM_CAMPAIGN")
    utm_content: Optional[str] = Field(None, alias="UTM_CONTENT")
    utm_term: Optional[str] = Field(None, alias="UTM_TERM")

    # External integration
    originator_id: Optional[str] = Field(None, alias="ORIGINATOR_ID")
    origin_id: Optional[str] = Field(None, alias="ORIGIN_ID")

    # Birthdate
    birthdate: Optional[datetime] = Field(None, alias="BIRTHDATE")

    # Activity
    last_activity_time: Optional[datetime] = Field(None, alias="LAST_ACTIVITY_TIME")
    last_activity_by: Optional[str] = Field(None, alias="LAST_ACTIVITY_BY")
    moved_by_id: Optional[str] = Field(None, alias="MOVED_BY_ID")
    moved_time: Optional[datetime] = Field(None, alias="MOVED_TIME")
