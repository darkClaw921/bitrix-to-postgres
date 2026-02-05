"""Field mapper service for transforming Bitrix24 fields to PostgreSQL format."""

from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeEngine


# Mapping from Bitrix24 field types to SQLAlchemy column types
TYPE_MAPPING: dict[str, type[TypeEngine]] = {
    "string": String,
    "char": String,
    "text": Text,
    "integer": BigInteger,
    "double": Float,
    "float": Float,
    "datetime": DateTime,
    "date": DateTime,
    "boolean": Boolean,
    "url": String,
    "money": Float,
    "file": String,  # Store file ID as string
    "disk_file": String,
    "employee": String,  # User ID
    "enumeration": String,  # Store enum value
    "iblock_element": String,
    "iblock_section": String,
    "crm_status": String,
    "crm_category": String,
    "crm": String,  # CRM entity reference
    "crm_multifield": String,  # Phone, email etc. - serialized to JSON string
    "crm_entity": String,
    "address": Text,
    "resourcebooking": String,
    "hlblock": String,  # HighLoad block reference
    "video": String,
}

# SQL type names for ALTER TABLE statements
SQL_TYPE_NAMES: dict[str, str] = {
    "string": "VARCHAR",
    "char": "VARCHAR",
    "text": "TEXT",
    "integer": "BIGINT",
    "double": "FLOAT",
    "float": "FLOAT",
    "datetime": "TIMESTAMP",
    "date": "TIMESTAMP",
    "boolean": "BOOLEAN",
    "url": "VARCHAR",
    "money": "FLOAT",
    "file": "VARCHAR",
    "disk_file": "VARCHAR",
    "employee": "VARCHAR",
    "enumeration": "VARCHAR",
    "iblock_element": "VARCHAR",
    "iblock_section": "VARCHAR",
    "crm_status": "VARCHAR",
    "crm_category": "VARCHAR",
    "crm": "VARCHAR",
    "crm_multifield": "VARCHAR",
    "crm_entity": "VARCHAR",
    "address": "TEXT",
    "resourcebooking": "VARCHAR",
    "hlblock": "VARCHAR",
    "video": "VARCHAR",
}


class FieldInfo:
    """Processed field information for database operations."""

    def __init__(
        self,
        field_id: str,
        field_type: str,
        entity_id: str,
        description: str | None = None,
        is_user_field: bool = False,
        is_multiple: bool = False,
        is_required: bool = False,
    ):
        self.field_id = field_id
        self.field_type = field_type
        self.entity_id = entity_id
        self.description = description or field_id
        self.is_user_field = is_user_field
        self.is_multiple = is_multiple
        self.is_required = is_required

    @property
    def column_name(self) -> str:
        """Get lowercase column name for PostgreSQL."""
        return self.field_id.lower()

    @property
    def sqlalchemy_type(self) -> type[TypeEngine]:
        """Get SQLAlchemy column type."""
        if self.is_multiple:
            return ARRAY(String)
        return TYPE_MAPPING.get(self.field_type.lower(), String)

    @property
    def sql_type_name(self) -> str:
        """Get SQL type name for ALTER TABLE."""
        if self.is_multiple:
            return "VARCHAR[]"
        return SQL_TYPE_NAMES.get(self.field_type.lower(), "VARCHAR")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "fieldID": self.field_id,
            "fieldType": self.field_type,
            "entityID": self.entity_id,
            "description": self.description,
            "isUserField": self.is_user_field,
            "isMultiple": self.is_multiple,
            "isRequired": self.is_required,
        }


