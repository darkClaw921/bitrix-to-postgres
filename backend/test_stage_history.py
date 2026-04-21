#!/usr/bin/env python3
"""Test script for stage_history entity type registration."""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))


def test_entity_type_registration():
    """Test that stage_history types are properly registered."""
    from app.domain.entities.base import EntityType

    print("=== Testing EntityType Registration ===\n")

    # Test 1: Check if types are in all()
    all_types = EntityType.all()
    print(f"All entity types: {all_types}")
    assert "stage_history_deal" in all_types, "stage_history_deal not in all()"
    assert "stage_history_lead" in all_types, "stage_history_lead not in all()"
    print("✓ stage_history types are registered\n")

    # Test 2: Check table names
    deal_table = EntityType.get_table_name("stage_history_deal")
    lead_table = EntityType.get_table_name("stage_history_lead")
    print(f"Deal table name: {deal_table}")
    print(f"Lead table name: {lead_table}")
    assert deal_table == "stage_history_deals", f"Expected stage_history_deals, got {deal_table}"
    assert lead_table == "stage_history_leads", f"Expected stage_history_leads, got {lead_table}"
    print("✓ Table names are correct\n")

    # Test 3: Check Bitrix API prefix
    deal_prefix = EntityType.get_bitrix_prefix("stage_history_deal")
    lead_prefix = EntityType.get_bitrix_prefix("stage_history_lead")
    print(f"Deal API prefix: {deal_prefix}")
    print(f"Lead API prefix: {lead_prefix}")
    assert deal_prefix == "crm.stagehistory", f"Expected crm.stagehistory, got {deal_prefix}"
    assert lead_prefix == "crm.stagehistory", f"Expected crm.stagehistory, got {lead_prefix}"
    print("✓ API prefixes are correct\n")

    print("=== All tests passed! ===")


def test_stage_history_model():
    """Test StageHistory model."""
    from app.domain.entities.stage_history import StageHistory

    print("\n=== Testing StageHistory Model ===\n")

    # Test model creation
    history = StageHistory(
        id="123",
        history_id="456",
        type_id=2,
        owner_id="789",
        stage_id="C1:NEW",
        stage_semantic_id="P",
    )

    print(f"Created history: {history}")
    print(f"History ID: {history.history_id}")
    print(f"Owner ID: {history.owner_id}")
    print(f"Type ID: {history.type_id}")
    print(f"Stage ID: {history.stage_id}")
    print("✓ StageHistory model works\n")


def test_sync_service_mappings():
    """Test SyncService mappings."""
    from app.domain.services.sync_service import SyncService

    print("=== Testing SyncService Mappings ===\n")

    # Access the class mappings directly
    ref_map = SyncService._ENTITY_REFERENCE_MAP
    date_field_map = SyncService._DATE_MODIFY_FIELD

    print(f"Reference map for stage_history_deal: {ref_map.get('stage_history_deal')}")
    print(f"Reference map for stage_history_lead: {ref_map.get('stage_history_lead')}")
    assert "stage_history_deal" in ref_map, "stage_history_deal not in reference map"
    assert "stage_history_lead" in ref_map, "stage_history_lead not in reference map"
    print("✓ Reference mappings exist\n")

    print(f"Date field for stage_history_deal: {date_field_map.get('stage_history_deal')}")
    print(f"Date field for stage_history_lead: {date_field_map.get('stage_history_lead')}")
    assert date_field_map.get("stage_history_deal") == "CREATED_TIME", "Wrong date field for deals"
    assert date_field_map.get("stage_history_lead") == "CREATED_TIME", "Wrong date field for leads"
    print("✓ Date fields are correct\n")

    print("=== All sync service tests passed! ===")


if __name__ == "__main__":
    try:
        test_entity_type_registration()
        test_stage_history_model()
        test_sync_service_mappings()
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
