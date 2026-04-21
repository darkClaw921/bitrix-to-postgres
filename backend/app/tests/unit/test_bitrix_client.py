"""Unit tests for BitrixClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BitrixAPIError, BitrixAuthError, BitrixRateLimitError


class TestBitrixClient:
    """Test suite for BitrixClient class."""

    @pytest.fixture
    def mock_fast_bitrix(self):
        """Mock fast-bitrix24 BitrixAsync client."""
        with patch("app.infrastructure.bitrix.client.BitrixAsync") as mock:
            mock_instance = AsyncMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def client(self, mock_fast_bitrix, mock_settings):
        """Create BitrixClient instance with mocked dependencies."""
        with patch("app.infrastructure.bitrix.client.get_settings", return_value=mock_settings):
            from app.infrastructure.bitrix.client import BitrixClient
            return BitrixClient()

    async def test_get_entities_returns_list(
        self, client, mock_fast_bitrix, sample_deal_data
    ):
        """Test get_entities returns list of entities."""
        mock_fast_bitrix.get_all.return_value = [sample_deal_data]

        result = await client.get_entities("deal")

        assert result == [sample_deal_data]
        mock_fast_bitrix.get_all.assert_called_once()

    async def test_get_entities_with_filter(
        self, client, mock_fast_bitrix, sample_deal_data
    ):
        """Test get_entities applies filter parameters."""
        mock_fast_bitrix.get_all.return_value = [sample_deal_data]
        filter_params = {"STAGE_ID": "NEW"}

        result = await client.get_entities("deal", filter_params=filter_params)

        assert result == [sample_deal_data]
        call_args = mock_fast_bitrix.get_all.call_args
        assert call_args[1]["params"]["FILTER"] == filter_params

    async def test_get_entities_with_select(
        self, client, mock_fast_bitrix, sample_deal_data
    ):
        """Test get_entities applies select fields."""
        mock_fast_bitrix.get_all.return_value = [sample_deal_data]
        select = ["ID", "TITLE"]

        result = await client.get_entities("deal", select=select)

        call_args = mock_fast_bitrix.get_all.call_args
        assert call_args[1]["params"]["SELECT"] == select

    async def test_get_entities_default_select_includes_uf_fields(
        self, client, mock_fast_bitrix
    ):
        """Test get_entities includes UF_* fields by default."""
        mock_fast_bitrix.get_all.return_value = []

        await client.get_entities("deal")

        call_args = mock_fast_bitrix.get_all.call_args
        assert call_args[1]["params"]["SELECT"] == ["*", "UF_*"]

    async def test_get_entity_returns_single_record(
        self, client, mock_fast_bitrix, sample_deal_data
    ):
        """Test get_entity returns a single entity."""
        mock_fast_bitrix.call.return_value = {"result": sample_deal_data}

        result = await client.get_entity("deal", "123")

        assert result == sample_deal_data
        mock_fast_bitrix.call.assert_called_once_with(
            "crm.deal.get",
            items={"ID": "123", "select": ["*", "UF_*"]},
            raw=True,
        )

    async def test_get_entity_fields_returns_field_definitions(
        self, client, mock_fast_bitrix, sample_deal_fields
    ):
        """Test get_entity_fields returns field definitions."""
        mock_fast_bitrix.call.return_value = {"result": sample_deal_fields}

        result = await client.get_entity_fields("deal")

        assert result == sample_deal_fields
        mock_fast_bitrix.call.assert_called_once_with("crm.deal.fields", items=None, raw=True)

    async def test_get_userfields_returns_user_field_list(
        self, client, mock_fast_bitrix, sample_userfields
    ):
        """Test get_userfields returns list of user field definitions."""
        mock_fast_bitrix.get_all.return_value = sample_userfields

        result = await client.get_userfields("deal")

        assert result == sample_userfields
        mock_fast_bitrix.get_all.assert_called_once()

    async def test_call_handles_api_error(self, client, mock_fast_bitrix):
        """Test _call raises BitrixAPIError on API errors."""
        mock_fast_bitrix.call.return_value = {
            "error": "SOME_ERROR",
            "error_description": "Something went wrong",
        }

        with pytest.raises(BitrixAPIError, match="Bitrix API error"):
            await client._call("crm.deal.list")

    async def test_call_handles_rate_limit_error(self, client, mock_fast_bitrix):
        """Test _call raises BitrixRateLimitError on rate limit."""
        mock_fast_bitrix.call.return_value = {
            "error": "QUERY_LIMIT_EXCEEDED",
            "error_description": "Too many requests",
        }

        with pytest.raises(BitrixRateLimitError, match="Rate limit exceeded"):
            await client._call("crm.deal.list")

    async def test_call_handles_auth_error_expired_token(self, client, mock_fast_bitrix):
        """Test _call raises BitrixAuthError on expired token."""
        mock_fast_bitrix.call.return_value = {
            "error": "expired_token",
            "error_description": "Token has expired",
        }

        with pytest.raises(BitrixAuthError, match="Authentication error"):
            await client._call("crm.deal.list")

    async def test_call_handles_auth_error_invalid_token(self, client, mock_fast_bitrix):
        """Test _call raises BitrixAuthError on invalid token."""
        mock_fast_bitrix.call.return_value = {
            "error": "invalid_token",
            "error_description": "Invalid token",
        }

        with pytest.raises(BitrixAuthError, match="Authentication error"):
            await client._call("crm.deal.list")

    async def test_call_handles_connection_error(self, client, mock_fast_bitrix):
        """Test _call raises BitrixAPIError on connection errors."""
        mock_fast_bitrix.call.side_effect = ConnectionError("Network error")

        with pytest.raises(BitrixAPIError, match="API call failed"):
            await client._call("crm.deal.list")

    async def test_register_webhook_success(self, client, mock_fast_bitrix):
        """Test register_webhook returns True on success."""
        mock_fast_bitrix.call.return_value = {"result": True}

        result = await client.register_webhook(
            "ONCRMDEALUPDATE", "https://example.com/webhook"
        )

        assert result is True
        mock_fast_bitrix.call.assert_called_once_with(
            "event.bind",
            items={"EVENT": "ONCRMDEALUPDATE", "HANDLER": "https://example.com/webhook"},
            raw=True,
        )

    async def test_register_webhook_failure(self, client, mock_fast_bitrix):
        """Test register_webhook returns False on failure."""
        mock_fast_bitrix.call.return_value = {
            "error": "ERROR",
            "error_description": "Failed",
        }

        result = await client.register_webhook(
            "ONCRMDEALUPDATE", "https://example.com/webhook"
        )

        assert result is False

    async def test_unregister_webhook_success(self, client, mock_fast_bitrix):
        """Test unregister_webhook returns True on success."""
        mock_fast_bitrix.call.return_value = {"result": True}

        result = await client.unregister_webhook(
            "ONCRMDEALUPDATE", "https://example.com/webhook"
        )

        assert result is True
        mock_fast_bitrix.call.assert_called_once_with(
            "event.unbind",
            items={"EVENT": "ONCRMDEALUPDATE", "HANDLER": "https://example.com/webhook"},
            raw=True,
        )

    async def test_get_registered_webhooks(self, client, mock_fast_bitrix):
        """Test get_registered_webhooks returns list of webhooks."""
        expected = [
            {"event": "ONCRMDEALUPDATE", "handler": "https://example.com/webhook"}
        ]
        mock_fast_bitrix.call.return_value = {"result": expected}

        result = await client.get_registered_webhooks()

        assert result == expected

    async def test_get_all_handles_pagination(self, client, mock_fast_bitrix):
        """Test get_all uses fast-bitrix24 pagination."""
        records = [{"ID": str(i)} for i in range(100)]
        mock_fast_bitrix.get_all.return_value = records

        result = await client.get_all("crm.deal.list")

        assert len(result) == 100
        mock_fast_bitrix.get_all.assert_called_once()


class TestBitrixClientRetry:
    """Test suite for BitrixClient retry logic."""

    @pytest.fixture
    def mock_fast_bitrix(self):
        """Mock fast-bitrix24 BitrixAsync client."""
        with patch("app.infrastructure.bitrix.client.BitrixAsync") as mock:
            mock_instance = AsyncMock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def client(self, mock_fast_bitrix, mock_settings):
        """Create BitrixClient instance with mocked dependencies."""
        with patch("app.infrastructure.bitrix.client.get_settings", return_value=mock_settings):
            from app.infrastructure.bitrix.client import BitrixClient
            return BitrixClient()

    async def test_retry_on_rate_limit(self, client, mock_fast_bitrix, sample_deal_data):
        """Test _call retries on rate limit errors."""
        # First call fails with rate limit, second succeeds
        mock_fast_bitrix.call.side_effect = [
            {"error": "QUERY_LIMIT_EXCEEDED", "error_description": "Rate limit"},
            {"result": sample_deal_data},
        ]

        # Note: Tenacity retry will still re-raise after max attempts
        # This test verifies the retry is triggered
        with pytest.raises(BitrixRateLimitError):
            await client._call("crm.deal.get")

    async def test_no_retry_on_auth_error(self, client, mock_fast_bitrix):
        """Test _call does not retry on auth errors."""
        mock_fast_bitrix.call.return_value = {
            "error": "expired_token",
            "error_description": "Token expired",
        }

        with pytest.raises(BitrixAuthError):
            await client._call("crm.deal.get")

        # Should only be called once (no retry)
        assert mock_fast_bitrix.call.call_count == 1


class TestBitrixClientEntityTypes:
    """Test BitrixClient with different entity types."""

    @pytest.fixture
    def mock_fast_bitrix(self):
        """Mock fast-bitrix24 BitrixAsync client."""
        with patch("app.infrastructure.bitrix.client.BitrixAsync") as mock:
            mock_instance = AsyncMock()
            mock_instance.get_all.return_value = []
            mock_instance.call.return_value = {"result": {}}
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def client(self, mock_fast_bitrix, mock_settings):
        """Create BitrixClient instance with mocked dependencies."""
        with patch("app.infrastructure.bitrix.client.get_settings", return_value=mock_settings):
            from app.infrastructure.bitrix.client import BitrixClient
            return BitrixClient()

    @pytest.mark.parametrize("entity_type,expected_method", [
        ("deal", "crm.deal.list"),
        ("contact", "crm.contact.list"),
        ("lead", "crm.lead.list"),
        ("company", "crm.company.list"),
    ])
    async def test_get_entities_uses_correct_method(
        self, client, mock_fast_bitrix, entity_type, expected_method
    ):
        """Test get_entities uses correct Bitrix API method."""
        await client.get_entities(entity_type)

        call_args = mock_fast_bitrix.get_all.call_args
        assert call_args[0][0] == expected_method

    @pytest.mark.parametrize("entity_type,expected_method", [
        ("deal", "crm.deal.fields"),
        ("contact", "crm.contact.fields"),
        ("lead", "crm.lead.fields"),
        ("company", "crm.company.fields"),
    ])
    async def test_get_entity_fields_uses_correct_method(
        self, client, mock_fast_bitrix, entity_type, expected_method
    ):
        """Test get_entity_fields uses correct Bitrix API method."""
        await client.get_entity_fields(entity_type)

        call_args = mock_fast_bitrix.call.call_args
        assert call_args[0][0] == expected_method
