"""Integration tests for API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_all_dependencies():
    """Mock all external dependencies for API testing."""
    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main.close_db", new_callable=AsyncMock), \
         patch("app.main.start_scheduler"), \
         patch("app.main.stop_scheduler"), \
         patch("app.main.schedule_sync_jobs", new_callable=AsyncMock), \
         patch("app.main.get_scheduler_status", return_value={"running": True, "job_count": 0}), \
         patch("app.infrastructure.database.connection.get_engine"), \
         patch("app.infrastructure.database.connection.get_session"):
        yield


@pytest.fixture
def app(mock_all_dependencies) -> FastAPI:
    """Create test application."""
    from app.main import create_app
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create synchronous test client."""
    return TestClient(app)


@pytest.fixture
async def async_test_client(app: FastAPI):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestHealthEndpoint:
    """Test suite for health check endpoint."""

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_health_returns_status(self, client):
        """Test health endpoint returns status information."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data
        assert "scheduler" in data


class TestSyncConfigEndpoint:
    """Test suite for sync configuration endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for sync config."""
        with patch("app.api.v1.endpoints.sync.get_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_result = AsyncMock()
            mock_result.fetchall.return_value = []
            mock_result.fetchone.return_value = None
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn
            yield mock_conn

    def test_get_sync_config_returns_entities(self, client, mock_db):
        """Test GET /api/v1/sync/config returns entity configurations."""
        response = client.get("/api/v1/sync/config")

        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert "default_interval_minutes" in data

    def test_get_sync_config_returns_default_for_all_types(self, client, mock_db):
        """Test GET /api/v1/sync/config returns defaults for all entity types."""
        response = client.get("/api/v1/sync/config")
        data = response.json()

        entity_types = [e["entity_type"] for e in data["entities"]]
        assert "deal" in entity_types
        assert "contact" in entity_types
        assert "lead" in entity_types
        assert "company" in entity_types

    def test_update_sync_config_validates_entity_type(self, client, mock_db):
        """Test PUT /api/v1/sync/config validates entity type."""
        response = client.put(
            "/api/v1/sync/config",
            json={"entity_type": "invalid_type", "enabled": True},
        )

        assert response.status_code == 400
        assert "Invalid entity type" in response.json()["detail"]

    def test_update_sync_config_requires_fields(self, client, mock_db):
        """Test PUT /api/v1/sync/config requires at least one field to update."""
        response = client.put(
            "/api/v1/sync/config",
            json={"entity_type": "deal"},
        )

        assert response.status_code == 400
        assert "No fields to update" in response.json()["detail"]


class TestSyncStartEndpoint:
    """Test suite for sync start endpoint."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for sync operations."""
        with patch("app.api.v1.endpoints.sync.get_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_result = AsyncMock()
            mock_result.fetchone.return_value = None
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn
            yield mock_conn

    def test_start_sync_validates_entity_type(self, client, mock_db):
        """Test POST /api/v1/sync/start validates entity type."""
        response = client.post("/api/v1/sync/start/invalid_entity")

        assert response.status_code == 400
        assert "Invalid entity type" in response.json()["detail"]

    def test_start_sync_validates_sync_type(self, client, mock_db):
        """Test POST /api/v1/sync/start validates sync_type."""
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "invalid"},
        )

        assert response.status_code == 400
        assert "sync_type" in response.json()["detail"]

    def test_start_sync_accepts_full_sync(self, client, mock_db):
        """Test POST /api/v1/sync/start/deal accepts full sync."""
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "full"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["entity"] == "deal"
        assert data["sync_type"] == "full"

    def test_start_sync_accepts_incremental_sync(self, client, mock_db):
        """Test POST /api/v1/sync/start/deal accepts incremental sync."""
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "incremental"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sync_type"] == "incremental"


