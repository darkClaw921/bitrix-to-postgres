"""Contact entity model."""

from datetime import datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class Contact(BitrixEntity):
    """Bitrix24 Contact (CRM Contact) entity.

    Standard fields from crm.contact.fields.
    User fields (UF_*) are stored in model_extra.
    """

    # Name fields
    name: Optional[str] = Field(None, alias="NAME")
    second_name: Optional[str] = Field(None, alias="SECOND_NAME")
    last_name: Optional[str] = Field(None, alias="LAST_NAME")
    honorific: Optional[str] = Field(None, alias="HONORIFIC")

    # Full name (generated)
    full_name: Optional[str] = Field(None, alias="FULL_NAME")

    # Basic info
    photo: Optional[str] = Field(None, alias="PHOTO")
    birthdate: Optional[datetime] = Field(None, alias="BIRTHDATE")
    type_id: Optional[str] = Field(None, alias="TYPE_ID")

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

    # Work info
    post: Optional[str] = Field(None, alias="POST")  # Job title
    company_id: Optional[str] = Field(None, alias="COMPANY_ID")

    # Status
    opened: Optional[str] = Field(None, alias="OPENED")
    export: Optional[str] = Field(None, alias="EXPORT")

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
    origin_version: Optional[str] = Field(None, alias="ORIGIN_VERSION")

    # Face tracking
    face_id: Optional[str] = Field(None, alias="FACE_ID")

    # Activity
    last_activity_time: Optional[datetime] = Field(None, alias="LAST_ACTIVITY_TIME")
    last_activity_by: Optional[str] = Field(None, alias="LAST_ACTIVITY_BY")
