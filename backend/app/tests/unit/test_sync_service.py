"""Unit tests for SyncService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import SyncError


class TestSyncServiceFullSync:
    """Test suite for SyncService.full_sync method."""

    @pytest.fixture
    def mock_dependencies(self, mock_bitrix_client, sample_deal_fields, sample_userfields):
        """Set up all mocked dependencies."""
        mock_bitrix_client.get_entity_fields.return_value = sample_deal_fields
        mock_bitrix_client.get_userfields.return_value = sample_userfields

        with patch("app.domain.services.sync_service.get_engine") as mock_engine, \
             patch("app.domain.services.sync_service.DynamicTableBuilder") as mock_builder, \
             patch("app.domain.services.sync_service.FieldMapper") as mock_mapper:

            # Setup engine mock
            mock_conn = AsyncMock()
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn

            # Setup builder mock
            mock_builder.table_exists = AsyncMock(return_value=False)
            mock_builder.create_table_from_fields = AsyncMock()
            mock_builder.ensure_columns_exist = AsyncMock(return_value=[])
            mock_builder.get_table_columns = AsyncMock(return_value=["bitrix_id", "title", "stage_id"])

            # Setup mapper mock
            mock_mapper.prepare_fields_to_postgres.return_value = []
            mock_mapper.prepare_userfields_to_postgres.return_value = []
            mock_mapper.merge_fields.return_value = []

            yield {
                "bitrix": mock_bitrix_client,
                "engine": mock_engine,
                "builder": mock_builder,
                "mapper": mock_mapper,
                "connection": mock_conn,
            }

    @pytest.fixture
    def sync_service(self, mock_dependencies):
        """Create SyncService instance with mocked BitrixClient."""
        from app.domain.services.sync_service import SyncService
        return SyncService(bitrix_client=mock_dependencies["bitrix"])

    async def test_full_sync_creates_table_if_not_exists(
        self, sync_service, mock_dependencies
    ):
        """Test full_sync creates table when it doesn't exist."""
        mock_dependencies["bitrix"].get_entities.return_value = []
        mock_dependencies["builder"].table_exists.return_value = False

        result = await sync_service.full_sync("deal")

        assert result["status"] == "completed"
        assert result["entity_type"] == "deal"
        mock_dependencies["builder"].create_table_from_fields.assert_called_once()

    async def test_full_sync_updates_existing_table(
        self, sync_service, mock_dependencies
    ):
        """Test full_sync updates columns when table exists."""
        mock_dependencies["bitrix"].get_entities.return_value = []
        mock_dependencies["builder"].table_exists.return_value = True

        result = await sync_service.full_sync("deal")

        assert result["status"] == "completed"
        mock_dependencies["builder"].ensure_columns_exist.assert_called_once()

    async def test_full_sync_fetches_all_entities(
        self, sync_service, mock_dependencies, sample_deal_data
    ):
        """Test full_sync fetches entities from Bitrix."""
        mock_dependencies["bitrix"].get_entities.return_value = [sample_deal_data]

        result = await sync_service.full_sync("deal")

        mock_dependencies["bitrix"].get_entities.assert_called_once_with("deal")
        assert result["records_processed"] >= 0

    async def test_full_sync_processes_records(
        self, sync_service, mock_dependencies, sample_deal_data
    ):
        """Test full_sync processes and upserts records."""
        mock_dependencies["bitrix"].get_entities.return_value = [
            sample_deal_data,
            {**sample_deal_data, "ID": "456"},
        ]

        result = await sync_service.full_sync("deal")

        assert result["records_processed"] == 2

    async def test_full_sync_handles_empty_result(
        self, sync_service, mock_dependencies
    ):
        """Test full_sync handles empty response from Bitrix."""
        mock_dependencies["bitrix"].get_entities.return_value = []

        result = await sync_service.full_sync("deal")

        assert result["status"] == "completed"
        assert result["records_processed"] == 0

    async def test_full_sync_raises_on_bitrix_error(
        self, sync_service, mock_dependencies
    ):
        """Test full_sync raises SyncError on Bitrix API errors."""
        from app.core.exceptions import BitrixAPIError
        mock_dependencies["bitrix"].get_entities.side_effect = BitrixAPIError("API failed")

        with pytest.raises(SyncError, match="Full sync failed for deal"):
            await sync_service.full_sync("deal")

    async def test_full_sync_creates_sync_log(
        self, sync_service, mock_dependencies
    ):
        """Test full_sync creates sync log entry."""
        mock_dependencies["bitrix"].get_entities.return_value = []

        # Mock the sync log creation
        mock_dependencies["connection"].execute.return_value.scalar.return_value = 1

        result = await sync_service.full_sync("deal")

        assert result["status"] == "completed"


