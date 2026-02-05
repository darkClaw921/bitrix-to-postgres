"""Bitrix24 API client with retry and rate limiting support."""

from typing import Any, AsyncIterator, TypeVar

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
    BitrixRateLimitError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


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
        except Exception as e:
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
        except Exception as e:
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
            entity_type: Entity type (deal, contact, lead, company)
            filter_params: Filter parameters
            select: Fields to select (defaults to all including UF_*)

        Returns:
            List of entities
        """
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

    async def get_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """Get a single entity by ID.

        Args:
            entity_type: Entity type (deal, contact, lead, company)
            entity_id: Entity ID

        Returns:
            Entity data
        """
        method = f"crm.{entity_type}.get"
        items = {"ID": entity_id, "select": ["*", "UF_*"]}
        return await self._call(method, items=items)

    async def get_entity_fields(self, entity_type: str) -> dict[str, Any]:
        """Get field definitions for an entity type.

        Args:
            entity_type: Entity type (deal, contact, lead, company)

        Returns:
            Field definitions from crm.{entity}.fields
        """
        method = f"crm.{entity_type}.fields"
        return await self._call(method)

    async def get_userfields(self, entity_type: str) -> list[dict[str, Any]]:
        """Get user field definitions for an entity type.

        Args:
            entity_type: Entity type (deal, contact, lead, company)

        Returns:
            List of user field definitions from crm.{entity}.userfield.list
        """
        method = f"crm.{entity_type}.userfield.list"
        params = {"FILTER": {">ID": 0}}
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
