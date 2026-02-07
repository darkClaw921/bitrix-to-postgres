"""User entity model."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class User(BitrixEntity):
    """Bitrix24 User entity.

    Standard fields from user.fields / user.get.
    User fields (UF_*) are stored in model_extra.
    """

    # Basic info
    active: Optional[str] = Field(None, alias="ACTIVE")
    name: Optional[str] = Field(None, alias="NAME")
    last_name: Optional[str] = Field(None, alias="LAST_NAME")
    second_name: Optional[str] = Field(None, alias="SECOND_NAME")
    title: Optional[str] = Field(None, alias="TITLE")
    email: Optional[str] = Field(None, alias="EMAIL")
    xml_id: Optional[str] = Field(None, alias="XML_ID")
    user_type: Optional[str] = Field(None, alias="USER_TYPE")

    # Dates
    last_login: Optional[datetime] = Field(None, alias="LAST_LOGIN")
    date_register: Optional[datetime] = Field(None, alias="DATE_REGISTER")
    timestamp_x: Optional[datetime] = Field(None, alias="TIMESTAMP_X")
    last_activity_date: Optional[datetime] = Field(None, alias="LAST_ACTIVITY_DATE")

    # Timezone
    time_zone: Optional[str] = Field(None, alias="TIME_ZONE")
    is_online: Optional[str] = Field(None, alias="IS_ONLINE")

    # Personal info
    personal_gender: Optional[str] = Field(None, alias="PERSONAL_GENDER")
    personal_profession: Optional[str] = Field(None, alias="PERSONAL_PROFESSION")
    personal_www: Optional[str] = Field(None, alias="PERSONAL_WWW")
    personal_birthday: Optional[str] = Field(None, alias="PERSONAL_BIRTHDAY")
    personal_photo: Optional[str] = Field(None, alias="PERSONAL_PHOTO")
    personal_icq: Optional[str] = Field(None, alias="PERSONAL_ICQ")
    personal_phone: Optional[str] = Field(None, alias="PERSONAL_PHONE")
    personal_fax: Optional[str] = Field(None, alias="PERSONAL_FAX")
    personal_mobile: Optional[str] = Field(None, alias="PERSONAL_MOBILE")
    personal_pager: Optional[str] = Field(None, alias="PERSONAL_PAGER")
    personal_street: Optional[str] = Field(None, alias="PERSONAL_STREET")
    personal_city: Optional[str] = Field(None, alias="PERSONAL_CITY")
    personal_state: Optional[str] = Field(None, alias="PERSONAL_STATE")
    personal_zip: Optional[str] = Field(None, alias="PERSONAL_ZIP")
    personal_country: Optional[str] = Field(None, alias="PERSONAL_COUNTRY")
    personal_mailbox: Optional[str] = Field(None, alias="PERSONAL_MAILBOX")
    personal_notes: Optional[str] = Field(None, alias="PERSONAL_NOTES")

    # Work info
    work_phone: Optional[str] = Field(None, alias="WORK_PHONE")
    work_company: Optional[str] = Field(None, alias="WORK_COMPANY")
    work_position: Optional[str] = Field(None, alias="WORK_POSITION")
    work_department: Optional[str] = Field(None, alias="WORK_DEPARTMENT")
    work_www: Optional[str] = Field(None, alias="WORK_WWW")
    work_fax: Optional[str] = Field(None, alias="WORK_FAX")
    work_pager: Optional[str] = Field(None, alias="WORK_PAGER")
    work_street: Optional[str] = Field(None, alias="WORK_STREET")
    work_mailbox: Optional[str] = Field(None, alias="WORK_MAILBOX")
    work_city: Optional[str] = Field(None, alias="WORK_CITY")
    work_state: Optional[str] = Field(None, alias="WORK_STATE")
    work_zip: Optional[str] = Field(None, alias="WORK_ZIP")
    work_country: Optional[str] = Field(None, alias="WORK_COUNTRY")
    work_profile: Optional[str] = Field(None, alias="WORK_PROFILE")
    work_logo: Optional[str] = Field(None, alias="WORK_LOGO")
    work_notes: Optional[str] = Field(None, alias="WORK_NOTES")
