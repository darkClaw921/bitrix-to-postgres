"""Bitrix24 API client with retry and rate limiting support."""

import re
from typing import Any, TypeVar

from fast_bitrix24 import BitrixAsync
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.exceptions import (
    BitrixAPIError,
    BitrixAuthError,
    BitrixOperationTimeLimitError,
    BitrixRateLimitError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# user.fields returns flat {FIELD: description} without type metadata.
# This mapping provides type info for known user fields.
USER_FIELD_TYPES: dict[str, str] = {
    "ID": "integer",
    "XML_ID": "string",
    "ACTIVE": "char",
    "NAME": "string",
    "LAST_NAME": "string",
    "SECOND_NAME": "string",
    "TITLE": "string",
    "EMAIL": "string",
    "LAST_LOGIN": "datetime",
    "DATE_REGISTER": "datetime",
    "TIME_ZONE": "string",
    "IS_ONLINE": "char",
    "TIME_ZONE_OFFSET": "string",
    "TIMESTAMP_X": "datetime",
    "LAST_ACTIVITY_DATE": "datetime",
    "PERSONAL_GENDER": "string",
    "PERSONAL_PROFESSION": "string",
    "PERSONAL_WWW": "string",
    "PERSONAL_BIRTHDAY": "date",
    "PERSONAL_PHOTO": "integer",
    "PERSONAL_ICQ": "string",
    "PERSONAL_PHONE": "string",
    "PERSONAL_FAX": "string",
    "PERSONAL_MOBILE": "string",
    "PERSONAL_PAGER": "string",
    "PERSONAL_STREET": "string",
    "PERSONAL_CITY": "string",
    "PERSONAL_STATE": "string",
    "PERSONAL_ZIP": "string",
    "PERSONAL_COUNTRY": "string",
    "PERSONAL_MAILBOX": "string",
    "PERSONAL_NOTES": "text",
    "WORK_PHONE": "string",
    "WORK_COMPANY": "string",
    "WORK_POSITION": "string",
    "WORK_DEPARTMENT": "string",
    "WORK_WWW": "string",
    "WORK_FAX": "string",
    "WORK_PAGER": "string",
    "WORK_STREET": "string",
    "WORK_MAILBOX": "string",
    "WORK_CITY": "string",
    "WORK_STATE": "string",
    "WORK_ZIP": "string",
    "WORK_COUNTRY": "string",
    "WORK_PROFILE": "string",
    "WORK_LOGO": "string",
    "WORK_NOTES": "text",
    "UF_SKYPE_LINK": "string",
    "UF_ZOOM": "string",
    "UF_EMPLOYMENT_DATE": "datetime",
    "UF_TIMEMAN": "char",
    "UF_DEPARTMENT": "string",
    "UF_INTERESTS": "text",
    "UF_SKILLS": "text",
    "UF_WEB_SITES": "text",
    "UF_XING": "string",
    "UF_LINKEDIN": "string",
    "UF_FACEBOOK": "string",
    "UF_TWITTER": "string",
    "UF_SKYPE": "string",
    "UF_DISTRICT": "string",
    "UF_PHONE_INNER": "string",
    "USER_TYPE": "string",
}

# voximplant.statistic.get has no .fields method.
# This mapping provides type info for known call fields.
CALL_FIELD_TYPES: dict[str, str] = {
    "ID": "integer",
    "CALL_ID": "string",
    "CALL_TYPE": "integer",
    "CALL_VOTE": "integer",
    "COMMENT": "string",
    "PORTAL_USER_ID": "string",
    "PORTAL_NUMBER": "string",
    "PHONE_NUMBER": "string",
    "CALL_DURATION": "integer",
    "CALL_START_DATE": "datetime",
    "COST": "string",
    "COST_CURRENCY": "string",
    "CALL_FAILED_CODE": "string",
    "CALL_FAILED_REASON": "string",
    "CRM_ACTIVITY_ID": "string",
    "CRM_ENTITY_ID": "string",
    "CRM_ENTITY_TYPE": "string",
    "REST_APP_ID": "string",
    "REST_APP_NAME": "string",
    "REDIAL_ATTEMPT": "integer",
    "SESSION_ID": "string",
    "TRANSCRIPT_ID": "string",
    "TRANSCRIPT_PENDING": "string",
    "RECORD_FILE_ID": "string",
}

# crm.stagehistory.list has no .fields method.
# This mapping provides type info for known stage history fields.
STAGE_HISTORY_FIELD_TYPES: dict[str, str] = {
    "ID": "integer",
    "TYPE_ID": "integer",
    "OWNER_ID": "integer",
    "CREATED_TIME": "datetime",
    "CATEGORY_ID": "integer",
    "STAGE_SEMANTIC_ID": "string",
    "STAGE_ID": "string",
    "STATUS_SEMANTIC_ID": "string",
    "STATUS_ID": "string",
}


def _camel_to_upper_snake(name: str) -> str:
    """Convert camelCase to UPPER_SNAKE_CASE.

    Already UPPER_SNAKE_CASE keys (e.g. UF_CRM_TASK) pass through unchanged.

    Examples:
        responsibleId -> RESPONSIBLE_ID
        changedDate   -> CHANGED_DATE
        ID            -> ID
        UF_CRM_TASK   -> UF_CRM_TASK
    """
    converted = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return converted.upper()


def _normalize_task_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize task record keys from camelCase to UPPER_SNAKE_CASE."""
    return [
        {_camel_to_upper_snake(k): v for k, v in record.items()}
        for record in records
    ]


class BitrixClient:
    """Async client for Bitrix24 REST API.

    Wraps fast-bitrix24 BitrixAsync with:
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Structured error handling
    """

    def __init__(self, webhook_url: str | None = None):
        """Initialize Bitrix client.

        Args:
            webhook_url: Bitrix24 webhook URL. If not provided, uses settings.
        """
        settings = get_settings()
        self._webhook_url = webhook_url or settings.bitrix_webhook_url
        self._client = BitrixAsync(self._webhook_url, ssl=False)
        self._batch_size = settings.sync_batch_size

    @retry(
        retry=retry_if_exception_type((BitrixRateLimitError,)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True,
    )
    async def _call(
        self,
        method: str,
        items: dict[str, Any] | None = None,
        raw: bool = True,
    ) -> dict[str, Any]:
        """Make a single API call with retry logic.

        Args:
            method: Bitrix24 REST API method name
            items: Request parameters
            raw: Return raw response

        Returns:
            API response data

        Raises:
            BitrixAPIError: On API errors
            BitrixRateLimitError: On rate limit (triggers retry)
            BitrixAuthError: On authentication errors
        """
        try:
            logger.debug("Calling Bitrix API", method=method, items=items)
            response = await self._client.call(method, items=items or {}, raw=raw)

            if raw and isinstance(response, dict):
                # Check for errors in raw response
                if "error" in response:
                    error_code = response.get("error", "")
                    error_msg = response.get("error_description", str(response))

                    if "OPERATION_TIME_LIMIT" in str(error_code):
                        raise BitrixOperationTimeLimitError(
                            f"OPERATION_TIME_LIMIT: {error_msg}"
                        )
                    if "QUERY_LIMIT_EXCEEDED" in str(error_code):
                        raise BitrixRateLimitError(f"Rate limit exceeded: {error_msg}")
                    if "expired_token" in str(error_code) or "invalid_token" in str(error_code):
                        raise BitrixAuthError(f"Authentication error: {error_msg}")
                    raise BitrixAPIError(f"Bitrix API error: {error_msg}")

                return response.get("result", response)

            return response

        except BitrixRateLimitError:
            logger.warning("Rate limit hit, will retry", method=method)
            raise
        except BitrixAuthError:
            logger.error("Authentication failed", method=method)
            raise
        except BitrixOperationTimeLimitError:
            logger.error("Operation time limit exceeded", method=method)
            raise
        except Exception as e:
            if "OPERATION_TIME_LIMIT" in str(e):
                raise BitrixOperationTimeLimitError(
                    f"OPERATION_TIME_LIMIT: {str(e)}"
                ) from e
            logger.error("Bitrix API call failed", method=method, error=str(e))
            raise BitrixAPIError(f"API call failed: {str(e)}") from e

    async def get_all(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get all records using batch requests.

        Uses fast-bitrix24's built-in pagination handling.

        Args:
            method: Bitrix24 list method (e.g., crm.deal.list)
            params: Request parameters (FILTER, SELECT, etc.)

        Returns:
            List of all records
        """
        try:
            logger.info("Fetching all records", method=method)
            result = await self._client.get_all(method, params=params or {})
            logger.info("Fetched records", method=method, count=len(result))
            return result
        except BitrixOperationTimeLimitError:
            raise
        except Exception as e:
            if "OPERATION_TIME_LIMIT" in str(e):
                raise BitrixOperationTimeLimitError(
                    f"OPERATION_TIME_LIMIT: сервер Bitrix24 не успел обработать запрос. "
                    f"Попробуйте использовать фильтр (например, DATE_CREATE > 2024-01-01). "
                    f"Метод: {method}"
                ) from e
            logger.error("Failed to fetch all records", method=method, error=str(e))
            raise BitrixAPIError(f"Failed to fetch records: {str(e)}") from e

    async def get_entities(
        self,
        entity_type: str,
        filter_params: dict[str, Any] | None = None,
        select: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get all entities of a specific type.

        Args:
            entity_type: Entity type (deal, contact, lead, company, user, task, stage_history_*)
            filter_params: Filter parameters
            select: Fields to select (defaults to all including UF_*)

        Returns:
            List of entities
        """
        if entity_type == "user":
            return await self._get_users(filter_params)
        if entity_type == "task":
            return await self._get_tasks(filter_params, select)
        if entity_type == "call":
            return await self._get_calls(filter_params)
        if entity_type in ["stage_history_deal", "stage_history_lead"]:
            return await self._get_stage_history(entity_type, filter_params, select)

        method = f"crm.{entity_type}.list"
        params: dict[str, Any] = {}

        if filter_params:
            params["FILTER"] = filter_params
        else:
            params["FILTER"] = {">ID": 0}

        if select:
            params["SELECT"] = select
        else:
            params["SELECT"] = ["*", "UF_*"]

        return await self.get_all(method, params)

    async def _get_users(
        self,
        filter_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get all users via user.get (non-CRM namespace)."""
        params: dict[str, Any] = {}
        if filter_params:
            params["FILTER"] = filter_params
        return await self.get_all("user.get", params)

    async def _get_tasks(
        self,
        filter_params: dict[str, Any] | None = None,
        select: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get all tasks via tasks.task.list.

        tasks.task.list returns {tasks: [...]} inside result,
        so we need to unwrap the response.
        """
        params: dict[str, Any] = {}
        if filter_params:
            params["filter"] = filter_params
        if select:
            params["select"] = select

        try:
            logger.info("Fetching all tasks")
            result = await self._client.get_all("tasks.task.list", params=params)

            # fast-bitrix24 may return list directly or dict with 'tasks' key
            if isinstance(result, list):
                # If each item is a dict with 'tasks' key, unwrap
                if result and isinstance(result[0], dict) and "tasks" in result[0]:
                    tasks = []
                    for batch in result:
                        tasks.extend(batch.get("tasks", []))
                    return _normalize_task_records(tasks)
                return _normalize_task_records(result)
            if isinstance(result, dict) and "tasks" in result:
                return _normalize_task_records(result["tasks"])
            return _normalize_task_records(result)
        except BitrixOperationTimeLimitError:
            raise
        except Exception as e:
            if "OPERATION_TIME_LIMIT" in str(e):
                raise BitrixOperationTimeLimitError(
                    f"OPERATION_TIME_LIMIT: сервер Bitrix24 не успел обработать запрос задач. "
                    f"Попробуйте использовать фильтр (например, CHANGED_DATE > 2024-01-01)."
                ) from e
            logger.error("Failed to fetch tasks", error=str(e))
            raise BitrixAPIError(f"Failed to fetch tasks: {str(e)}") from e

    async def _get_calls(
        self,
        filter_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get all call records via voximplant.statistic.get.

        Remaps CALL_ID → ID so that _prepare_record_data() uses CALL_ID
        as bitrix_id (the unique key).
        """
        params: dict[str, Any] = {}
        if filter_params:
            params["FILTER"] = filter_params

        try:
            logger.info("Fetching all calls")
            result = await self._client.get_all(
                "voximplant.statistic.get", params=params
            )
            # Remap: set ID = CALL_ID so bitrix_id uses CALL_ID
            for record in result:
                if "CALL_ID" in record:
                    record["ID"] = record["CALL_ID"]
            logger.info("Fetched calls", count=len(result))
            return result
        except BitrixOperationTimeLimitError:
            raise
        except Exception as e:
            if "OPERATION_TIME_LIMIT" in str(e):
                raise BitrixOperationTimeLimitError(
                    f"OPERATION_TIME_LIMIT: сервер Bitrix24 не успел обработать запрос звонков. "
                    f"Попробуйте использовать фильтр (например, CALL_START_DATE > 2024-01-01)."
                ) from e
            logger.error("Failed to fetch calls", error=str(e))
            raise BitrixAPIError(f"Failed to fetch calls: {str(e)}") from e

    async def _get_stage_history(
        self,
        entity_type: str,
        filter_params: dict[str, Any] | None = None,
        select: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get stage history records via crm.stagehistory.list.

        Args:
            entity_type: "stage_history_deal" or "stage_history_lead"
            filter_params: Filter parameters for API
            select: List of fields to select

        Returns:
            List of stage history records
        """
        # Determine entityTypeId: 1=Lead, 2=Deal
        entity_type_id = 1 if entity_type == "stage_history_lead" else 2

        params: dict[str, Any] = {
            "entityTypeId": entity_type_id,
        }

        if filter_params:
            params["filter"] = filter_params

        if select:
            params["select"] = select

        try:
            logger.info(
                "Fetching stage history",
                entity_type=entity_type,
                entity_type_id=entity_type_id,
            )

            # Use built-in get_all for automatic pagination
            result = await self._client.get_all("crm.stagehistory.list", params=params)

            # crm.stagehistory.list returns {"items": [...]} structure
            # fast-bitrix24 get_all may return list directly or dict with items
            if isinstance(result, dict) and "items" in result:
                records = result["items"]
            elif isinstance(result, list):
                # If result is already a list, check if items are wrapped
                if result and isinstance(result[0], dict) and "items" in result[0]:
                    # Unwrap batched items
                    records = []
                    for batch in result:
                        records.extend(batch.get("items", []))
                else:
                    records = result
            else:
                records = []

            logger.info(
                "Fetched stage history",
                entity_type=entity_type,
                count=len(records),
            )
            return records

        except BitrixOperationTimeLimitError:
            raise
        except Exception as e:
            if "OPERATION_TIME_LIMIT" in str(e):
                raise BitrixOperationTimeLimitError(
                    f"OPERATION_TIME_LIMIT: сервер Bitrix24 не успел обработать запрос истории стадий. "
                    f"Попробуйте использовать фильтр (например, CREATED_TIME > 2024-01-01)."
                ) from e
            logger.error(
                "Failed to fetch stage history",
                entity_type=entity_type,
                error=str(e),
            )
            raise BitrixAPIError(f"Failed to fetch stage history: {str(e)}") from e

    async def get_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """Get a single entity by ID.

        Args:
            entity_type: Entity type (deal, contact, lead, company, user, task, stage_history_*)
            entity_id: Entity ID

        Returns:
            Entity data
        """
        if entity_type == "user":
            # user.get with ID filter returns a list; take the first item
            result = await self._call(
                "user.get", items={"ID": entity_id}
            )
            if isinstance(result, list):
                return result[0] if result else {}
            return result

        if entity_type == "task":
            result = await self._call(
                "tasks.task.get", items={"taskId": entity_id}
            )
            # Result may be {"task": {...}} or the task dict directly
            if isinstance(result, dict) and "task" in result:
                task_data = result["task"]
            else:
                task_data = result
            # Normalize camelCase keys to UPPER_SNAKE_CASE
            return {_camel_to_upper_snake(k): v for k, v in task_data.items()}

        if entity_type == "call":
            # voximplant has no .get method; filter by CALL_ID
            records = await self._get_calls({"CALL_ID": entity_id})
            if records:
                return records[0]
            return {}

        if entity_type in ["stage_history_deal", "stage_history_lead"]:
            # stage_history has no .get method; filter by ID
            records = await self._get_stage_history(entity_type, {"ID": entity_id})
            if records:
                return records[0]
            return {}

        method = f"crm.{entity_type}.get"
        items = {"ID": entity_id, "select": ["*", "UF_*"]}
        return await self._call(method, items=items)

    async def get_entity_fields(self, entity_type: str) -> dict[str, Any]:
        """Get field definitions for an entity type.

        Args:
            entity_type: Entity type (deal, contact, lead, company, user, task, stage_history_*)

        Returns:
            Field definitions in format {FIELD: {type, title, isMultiple, isRequired}}
        """
        if entity_type == "user":
            return self._get_user_field_definitions()

        if entity_type == "call":
            return self._get_call_field_definitions()

        if entity_type in ["stage_history_deal", "stage_history_lead"]:
            return self._get_stage_history_field_definitions()

        if entity_type == "task":
            result = await self._call("tasks.task.getFields")
            # Result may be {"fields": {...}} or the fields dict directly
            if isinstance(result, dict) and "fields" in result:
                return result["fields"]
            return result

        method = f"crm.{entity_type}.fields"
        return await self._call(method)

    @staticmethod
    def _get_user_field_definitions() -> dict[str, Any]:
        """Build CRM-compatible field definitions from USER_FIELD_TYPES.

        user.fields returns flat {FIELD: description} without type metadata,
        so we use a predefined mapping to construct proper field definitions.
        """
        fields: dict[str, Any] = {}
        for field_name, field_type in USER_FIELD_TYPES.items():
            fields[field_name] = {
                "type": field_type,
                "title": field_name,
                "isMultiple": False,
                "isRequired": field_name == "ID",
            }
        return fields

    @staticmethod
    def _get_call_field_definitions() -> dict[str, Any]:
        """Build CRM-compatible field definitions from CALL_FIELD_TYPES.

        voximplant.statistic.get has no .fields method,
        so we use a predefined mapping to construct proper field definitions.
        """
        fields: dict[str, Any] = {}
        for field_name, field_type in CALL_FIELD_TYPES.items():
            fields[field_name] = {
                "type": field_type,
                "title": field_name,
                "isMultiple": False,
                "isRequired": field_name == "CALL_ID",
            }
        return fields

    @staticmethod
    def _get_stage_history_field_definitions() -> dict[str, Any]:
        """Build CRM-compatible field definitions from STAGE_HISTORY_FIELD_TYPES.

        crm.stagehistory.list has no .fields method,
        so we use a predefined mapping to construct proper field definitions.
        """
        fields: dict[str, Any] = {}
        for field_name, field_type in STAGE_HISTORY_FIELD_TYPES.items():
            fields[field_name] = {
                "type": field_type,
                "title": field_name,
                "isMultiple": False,
                "isRequired": field_name == "ID",
            }
        return fields

    async def get_userfields(self, entity_type: str) -> list[dict[str, Any]]:
        """Get user field definitions for an entity type.

        Args:
            entity_type: Entity type (deal, contact, lead, company, user, task, stage_history_*)

        Returns:
            List of user field definitions
        """
        if entity_type == "user":
            params = {"FILTER": {">ID": 0, "LANG": "ru"}}
            return await self.get_all("user.userfield.list", params)

        if entity_type == "call":
            # Voximplant doesn't support UF_* fields
            return []

        if entity_type in ["stage_history_deal", "stage_history_lead"]:
            # Stage history doesn't support UF_* fields
            return []

        if entity_type == "task":
            # Tasks don't have a separate userfield.list;
            # UF fields are included in tasks.task.getFields response
            return []

        method = f"crm.{entity_type}.userfield.list"
        params = {"FILTER": {">ID": 0, "LANG": "ru"}}
        return await self.get_all(method, params)

    async def register_webhook(
        self,
        event: str,
        handler_url: str,
    ) -> bool:
        """Register a webhook handler for a Bitrix event.

        Args:
            event: Event name (e.g., ONCRMDEALUPDATE)
            handler_url: URL to receive webhook calls

        Returns:
            True if registration successful
        """
        method = "event.bind"
        items = {
            "EVENT": event,
            "HANDLER": handler_url,
        }

        try:
            await self._call(method, items=items)
            logger.info("Webhook registered", event=event, handler_url=handler_url)
            return True
        except BitrixAPIError as e:
            logger.error("Failed to register webhook", event=event, error=str(e))
            return False

    async def unregister_webhook(
        self,
        event: str,
        handler_url: str,
    ) -> bool:
        """Unregister a webhook handler.

        Args:
            event: Event name
            handler_url: Handler URL to unregister

        Returns:
            True if unregistration successful
        """
        method = "event.unbind"
        items = {
            "EVENT": event,
            "HANDLER": handler_url,
        }

        try:
            await self._call(method, items=items)
            logger.info("Webhook unregistered", event=event, handler_url=handler_url)
            return True
        except BitrixAPIError as e:
            logger.error("Failed to unregister webhook", event=event, error=str(e))
            return False

    async def get_registered_webhooks(self) -> list[dict[str, Any]]:
        """Get list of registered webhooks.

        Returns:
            List of registered event handlers
        """
        method = "event.get"
        return await self._call(method)


# Dependency injection helper
def get_bitrix_client() -> BitrixClient:
    """Get BitrixClient instance for dependency injection."""
    return BitrixClient()
