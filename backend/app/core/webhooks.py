"""Webhook parsing utilities for Bitrix24 events."""

import urllib.parse
from typing import Any


def parse_nested_query(query_string: str) -> dict[str, Any]:
    """Parse URL-encoded nested query string from Bitrix24 webhook.

    Bitrix24 sends webhook data as URL-encoded form data with nested keys like:
    data[FIELDS][ID]=123&event=ONCRMDEALUPDATE

    This function parses such strings into nested Python dictionaries.

    Args:
        query_string: URL-encoded query string from webhook body

    Returns:
        Nested dictionary with parsed data

    Example:
        >>> parse_nested_query("event=ONCRMDEALUPDATE&data[FIELDS][ID]=123")
        {'event': 'ONCRMDEALUPDATE', 'data': {'FIELDS': {'ID': '123'}}}
    """
    pairs = urllib.parse.parse_qsl(query_string)
    result: dict[str, Any] = {}

    for key, value in pairs:
        # Split key by square brackets: data[FIELDS][ID] -> ['data', 'FIELDS', 'ID']
        parts = key.replace("]", "").split("[")

        # Start from root dict
        current = result

        # Navigate through all parts except the last one
        for part in parts[:-1]:
            if part == "":
                continue

            if part not in current:
                current[part] = {}

            current = current[part]

        # Set value for the last key
        last_key = parts[-1]
        if last_key in current and isinstance(current[last_key], dict):
            # If last key exists and is a dict, convert to list
            if not isinstance(current[last_key], list):
                current[last_key] = [current[last_key]]
            current[last_key].append(value)
        else:
            current[last_key] = value

    return result


def extract_event_info(event_data: dict[str, Any]) -> tuple[str, str | None]:
    """Extract event type and entity ID from parsed webhook data.

    Args:
        event_data: Parsed webhook data dictionary

    Returns:
        Tuple of (event_type, entity_id)
    """
    event_type = event_data.get("event", "")
    entity_id = None

    if "data" in event_data and "FIELDS" in event_data["data"]:
        entity_id = event_data["data"]["FIELDS"].get("ID")

    return event_type, entity_id