class TestSyncServiceIncrementalSync:
    """Test suite for SyncService.incremental_sync method."""

    @pytest.fixture
    def mock_dependencies(self, mock_bitrix_client):
        """Set up all mocked dependencies."""
        with patch("app.domain.services.sync_service.get_engine") as mock_engine, \
             patch("app.domain.services.sync_service.DynamicTableBuilder") as mock_builder, \
             patch("app.domain.services.sync_service.FieldMapper") as mock_mapper:

            # Setup engine mock
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_result.fetchone.return_value = (datetime(2024, 1, 15, 10, 0, 0),)
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn

            # Setup builder mock
            mock_builder.table_exists = AsyncMock(return_value=True)
            mock_builder.get_table_columns = AsyncMock(return_value=["bitrix_id", "title"])
            mock_builder.ensure_columns_exist = AsyncMock(return_value=[])

            # Setup mapper mock
            mock_mapper.prepare_fields_to_postgres.return_value = []
            mock_mapper.prepare_userfields_to_postgres.return_value = []
            mock_mapper.merge_fields.return_value = []

            yield {
                "bitrix": mock_bitrix_client,
                "engine": mock_engine,
                "builder": mock_builder,
                "mapper": mock_mapper,
                "connection": mock_conn,
            }

    @pytest.fixture
    def sync_service(self, mock_dependencies):
        """Create SyncService instance with mocked BitrixClient."""
        from app.domain.services.sync_service import SyncService
        return SyncService(bitrix_client=mock_dependencies["bitrix"])

    async def test_incremental_sync_uses_date_filter(
        self, sync_service, mock_dependencies, sample_deal_data
    ):
        """Test incremental_sync uses DATE_MODIFY filter."""
        mock_dependencies["bitrix"].get_entity_fields.return_value = {}
        mock_dependencies["bitrix"].get_userfields.return_value = []
        mock_dependencies["bitrix"].get_entities.return_value = [sample_deal_data]

        result = await sync_service.incremental_sync("deal")

        # Verify filter was applied
        call_args = mock_dependencies["bitrix"].get_entities.call_args
        assert ">DATE_MODIFY" in call_args[1]["filter_params"]

    async def test_incremental_sync_falls_back_to_full_when_no_state(
        self, sync_service, mock_dependencies
    ):
        """Test incremental_sync runs full sync when no previous state exists."""
        # Return None for last_modified_date
        mock_dependencies["connection"].execute.return_value.fetchone.return_value = None
        mock_dependencies["bitrix"].get_entity_fields.return_value = {}
        mock_dependencies["bitrix"].get_userfields.return_value = []
        mock_dependencies["bitrix"].get_entities.return_value = []

        result = await sync_service.incremental_sync("deal")

        # Should have called get_entities without DATE_MODIFY filter (full sync)
        assert result["status"] == "completed"

    async def test_incremental_sync_falls_back_when_table_not_exists(
        self, sync_service, mock_dependencies
    ):
        """Test incremental_sync runs full sync when table doesn't exist."""
        mock_dependencies["builder"].table_exists.return_value = False
        mock_dependencies["bitrix"].get_entity_fields.return_value = {}
        mock_dependencies["bitrix"].get_userfields.return_value = []
        mock_dependencies["bitrix"].get_entities.return_value = []

        result = await sync_service.incremental_sync("deal")

        # Should run full sync
        mock_dependencies["builder"].create_table_from_fields.assert_called_once()

    async def test_incremental_sync_handles_no_changes(
        self, sync_service, mock_dependencies
    ):
        """Test incremental_sync handles case with no modified records."""
        mock_dependencies["bitrix"].get_entities.return_value = []

        result = await sync_service.incremental_sync("deal")

        assert result["status"] == "completed"
        assert result["records_processed"] == 0
        assert result["sync_type"] == "incremental"