class FieldMapper:
    """Service for mapping Bitrix24 fields to PostgreSQL format."""

    @staticmethod
    def prepare_fields_to_postgres(
        fields: dict[str, dict[str, Any]],
        entity_type: str,
    ) -> list[FieldInfo]:
        """Transform crm.*.fields response to standardized format.

        Args:
            fields: Response from crm.{entity}.fields API call
            entity_type: Entity type (deal, contact, lead, company)

        Returns:
            List of FieldInfo objects ready for database operations
        """
        entity_id = f"CRM_{entity_type.upper()}"
        result: list[FieldInfo] = []

        for field_id, meta in fields.items():
            field_type = meta.get("type", "string")
            is_multiple = meta.get("isMultiple", False)
            is_required = meta.get("isRequired", False)
            title = meta.get("title") or meta.get("formLabel") or field_id

            field_info = FieldInfo(
                field_id=field_id,
                field_type=field_type,
                entity_id=entity_id,
                description=title,
                is_user_field=field_id.upper().startswith("UF_"),
                is_multiple=is_multiple,
                is_required=is_required,
            )
            result.append(field_info)

        return result

    @staticmethod
    def prepare_userfields_to_postgres(
        userfields: list[dict[str, Any]],
        entity_type: str,
    ) -> list[FieldInfo]:
        """Transform crm.*.userfield.list response to standardized format.

        Args:
            userfields: Response from crm.{entity}.userfield.list API call
            entity_type: Entity type (deal, contact, lead, company)

        Returns:
            List of FieldInfo objects ready for database operations
        """
        entity_id = f"CRM_{entity_type.upper()}"
        result: list[FieldInfo] = []

        for field in userfields:
            field_name = field.get("FIELD_NAME", "")
            user_type_id = field.get("USER_TYPE_ID", "string")
            is_multiple = field.get("MULTIPLE") == "Y"

            # Get title from LIST_COLUMN_LABEL or EDIT_FORM_LABEL
            title = None
            if field.get("LIST_COLUMN_LABEL"):
                labels = field["LIST_COLUMN_LABEL"]
                title = labels.get("ru") or labels.get("en") or next(iter(labels.values()), None)
            if not title and field.get("EDIT_FORM_LABEL"):
                labels = field["EDIT_FORM_LABEL"]
                title = labels.get("ru") or labels.get("en") or next(iter(labels.values()), None)

            field_info = FieldInfo(
                field_id=field_name,
                field_type=user_type_id,
                entity_id=entity_id,
                description=title,
                is_user_field=True,
                is_multiple=is_multiple,
                is_required=field.get("MANDATORY") == "Y",
            )
            result.append(field_info)

        return result

    @staticmethod
    def merge_fields(
        standard_fields: list[FieldInfo],
        user_fields: list[FieldInfo],
    ) -> list[FieldInfo]:
        """Merge standard fields and user fields, removing duplicates.

        User fields take precedence when field_id matches.

        Args:
            standard_fields: Fields from crm.*.fields
            user_fields: Fields from crm.*.userfield.list

        Returns:
            Merged list of unique fields
        """
        # Create dict of user fields for quick lookup
        user_field_ids = {f.field_id.upper() for f in user_fields}

        # Filter out standard fields that are duplicated in user fields
        result = [f for f in standard_fields if f.field_id.upper() not in user_field_ids]

        # Add all user fields
        result.extend(user_fields)

        return result

    @staticmethod
    def get_sqlalchemy_type(field_type: str, is_multiple: bool = False) -> type[TypeEngine]:
        """Get SQLAlchemy column type for a Bitrix field type.

        Args:
            field_type: Bitrix field type string
            is_multiple: Whether the field can have multiple values

        Returns:
            SQLAlchemy type class
        """
        if is_multiple:
            return ARRAY(String)
        return TYPE_MAPPING.get(field_type.lower(), String)

    @staticmethod
    def get_sql_type_name(field_type: str, is_multiple: bool = False) -> str:
        """Get SQL type name for ALTER TABLE statements.

        Args:
            field_type: Bitrix field type string
            is_multiple: Whether the field can have multiple values

        Returns:
            SQL type name string (e.g., 'VARCHAR', 'BIGINT')
        """
        if is_multiple:
            return "VARCHAR[]"
        return SQL_TYPE_NAMES.get(field_type.lower(), "VARCHAR")
