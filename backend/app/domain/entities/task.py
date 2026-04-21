"""Task entity model."""

from datetime import datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.entities.base import BitrixEntity


class Task(BitrixEntity):
    """Bitrix24 Task entity.

    Standard fields from tasks.task.getFields.
    """

    # Basic info
    title: Optional[str] = Field(None, alias="TITLE")
    description: Optional[str] = Field(None, alias="DESCRIPTION")
    priority: Optional[str] = Field(None, alias="PRIORITY")
    mark: Optional[str] = Field(None, alias="MARK")

    # Status
    status: Optional[str] = Field(None, alias="STATUS")
    multitask: Optional[str] = Field(None, alias="MULTITASK")
    not_viewed: Optional[str] = Field(None, alias="NOT_VIEWED")
    replicate: Optional[str] = Field(None, alias="REPLICATE")
    subordinate: Optional[str] = Field(None, alias="SUBORDINATE")
    favorite: Optional[str] = Field(None, alias="FAVORITE")

    # People
    responsible_id: Optional[str] = Field(None, alias="RESPONSIBLE_ID")
    changed_by: Optional[str] = Field(None, alias="CHANGED_BY")
    status_changed_by: Optional[str] = Field(None, alias="STATUS_CHANGED_BY")
    closed_by: Optional[str] = Field(None, alias="CLOSED_BY")

    # Relations
    parent_id: Optional[str] = Field(None, alias="PARENT_ID")
    group_id: Optional[str] = Field(None, alias="GROUP_ID")
    stage_id: Optional[str] = Field(None, alias="STAGE_ID")
    flow_id: Optional[str] = Field(None, alias="FLOW_ID")

    # Dates
    created_date: Optional[datetime] = Field(None, alias="CREATED_DATE")
    changed_date: Optional[datetime] = Field(None, alias="CHANGED_DATE")
    closed_date: Optional[datetime] = Field(None, alias="CLOSED_DATE")
    date_start: Optional[datetime] = Field(None, alias="DATE_START")
    deadline: Optional[datetime] = Field(None, alias="DEADLINE")
    start_date_plan: Optional[datetime] = Field(None, alias="START_DATE_PLAN")
    end_date_plan: Optional[datetime] = Field(None, alias="END_DATE_PLAN")
    viewed_date: Optional[datetime] = Field(None, alias="VIEWED_DATE")

    # Time tracking
    time_estimate: Optional[int] = Field(None, alias="TIME_ESTIMATE")
    time_spent_in_logs: Optional[int] = Field(None, alias="TIME_SPENT_IN_LOGS")
    allow_time_tracking: Optional[str] = Field(None, alias="ALLOW_TIME_TRACKING")
    allow_change_deadline: Optional[str] = Field(None, alias="ALLOW_CHANGE_DEADLINE")
    match_work_time: Optional[str] = Field(None, alias="MATCH_WORK_TIME")

    # Duration
    duration_plan: Optional[int] = Field(None, alias="DURATION_PLAN")
    duration_fact: Optional[int] = Field(None, alias="DURATION_FACT")
    duration_type: Optional[str] = Field(None, alias="DURATION_TYPE")

    # Comments
    comments_count: Optional[int] = Field(None, alias="COMMENTS_COUNT")
    new_comments_count: Optional[int] = Field(None, alias="NEW_COMMENTS_COUNT")

    # Flags
    task_control: Optional[str] = Field(None, alias="TASK_CONTROL")
    add_in_report: Optional[str] = Field(None, alias="ADD_IN_REPORT")
    forked_by_template_id: Optional[str] = Field(None, alias="FORKED_BY_TEMPLATE_ID")

    # Forum
    forum_topic_id: Optional[str] = Field(None, alias="FORUM_TOPIC_ID")
    forum_id: Optional[str] = Field(None, alias="FORUM_ID")
    site_id: Optional[str] = Field(None, alias="SITE_ID")

    # External IDs
    guid: Optional[str] = Field(None, alias="GUID")
    xml_id: Optional[str] = Field(None, alias="XML_ID")

    # Sorting
    sorting: Optional[str] = Field(None, alias="SORTING")

    # CRM binding
    uf_crm_task: Optional[Any] = Field(None, alias="UF_CRM_TASK")

    # Muting / pinning
    is_muted: Optional[str] = Field(None, alias="IS_MUTED")
    is_pinned: Optional[str] = Field(None, alias="IS_PINNED")
    is_pinned_in_group: Optional[str] = Field(None, alias="IS_PINNED_IN_GROUP")
