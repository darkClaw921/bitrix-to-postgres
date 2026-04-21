"""Call (telephony) entity model."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class Call(BitrixEntity):
    """Bitrix24 Call entity (voximplant.statistic.get).

    Represents a telephony call history record.
    The API uses CALL_ID as the primary identifier.
    """

    # Call identifiers
    call_id: Optional[str] = Field(None, alias="CALL_ID")
    call_type: Optional[int] = Field(None, alias="CALL_TYPE")
    call_vote: Optional[int] = Field(None, alias="CALL_VOTE")
    comment: Optional[str] = Field(None, alias="COMMENT")

    # Operator / portal info
    portal_user_id: Optional[str] = Field(None, alias="PORTAL_USER_ID")
    portal_number: Optional[str] = Field(None, alias="PORTAL_NUMBER")
    phone_number: Optional[str] = Field(None, alias="PHONE_NUMBER")

    # Duration and timing
    call_duration: Optional[int] = Field(None, alias="CALL_DURATION")
    call_start_date: Optional[datetime] = Field(None, alias="CALL_START_DATE")

    # Cost
    cost: Optional[str] = Field(None, alias="COST")
    cost_currency: Optional[str] = Field(None, alias="COST_CURRENCY")

    # Failure info
    call_failed_code: Optional[str] = Field(None, alias="CALL_FAILED_CODE")
    call_failed_reason: Optional[str] = Field(None, alias="CALL_FAILED_REASON")

    # CRM links
    crm_activity_id: Optional[str] = Field(None, alias="CRM_ACTIVITY_ID")
    crm_entity_id: Optional[str] = Field(None, alias="CRM_ENTITY_ID")
    crm_entity_type: Optional[str] = Field(None, alias="CRM_ENTITY_TYPE")

    # REST app info
    rest_app_id: Optional[str] = Field(None, alias="REST_APP_ID")
    rest_app_name: Optional[str] = Field(None, alias="REST_APP_NAME")

    # Additional
    redial_attempt: Optional[int] = Field(None, alias="REDIAL_ATTEMPT")
    session_id: Optional[str] = Field(None, alias="SESSION_ID")
    transcript_id: Optional[str] = Field(None, alias="TRANSCRIPT_ID")
    transcript_pending: Optional[str] = Field(None, alias="TRANSCRIPT_PENDING")
    record_file_id: Optional[str] = Field(None, alias="RECORD_FILE_ID")