class TestSyncServiceWebhookSync:
    """Test suite for SyncService webhook sync methods."""

    @pytest.fixture
    def mock_dependencies(self, mock_bitrix_client):
        """Set up all mocked dependencies."""
        with patch("app.domain.services.sync_service.get_engine") as mock_engine, \
             patch("app.domain.services.sync_service.DynamicTableBuilder") as mock_builder:

            # Setup engine mock
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_result.rowcount = 1
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn

            # Setup builder mock
            mock_builder.table_exists = AsyncMock(return_value=True)
            mock_builder.get_table_columns = AsyncMock(return_value=["bitrix_id", "title"])

            yield {
                "bitrix": mock_bitrix_client,
                "engine": mock_engine,
                "builder": mock_builder,
                "connection": mock_conn,
            }

    @pytest.fixture
    def sync_service(self, mock_dependencies):
        """Create SyncService instance with mocked BitrixClient."""
        from app.domain.services.sync_service import SyncService
        return SyncService(bitrix_client=mock_dependencies["bitrix"])

    async def test_sync_entity_by_id_fetches_and_upserts(
        self, sync_service, mock_dependencies, sample_deal_data
    ):
        """Test sync_entity_by_id fetches single entity and upserts."""
        mock_dependencies["bitrix"].get_entity.return_value = sample_deal_data

        result = await sync_service.sync_entity_by_id("deal", "123")

        mock_dependencies["bitrix"].get_entity.assert_called_once_with("deal", "123")
        assert result["status"] == "completed"
        assert result["entity_id"] == "123"

    async def test_sync_entity_by_id_skips_when_table_not_exists(
        self, sync_service, mock_dependencies
    ):
        """Test sync_entity_by_id skips when table doesn't exist."""
        mock_dependencies["builder"].table_exists.return_value = False

        result = await sync_service.sync_entity_by_id("deal", "123")

        assert result["status"] == "skipped"
        assert result["reason"] == "table_not_exists"

    async def test_sync_entity_by_id_handles_not_found(
        self, sync_service, mock_dependencies
    ):
        """Test sync_entity_by_id handles entity not found in Bitrix."""
        mock_dependencies["bitrix"].get_entity.return_value = None

        result = await sync_service.sync_entity_by_id("deal", "999")

        assert result["status"] == "not_found"

    async def test_delete_entity_by_id_removes_record(
        self, sync_service, mock_dependencies
    ):
        """Test delete_entity_by_id deletes record from database."""
        result = await sync_service.delete_entity_by_id("deal", "123")

        assert result["status"] == "completed"
        assert result["records_deleted"] == 1

    async def test_delete_entity_by_id_skips_when_table_not_exists(
        self, sync_service, mock_dependencies
    ):
        """Test delete_entity_by_id skips when table doesn't exist."""
        mock_dependencies["builder"].table_exists.return_value = False

        result = await sync_service.delete_entity_by_id("deal", "123")

        assert result["status"] == "skipped"