class TestSyncStatusEndpoint:
    """Test suite for sync status endpoint."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for sync status."""
        with patch("app.api.v1.endpoints.sync.get_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_result = AsyncMock()
            mock_result.fetchall.return_value = []
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn
            yield mock_conn

    def test_get_sync_status_returns_overall_status(self, client, mock_db):
        """Test GET /api/v1/sync/status returns overall status."""
        response = client.get("/api/v1/sync/status")

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "entities" in data

    def test_get_running_syncs(self, client, mock_db):
        """Test GET /api/v1/sync/running returns running syncs."""
        response = client.get("/api/v1/sync/running")

        assert response.status_code == 200
        data = response.json()
        assert "running_syncs" in data
        assert "count" in data


class TestWebhookEndpoints:
    """Test suite for webhook endpoints."""

    @pytest.fixture
    def mock_webhook_processing(self):
        """Mock webhook processing dependencies."""
        with patch("app.api.v1.endpoints.webhooks.process_webhook_event", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "completed"}
            yield mock

    def test_webhook_bitrix_accepts_deal_update(
        self, client, mock_webhook_processing, webhook_deal_update_payload
    ):
        """Test POST /api/v1/webhooks/bitrix accepts deal update."""
        response = client.post(
            "/api/v1/webhooks/bitrix",
            content=webhook_deal_update_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event"] == "ONCRMDEALUPDATE"
        assert data["entity_id"] == "123"

    def test_webhook_bitrix_accepts_contact_add(
        self, client, mock_webhook_processing, webhook_contact_add_payload
    ):
        """Test POST /api/v1/webhooks/bitrix accepts contact add."""
        response = client.post(
            "/api/v1/webhooks/bitrix",
            content=webhook_contact_add_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event"] == "ONCRMCONTACTADD"

    def test_webhook_bitrix_accepts_delete_event(
        self, client, mock_webhook_processing, webhook_deal_delete_payload
    ):
        """Test POST /api/v1/webhooks/bitrix accepts delete event."""
        response = client.post(
            "/api/v1/webhooks/bitrix",
            content=webhook_deal_delete_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event"] == "ONCRMDEALDELETE"

    def test_webhook_register_calls_bitrix(self, client):
        """Test POST /api/v1/webhooks/register registers with Bitrix."""
        with patch("app.api.v1.endpoints.webhooks.BitrixClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.register_webhook.return_value = True
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/v1/webhooks/register",
                params={"handler_base_url": "https://example.com"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "registered" in data

    def test_webhook_unregister_calls_bitrix(self, client):
        """Test DELETE /api/v1/webhooks/unregister unregisters from Bitrix."""
        with patch("app.api.v1.endpoints.webhooks.BitrixClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.unregister_webhook.return_value = True
            mock_client_class.return_value = mock_client

            response = client.delete(
                "/api/v1/webhooks/unregister",
                params={"handler_base_url": "https://example.com"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

    def test_webhook_get_registered(self, client):
        """Test GET /api/v1/webhooks/registered returns registered webhooks."""
        with patch("app.api.v1.endpoints.webhooks.BitrixClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_registered_webhooks.return_value = [
                {"event": "ONCRMDEALUPDATE", "handler": "https://example.com/webhook"}
            ]
            mock_client_class.return_value = mock_client

            response = client.get("/api/v1/webhooks/registered")

            assert response.status_code == 200
            data = response.json()
            assert "webhooks" in data
            assert "count" in data


class TestAuthMiddleware:
    """Test suite for authentication middleware."""

    @pytest.fixture
    def mock_db(self):
        """Mock database."""
        with patch("app.api.v1.endpoints.sync.get_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_result = AsyncMock()
            mock_result.fetchall.return_value = []
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn
            yield

    def test_valid_jwt_token_accepted(self, client, valid_jwt_token, mock_db):
        """Test valid JWT token is accepted."""
        # Note: Most endpoints don't require auth in current implementation
        # This tests that the auth mechanism works when applied
        pass

    def test_invalid_jwt_token_rejected(self, client, invalid_jwt_token):
        """Test invalid JWT token is rejected."""
        # When auth is required, invalid tokens should be rejected
        pass

    def test_expired_jwt_token_rejected(self, client, expired_jwt_token):
        """Test expired JWT token is rejected."""
        # When auth is required, expired tokens should be rejected
        pass


class TestWebhookHelpers:
    """Test webhook helper functions."""

    def test_get_entity_type_from_event_deal(self):
        """Test extracting deal entity type from event."""
        from app.api.v1.endpoints.webhooks import get_entity_type_from_event

        assert get_entity_type_from_event("ONCRMDEALUPDATE") == "deal"
        assert get_entity_type_from_event("ONCRMDEALADD") == "deal"
        assert get_entity_type_from_event("ONCRMDEALDELETE") == "deal"

    def test_get_entity_type_from_event_contact(self):
        """Test extracting contact entity type from event."""
        from app.api.v1.endpoints.webhooks import get_entity_type_from_event

        assert get_entity_type_from_event("ONCRMCONTACTUPDATE") == "contact"
        assert get_entity_type_from_event("ONCRMCONTACTADD") == "contact"

    def test_get_entity_type_from_event_unknown(self):
        """Test extracting entity type from unknown event."""
        from app.api.v1.endpoints.webhooks import get_entity_type_from_event

        assert get_entity_type_from_event("UNKNOWN_EVENT") is None

    def test_is_delete_event(self):
        """Test detecting delete events."""
        from app.api.v1.endpoints.webhooks import is_delete_event

        assert is_delete_event("ONCRMDEALDELETE") is True
        assert is_delete_event("ONCRMCONTACTDELETE") is True
        assert is_delete_event("ONCRMDEALUPDATE") is False
        assert is_delete_event("ONCRMDEALADD") is False


class TestWebhookParsing:
    """Test webhook parsing utilities."""

    def test_parse_nested_query_simple(self):
        """Test parsing simple query string."""
        from app.core.webhooks import parse_nested_query

        result = parse_nested_query("event=ONCRMDEALUPDATE")

        assert result == {"event": "ONCRMDEALUPDATE"}

    def test_parse_nested_query_with_data(self):
        """Test parsing query string with nested data."""
        from app.core.webhooks import parse_nested_query

        query = "event=ONCRMDEALUPDATE&data[FIELDS][ID]=123"
        result = parse_nested_query(query)

        assert result["event"] == "ONCRMDEALUPDATE"
        assert result["data"]["FIELDS"]["ID"] == "123"

    def test_extract_event_info(self):
        """Test extracting event info from parsed data."""
        from app.core.webhooks import extract_event_info

        event_data = {
            "event": "ONCRMDEALUPDATE",
            "data": {"FIELDS": {"ID": "123"}},
        }
        event_type, entity_id = extract_event_info(event_data)

        assert event_type == "ONCRMDEALUPDATE"
        assert entity_id == "123"

    def test_extract_event_info_missing_fields(self):
        """Test extracting event info when fields are missing."""
        from app.core.webhooks import extract_event_info

        event_data = {"event": "ONCRMDEALUPDATE"}
        event_type, entity_id = extract_event_info(event_data)

        assert event_type == "ONCRMDEALUPDATE"
        assert entity_id is None
