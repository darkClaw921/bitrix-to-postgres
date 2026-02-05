"""Company entity model."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class Company(BitrixEntity):
    """Bitrix24 Company (CRM Company) entity.

    Standard fields from crm.company.fields.
    User fields (UF_*) are stored in model_extra.
    """

    # Basic info
    title: Optional[str] = Field(None, alias="TITLE")
    company_type: Optional[str] = Field(None, alias="COMPANY_TYPE")
    industry: Optional[str] = Field(None, alias="INDUSTRY")

    # Logo
    logo: Optional[str] = Field(None, alias="LOGO")

    # Contact info (multifields)
    phone: Optional[list[dict[str, Any]]] = Field(None, alias="PHONE")
    email: Optional[list[dict[str, Any]]] = Field(None, alias="EMAIL")
    web: Optional[list[dict[str, Any]]] = Field(None, alias="WEB")
    im: Optional[list[dict[str, Any]]] = Field(None, alias="IM")

    # Address (Legal)
    address: Optional[str] = Field(None, alias="ADDRESS")
    address_2: Optional[str] = Field(None, alias="ADDRESS_2")
    address_city: Optional[str] = Field(None, alias="ADDRESS_CITY")
    address_postal_code: Optional[str] = Field(None, alias="ADDRESS_POSTAL_CODE")
    address_region: Optional[str] = Field(None, alias="ADDRESS_REGION")
    address_province: Optional[str] = Field(None, alias="ADDRESS_PROVINCE")
    address_country: Optional[str] = Field(None, alias="ADDRESS_COUNTRY")
    address_country_code: Optional[str] = Field(None, alias="ADDRESS_COUNTRY_CODE")
    address_loc_addr_id: Optional[str] = Field(None, alias="ADDRESS_LOC_ADDR_ID")
    address_legal: Optional[str] = Field(None, alias="ADDRESS_LEGAL")

    # Registration address
    reg_address: Optional[str] = Field(None, alias="REG_ADDRESS")
    reg_address_2: Optional[str] = Field(None, alias="REG_ADDRESS_2")
    reg_address_city: Optional[str] = Field(None, alias="REG_ADDRESS_CITY")
    reg_address_postal_code: Optional[str] = Field(
        None, alias="REG_ADDRESS_POSTAL_CODE"
    )
    reg_address_region: Optional[str] = Field(None, alias="REG_ADDRESS_REGION")
    reg_address_province: Optional[str] = Field(None, alias="REG_ADDRESS_PROVINCE")
    reg_address_country: Optional[str] = Field(None, alias="REG_ADDRESS_COUNTRY")
    reg_address_country_code: Optional[str] = Field(
        None, alias="REG_ADDRESS_COUNTRY_CODE"
    )
    reg_address_loc_addr_id: Optional[str] = Field(
        None, alias="REG_ADDRESS_LOC_ADDR_ID"
    )

    # Bank details
    banking_details: Optional[str] = Field(None, alias="BANKING_DETAILS")

    # Financial
    revenue: Optional[Decimal] = Field(None, alias="REVENUE")
    currency_id: Optional[str] = Field(None, alias="CURRENCY_ID")
    employees: Optional[str] = Field(None, alias="EMPLOYEES")  # Employee count range

    # Status
    opened: Optional[str] = Field(None, alias="OPENED")
    is_my_company: Optional[str] = Field(None, alias="IS_MY_COMPANY")

    # Description
    comments: Optional[str] = Field(None, alias="COMMENTS")

    # Lead relation
    lead_id: Optional[str] = Field(None, alias="LEAD_ID")

    # Contact relation
    contact_id: Optional[str] = Field(None, alias="CONTACT_ID")

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
    origin_version: Optional[str] = Field(None, alias="ORIGIN_VERSION")

    # Activity
    last_activity_time: Optional[datetime] = Field(None, alias="LAST_ACTIVITY_TIME")
    last_activity_by: Optional[str] = Field(None, alias="LAST_ACTIVITY_BY")
