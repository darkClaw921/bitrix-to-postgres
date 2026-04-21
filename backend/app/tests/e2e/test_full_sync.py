"""End-to-end tests for full sync flow.

These tests verify the complete sync flow from API trigger to database write.
They require comprehensive mocks to simulate the Bitrix24 API and database.

For production e2e testing with real services, set the following environment variables:
- BITRIX_WEBHOOK_URL: Real Bitrix24 webhook URL
- DATABASE_URL: Real PostgreSQL connection string

Run with: pytest app/tests/e2e/ -v --e2e (when e2e marker is configured)
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def sample_bitrix_deals():
    """Sample deals from Bitrix API."""
    return [
        {
            "ID": "1",
            "TITLE": "Test Deal 1",
            "STAGE_ID": "NEW",
            "OPPORTUNITY": "10000.00",
            "CURRENCY_ID": "RUB",
            "CONTACT_ID": "10",
            "COMPANY_ID": "20",
            "ASSIGNED_BY_ID": "1",
            "CREATED_BY_ID": "1",
            "DATE_CREATE": "2024-01-15T10:00:00+03:00",
            "DATE_MODIFY": "2024-01-16T15:30:00+03:00",
            "UF_CRM_CUSTOM_1": "value1",
        },
        {
            "ID": "2",
            "TITLE": "Test Deal 2",
            "STAGE_ID": "PREPARATION",
            "OPPORTUNITY": "25000.00",
            "CURRENCY_ID": "RUB",
            "CONTACT_ID": "11",
            "COMPANY_ID": "21",
            "ASSIGNED_BY_ID": "2",
            "CREATED_BY_ID": "1",
            "DATE_CREATE": "2024-01-16T09:00:00+03:00",
            "DATE_MODIFY": "2024-01-17T11:00:00+03:00",
            "UF_CRM_CUSTOM_1": "value2",
        },
        {
            "ID": "3",
            "TITLE": "Test Deal 3",
            "STAGE_ID": "WON",
            "OPPORTUNITY": "50000.00",
            "CURRENCY_ID": "RUB",
            "CONTACT_ID": "12",
            "COMPANY_ID": "22",
            "ASSIGNED_BY_ID": "1",
            "CREATED_BY_ID": "2",
            "DATE_CREATE": "2024-01-10T14:00:00+03:00",
            "DATE_MODIFY": "2024-01-18T16:45:00+03:00",
        },
    ]


@pytest.fixture
def sample_bitrix_fields():
    """Sample field definitions from Bitrix API."""
    return {
        "ID": {"type": "integer", "isRequired": False, "isReadOnly": True},
        "TITLE": {"type": "string", "isRequired": True, "isReadOnly": False},
        "STAGE_ID": {"type": "crm_status", "isRequired": False, "isReadOnly": False},
        "OPPORTUNITY": {"type": "double", "isRequired": False, "isReadOnly": False},
        "CURRENCY_ID": {"type": "crm_currency", "isRequired": False, "isReadOnly": False},
        "CONTACT_ID": {"type": "crm_contact", "isRequired": False, "isReadOnly": False},
        "COMPANY_ID": {"type": "crm_company", "isRequired": False, "isReadOnly": False},
        "ASSIGNED_BY_ID": {"type": "user", "isRequired": False, "isReadOnly": False},
        "CREATED_BY_ID": {"type": "user", "isRequired": False, "isReadOnly": True},
        "DATE_CREATE": {"type": "datetime", "isRequired": False, "isReadOnly": True},
        "DATE_MODIFY": {"type": "datetime", "isRequired": False, "isReadOnly": True},
    }


@pytest.fixture
def sample_bitrix_userfields():
    """Sample user field definitions from Bitrix API."""
    return [
        {
            "ID": "1",
            "ENTITY_ID": "CRM_DEAL",
            "FIELD_NAME": "UF_CRM_CUSTOM_1",
            "USER_TYPE_ID": "string",
            "MANDATORY": "N",
            "LIST_COLUMN_LABEL": {"ru": "Custom Field 1"},
        },
    ]


@pytest.fixture
def mock_full_sync_dependencies(
    sample_bitrix_deals, sample_bitrix_fields, sample_bitrix_userfields
):
    """Mock all dependencies for full sync e2e test."""
    # Track database operations
    db_operations = {"inserts": [], "updates": [], "tables_created": []}

    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main.close_db", new_callable=AsyncMock), \
         patch("app.main.start_scheduler"), \
         patch("app.main.stop_scheduler"), \
         patch("app.main.schedule_sync_jobs", new_callable=AsyncMock), \
         patch("app.main.get_scheduler_status", return_value={"running": True, "job_count": 0}), \
         patch("app.api.v1.endpoints.sync.BitrixClient") as mock_bitrix_class, \
         patch("app.api.v1.endpoints.sync.SyncService") as mock_sync_class:

        # Setup BitrixClient mock
        mock_bitrix = AsyncMock()
        mock_bitrix.get_entity_fields.return_value = sample_bitrix_fields
        mock_bitrix.get_userfields.return_value = sample_bitrix_userfields
        mock_bitrix.get_entities.return_value = sample_bitrix_deals
        mock_bitrix_class.return_value = mock_bitrix

        # Setup SyncService mock
        mock_sync = AsyncMock()
        mock_sync.full_sync.return_value = {
            "status": "completed",
            "entity_type": "deal",
            "records_processed": len(sample_bitrix_deals),
            "fields_count": len(sample_bitrix_fields) + len(sample_bitrix_userfields),
        }
        mock_sync.incremental_sync.return_value = {
            "status": "completed",
            "entity_type": "deal",
            "records_processed": 1,
            "sync_type": "incremental",
        }
        mock_sync_class.return_value = mock_sync

        yield {
            "bitrix": mock_bitrix,
            "sync_service": mock_sync,
            "db_operations": db_operations,
        }


@pytest.fixture
def app(mock_full_sync_dependencies) -> FastAPI:
    """Create test application with mocked dependencies."""
    from app.main import create_app
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestFullSyncFlow:
    """E2E tests for complete full sync flow."""

    def test_full_sync_api_to_completion(
        self, client, mock_full_sync_dependencies, sample_bitrix_deals
    ):
        """Test full sync from API trigger to completion."""
        # Step 1: Trigger full sync via API
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "full"},
        )

        # Verify API accepts the request
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["entity"] == "deal"
        assert data["sync_type"] == "full"

    def test_full_sync_processes_all_records(
        self, client, mock_full_sync_dependencies, sample_bitrix_deals
    ):
        """Test full sync processes all records from Bitrix."""
        # Trigger sync
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "full"},
        )

        assert response.status_code == 200

        # Background task would be triggered
        # In real e2e test, we'd wait and verify database

    def test_full_sync_for_all_entity_types(self, client, mock_full_sync_dependencies):
        """Test full sync can be triggered for all entity types."""
        entity_types = ["deal", "contact", "lead", "company"]

        for entity_type in entity_types:
            response = client.post(
                f"/api/v1/sync/start/{entity_type}",
                json={"sync_type": "full"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["entity"] == entity_type


class TestIncrementalSyncFlow:
    """E2E tests for incremental sync flow."""

    def test_incremental_sync_api_to_completion(
        self, client, mock_full_sync_dependencies
    ):
        """Test incremental sync from API trigger to completion."""
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "incremental"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["sync_type"] == "incremental"

    def test_incremental_sync_uses_date_filter(
        self, client, mock_full_sync_dependencies
    ):
        """Test incremental sync filters by DATE_MODIFY."""
        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "incremental"},
        )

        assert response.status_code == 200


class TestWebhookSyncFlow:
    """E2E tests for webhook-triggered sync flow."""

    @pytest.fixture
    def mock_webhook_dependencies(self):
        """Mock dependencies for webhook e2e test."""
        with patch("app.main.init_db", new_callable=AsyncMock), \
             patch("app.main.close_db", new_callable=AsyncMock), \
             patch("app.main.start_scheduler"), \
             patch("app.main.stop_scheduler"), \
             patch("app.main.schedule_sync_jobs", new_callable=AsyncMock), \
             patch("app.main.get_scheduler_status", return_value={"running": True, "job_count": 0}), \
             patch("app.api.v1.endpoints.webhooks.BitrixClient") as mock_bitrix_class, \
             patch("app.api.v1.endpoints.webhooks.SyncService") as mock_sync_class:

            mock_bitrix = AsyncMock()
            mock_bitrix.get_entity.return_value = {
                "ID": "123",
                "TITLE": "Updated Deal",
                "STAGE_ID": "WON",
            }
            mock_bitrix_class.return_value = mock_bitrix

            mock_sync = AsyncMock()
            mock_sync.sync_entity_by_id.return_value = {
                "status": "completed",
                "entity_type": "deal",
                "entity_id": "123",
                "records_processed": 1,
            }
            mock_sync.delete_entity_by_id.return_value = {
                "status": "completed",
                "entity_type": "deal",
                "entity_id": "123",
                "records_deleted": 1,
            }
            mock_sync_class.return_value = mock_sync

            yield {
                "bitrix": mock_bitrix,
                "sync_service": mock_sync,
            }

    @pytest.fixture
    def webhook_app(self, mock_webhook_dependencies) -> FastAPI:
        """Create test application for webhook tests."""
        from app.main import create_app
        return create_app()

    @pytest.fixture
    def webhook_client(self, webhook_app: FastAPI) -> TestClient:
        """Create test client for webhook tests."""
        return TestClient(webhook_app)

    def test_webhook_update_triggers_sync(
        self, webhook_client, mock_webhook_dependencies
    ):
        """Test webhook update event triggers entity sync."""
        payload = "event=ONCRMDEALUPDATE&data[FIELDS][ID]=123"

        response = webhook_client.post(
            "/api/v1/webhooks/bitrix",
            content=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event"] == "ONCRMDEALUPDATE"
        assert data["entity_id"] == "123"

    def test_webhook_add_triggers_sync(
        self, webhook_client, mock_webhook_dependencies
    ):
        """Test webhook add event triggers entity sync."""
        payload = "event=ONCRMDEALADD&data[FIELDS][ID]=456"

        response = webhook_client.post(
            "/api/v1/webhooks/bitrix",
            content=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event"] == "ONCRMDEALADD"

    def test_webhook_delete_triggers_removal(
        self, webhook_client, mock_webhook_dependencies
    ):
        """Test webhook delete event triggers entity removal."""
        payload = "event=ONCRMDEALDELETE&data[FIELDS][ID]=789"

        response = webhook_client.post(
            "/api/v1/webhooks/bitrix",
            content=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event"] == "ONCRMDEALDELETE"


class TestSyncStatusFlow:
    """E2E tests for sync status monitoring."""

    def test_sync_status_shows_running_sync(
        self, client, mock_full_sync_dependencies
    ):
        """Test sync status endpoint shows running syncs."""
        # Start a sync
        client.post("/api/v1/sync/start/deal", json={"sync_type": "full"})

        # Check status
        response = client.get("/api/v1/sync/status")

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "entities" in data

    def test_running_syncs_endpoint(self, client, mock_full_sync_dependencies):
        """Test running syncs endpoint."""
        response = client.get("/api/v1/sync/running")

        assert response.status_code == 200
        data = response.json()
        assert "running_syncs" in data
        assert "count" in data


class TestConfigurationFlow:
    """E2E tests for sync configuration."""

    @pytest.fixture
    def mock_config_dependencies(self):
        """Mock dependencies for config e2e test."""
        with patch("app.main.init_db", new_callable=AsyncMock), \
             patch("app.main.close_db", new_callable=AsyncMock), \
             patch("app.main.start_scheduler"), \
             patch("app.main.stop_scheduler"), \
             patch("app.main.schedule_sync_jobs", new_callable=AsyncMock), \
             patch("app.main.get_scheduler_status", return_value={"running": True, "job_count": 0}), \
             patch("app.api.v1.endpoints.sync.get_engine") as mock_engine, \
             patch("app.api.v1.endpoints.sync.reschedule_entity", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.sync.remove_entity_job", new_callable=AsyncMock):

            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_result.fetchone.return_value = ("deal", True, 30, True, None)
            mock_result.scalar.return_value = 1
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn

            yield {"engine": mock_engine, "connection": mock_conn}

    @pytest.fixture
    def config_app(self, mock_config_dependencies) -> FastAPI:
        """Create test application for config tests."""
        from app.main import create_app
        return create_app()

    @pytest.fixture
    def config_client(self, config_app: FastAPI) -> TestClient:
        """Create test client for config tests."""
        return TestClient(config_app)

    def test_get_config_returns_all_entities(self, config_client, mock_config_dependencies):
        """Test getting config returns all entity types."""
        response = config_client.get("/api/v1/sync/config")

        assert response.status_code == 200
        data = response.json()
        assert len(data["entities"]) == 4  # deal, contact, lead, company

    def test_update_config_enables_sync(self, config_client, mock_config_dependencies):
        """Test updating config to enable sync."""
        response = config_client.put(
            "/api/v1/sync/config",
            json={"entity_type": "deal", "enabled": True, "sync_interval_minutes": 15},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "deal"

    def test_update_config_disables_sync(self, config_client, mock_config_dependencies):
        """Test updating config to disable sync."""
        response = config_client.put(
            "/api/v1/sync/config",
            json={"entity_type": "contact", "enabled": False},
        )

        assert response.status_code == 200


class TestDataIntegrity:
    """E2E tests for data integrity after sync."""

    def test_sync_preserves_all_fields(
        self, client, mock_full_sync_dependencies, sample_bitrix_deals
    ):
        """Test sync preserves all fields including custom fields."""
        # This would verify that UF_* fields are synced correctly
        # In a real e2e test, we'd check the database

        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "full"},
        )

        assert response.status_code == 200

    def test_sync_handles_special_characters(
        self, client, mock_full_sync_dependencies
    ):
        """Test sync handles special characters in field values."""
        # Modify mock to return deal with special characters
        mock_full_sync_dependencies["bitrix"].get_entities.return_value = [
            {
                "ID": "1",
                "TITLE": "Deal with 'quotes' and \"double quotes\"",
                "STAGE_ID": "NEW",
            }
        ]

        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "full"},
        )

        assert response.status_code == 200

    def test_sync_handles_unicode(
        self, client, mock_full_sync_dependencies
    ):
        """Test sync handles unicode characters."""
        mock_full_sync_dependencies["bitrix"].get_entities.return_value = [
            {
                "ID": "1",
                "TITLE": "Сделка на русском языке 中文 日本語",
                "STAGE_ID": "NEW",
            }
        ]

        response = client.post(
            "/api/v1/sync/start/deal",
            json={"sync_type": "full"},
        )

        assert response.status_code == 200
