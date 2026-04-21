"""Pytest configuration and fixtures."""

import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Set test environment variables before importing app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("BITRIX_WEBHOOK_URL", "https://test.bitrix24.ru/rest/1/test/")


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = MagicMock()
    settings.database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    settings.async_database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    settings.db_dialect = "postgresql"
    settings.bitrix_webhook_url = "https://test.bitrix24.ru/rest/1/test/"
    settings.sync_batch_size = 50
    settings.app_name = "Test App"
    settings.app_version = "1.0.0"
    settings.debug = True
    settings.port = 8080
    return settings


@pytest.fixture
def mock_bitrix_response():
    """Factory fixture for mocking Bitrix API responses."""
    def _create_response(data, error=None):
        if error:
            return {"error": error["code"], "error_description": error["message"]}
        return {"result": data}
    return _create_response


@pytest.fixture
def sample_deal_data():
    """Sample Bitrix deal data."""
    return {
        "ID": "123",
        "TITLE": "Test Deal",
        "STAGE_ID": "NEW",
        "OPPORTUNITY": "1000.00",
        "CURRENCY_ID": "RUB",
        "CONTACT_ID": "456",
        "COMPANY_ID": "789",
        "ASSIGNED_BY_ID": "1",
        "CREATED_BY_ID": "1",
        "DATE_CREATE": "2024-01-15T10:00:00+03:00",
        "DATE_MODIFY": "2024-01-16T15:30:00+03:00",
        "UF_CRM_CUSTOM": "custom_value",
    }


@pytest.fixture
def sample_contact_data():
    """Sample Bitrix contact data."""
    return {
        "ID": "456",
        "NAME": "John",
        "LAST_NAME": "Doe",
        "EMAIL": [{"VALUE": "john@example.com", "VALUE_TYPE": "WORK"}],
        "PHONE": [{"VALUE": "+79001234567", "VALUE_TYPE": "MOBILE"}],
        "ASSIGNED_BY_ID": "1",
        "DATE_CREATE": "2024-01-10T09:00:00+03:00",
        "DATE_MODIFY": "2024-01-15T12:00:00+03:00",
    }


@pytest.fixture
def sample_deal_fields():
    """Sample Bitrix deal field definitions."""
    return {
        "ID": {
            "type": "integer",
            "isRequired": False,
            "isReadOnly": True,
            "title": "ID",
        },
        "TITLE": {
            "type": "string",
            "isRequired": True,
            "isReadOnly": False,
            "title": "Название",
        },
        "STAGE_ID": {
            "type": "crm_status",
            "isRequired": False,
            "isReadOnly": False,
            "title": "Стадия",
        },
        "OPPORTUNITY": {
            "type": "double",
            "isRequired": False,
            "isReadOnly": False,
            "title": "Сумма",
        },
        "DATE_CREATE": {
            "type": "datetime",
            "isRequired": False,
            "isReadOnly": True,
            "title": "Дата создания",
        },
        "DATE_MODIFY": {
            "type": "datetime",
            "isRequired": False,
            "isReadOnly": True,
            "title": "Дата изменения",
        },
    }


@pytest.fixture
def sample_userfields():
    """Sample Bitrix user field definitions."""
    return [
        {
            "ID": "1",
            "ENTITY_ID": "CRM_DEAL",
            "FIELD_NAME": "UF_CRM_CUSTOM",
            "USER_TYPE_ID": "string",
            "XML_ID": None,
            "SORT": "100",
            "MANDATORY": "N",
            "SHOW_FILTER": "N",
            "SHOW_IN_LIST": "Y",
            "EDIT_IN_LIST": "Y",
            "IS_SEARCHABLE": "N",
            "SETTINGS": {"DEFAULT_VALUE": ""},
            "LIST_COLUMN_LABEL": {"ru": "Пользовательское поле"},
        },
        {
            "ID": "2",
            "ENTITY_ID": "CRM_DEAL",
            "FIELD_NAME": "UF_CRM_NUMBER",
            "USER_TYPE_ID": "double",
            "XML_ID": None,
            "SORT": "200",
            "MANDATORY": "N",
            "SETTINGS": {},
            "LIST_COLUMN_LABEL": {"ru": "Числовое поле"},
        },
    ]


@pytest.fixture
def webhook_deal_update_payload():
    """Sample Bitrix webhook payload for deal update."""
    return "event=ONCRMDEALUPDATE&data[FIELDS][ID]=123&auth[access_token]=abc"


@pytest.fixture
def webhook_contact_add_payload():
    """Sample Bitrix webhook payload for contact add."""
    return "event=ONCRMCONTACTADD&data[FIELDS][ID]=456&auth[access_token]=abc"


@pytest.fixture
def webhook_deal_delete_payload():
    """Sample Bitrix webhook payload for deal delete."""
    return "event=ONCRMDEALDELETE&data[FIELDS][ID]=123&auth[access_token]=abc"


@pytest.fixture
def mock_db_engine():
    """Mock database engine for testing."""
    engine = AsyncMock()
    connection = AsyncMock()
    engine.begin.return_value.__aenter__.return_value = connection
    return engine


@pytest.fixture
def mock_bitrix_client():
    """Mock BitrixClient for testing."""
    client = AsyncMock()
    client.get_entities = AsyncMock(return_value=[])
    client.get_entity = AsyncMock(return_value={})
    client.get_entity_fields = AsyncMock(return_value={})
    client.get_userfields = AsyncMock(return_value=[])
    client.register_webhook = AsyncMock(return_value=True)
    client.unregister_webhook = AsyncMock(return_value=True)
    client.get_registered_webhooks = AsyncMock(return_value=[])
    return client


@pytest.fixture
async def test_app() -> FastAPI:
    """Create a test FastAPI application instance."""
    from app.main import create_app

    app = create_app()
    return app


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        yield client