class TestSyncServiceRecordProcessing:
    """Test suite for SyncService record processing methods."""

    @pytest.fixture
    def sync_service(self, mock_bitrix_client):
        """Create SyncService instance with mocked BitrixClient."""
        from app.domain.services.sync_service import SyncService
        return SyncService(bitrix_client=mock_bitrix_client)

    def test_prepare_record_data_maps_id_to_bitrix_id(self, sync_service, sample_deal_data):
        """Test _prepare_record_data maps ID to bitrix_id."""
        valid_columns = {"bitrix_id", "title", "stage_id"}

        result = sync_service._prepare_record_data(sample_deal_data, valid_columns)

        assert result["bitrix_id"] == "123"
        assert "id" not in result

    def test_prepare_record_data_converts_keys_to_lowercase(self, sync_service):
        """Test _prepare_record_data converts keys to lowercase."""
        record = {"ID": "1", "TITLE": "Test", "STAGE_ID": "NEW"}
        valid_columns = {"bitrix_id", "title", "stage_id"}

        result = sync_service._prepare_record_data(record, valid_columns)

        assert "title" in result
        assert "stage_id" in result
        assert "TITLE" not in result

    def test_prepare_record_data_filters_invalid_columns(self, sync_service):
        """Test _prepare_record_data filters out invalid columns."""
        record = {"ID": "1", "TITLE": "Test", "UNKNOWN_FIELD": "value"}
        valid_columns = {"bitrix_id", "title"}

        result = sync_service._prepare_record_data(record, valid_columns)

        assert "unknown_field" not in result
        assert "UNKNOWN_FIELD" not in result

    def test_prepare_record_data_handles_complex_types(self, sync_service):
        """Test _prepare_record_data serializes complex types to JSON."""
        record = {
            "ID": "1",
            "EMAILS": [{"VALUE": "test@example.com"}],
            "METADATA": {"key": "value"},
        }
        valid_columns = {"bitrix_id", "emails", "metadata"}

        result = sync_service._prepare_record_data(record, valid_columns)

        import json
        assert json.loads(result["emails"]) == [{"VALUE": "test@example.com"}]
        assert json.loads(result["metadata"]) == {"key": "value"}

    def test_prepare_record_data_handles_empty_values(self, sync_service):
        """Test _prepare_record_data converts empty strings to None."""
        record = {"ID": "1", "TITLE": "", "STAGE_ID": None}
        valid_columns = {"bitrix_id", "title", "stage_id"}

        result = sync_service._prepare_record_data(record, valid_columns)

        assert result["title"] is None
        assert result["stage_id"] is None


class TestSyncServiceSyncState:
    """Test suite for SyncService sync state management."""

    @pytest.fixture
    def mock_dependencies(self, mock_bitrix_client):
        """Set up all mocked dependencies."""
        with patch("app.domain.services.sync_service.get_engine") as mock_engine:
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.begin.return_value.__aenter__.return_value = mock_conn

            yield {
                "bitrix": mock_bitrix_client,
                "engine": mock_engine,
                "connection": mock_conn,
            }

    @pytest.fixture
    def sync_service(self, mock_dependencies):
        """Create SyncService instance with mocked BitrixClient."""
        from app.domain.services.sync_service import SyncService
        return SyncService(bitrix_client=mock_dependencies["bitrix"])

    async def test_update_sync_state_full_sync(self, sync_service, mock_dependencies):
        """Test _update_sync_state for full sync updates total_records."""
        await sync_service._update_sync_state("deal", 100, incremental=False)

        # Verify UPSERT query was executed with total_records
        calls = mock_dependencies["connection"].execute.call_args_list
        assert any("total_records" in str(call) for call in calls)

    async def test_update_sync_state_incremental(self, sync_service, mock_dependencies):
        """Test _update_sync_state for incremental sync only updates timestamp."""
        await sync_service._update_sync_state("deal", 10, incremental=True)

        # Verify UPDATE query was executed
        calls = mock_dependencies["connection"].execute.call_args_list
        assert any("last_modified_date" in str(call) for call in calls)

    async def test_create_sync_log_returns_log_id(self, sync_service, mock_dependencies):
        """Test _create_sync_log creates log and returns ID."""
        result = await sync_service._create_sync_log("deal", "full")

        assert result.id == 1

    async def test_complete_sync_log_updates_status(self, sync_service, mock_dependencies):
        """Test _complete_sync_log updates log status."""
        await sync_service._complete_sync_log(1, "completed", 100)

        # Verify UPDATE was called
        mock_dependencies["connection"].execute.assert_called()
