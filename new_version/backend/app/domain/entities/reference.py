"""Reference data type definitions for Bitrix24 dictionaries."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReferenceFieldDef:
    """Definition of a single field in a reference table."""

    column_name: str
    sql_type: str
    nullable: bool = True


@dataclass(frozen=True)
class ReferenceType:
    """Definition of a reference data type."""

    name: str
    table_name: str
    api_method: str
    unique_key: list[str] = field(default_factory=list)
    fields: list[ReferenceFieldDef] = field(default_factory=list)
    requires_category_iteration: bool = False


# --- Field definitions ---

STATUS_FIELDS = [
    ReferenceFieldDef("status_id", "VARCHAR(100)", nullable=False),
    ReferenceFieldDef("entity_id", "VARCHAR(100)", nullable=False),
    ReferenceFieldDef("category_id", "VARCHAR(50)", nullable=False),
    ReferenceFieldDef("name", "VARCHAR(500)"),
    ReferenceFieldDef("name_init", "VARCHAR(500)"),
    ReferenceFieldDef("sort", "INTEGER"),
    ReferenceFieldDef("system", "VARCHAR(10)"),
    ReferenceFieldDef("color", "VARCHAR(50)"),
    ReferenceFieldDef("semantics", "VARCHAR(50)"),
    ReferenceFieldDef("extra_color", "VARCHAR(50)"),
    ReferenceFieldDef("extra_semantics", "VARCHAR(50)"),
]

DEAL_CATEGORY_FIELDS = [
    ReferenceFieldDef("id", "VARCHAR(50)", nullable=False),
    ReferenceFieldDef("name", "VARCHAR(500)"),
    ReferenceFieldDef("sort", "INTEGER"),
    ReferenceFieldDef("is_locked", "VARCHAR(10)"),
    ReferenceFieldDef("created_date", "TIMESTAMP"),
]

CURRENCY_FIELDS = [
    ReferenceFieldDef("currency", "VARCHAR(20)", nullable=False),
    ReferenceFieldDef("amount_cnt", "VARCHAR(20)"),
    ReferenceFieldDef("amount", "VARCHAR(50)"),
    ReferenceFieldDef("sort", "INTEGER"),
    ReferenceFieldDef("base", "VARCHAR(10)"),
    ReferenceFieldDef("full_name", "VARCHAR(500)"),
    ReferenceFieldDef("lid", "VARCHAR(10)"),
    ReferenceFieldDef("format_string", "VARCHAR(100)"),
    ReferenceFieldDef("dec_point", "VARCHAR(10)"),
    ReferenceFieldDef("thousands_sep", "VARCHAR(10)"),
    ReferenceFieldDef("decimals", "VARCHAR(10)"),
    ReferenceFieldDef("date_update", "TIMESTAMP"),
]


# --- Registry ---

REFERENCE_TYPES: dict[str, ReferenceType] = {
    "crm_status": ReferenceType(
        name="crm_status",
        table_name="ref_crm_statuses",
        api_method="crm.status.list",
        unique_key=["status_id", "entity_id", "category_id"],
        fields=STATUS_FIELDS,
        requires_category_iteration=True,
    ),
    "crm_deal_category": ReferenceType(
        name="crm_deal_category",
        table_name="ref_crm_deal_categories",
        api_method="crm.dealcategory.list",
        unique_key=["id"],
        fields=DEAL_CATEGORY_FIELDS,
    ),
    "crm_currency": ReferenceType(
        name="crm_currency",
        table_name="ref_crm_currencies",
        api_method="crm.currency.list",
        unique_key=["currency"],
        fields=CURRENCY_FIELDS,
    ),
}


def get_all_reference_types() -> dict[str, ReferenceType]:
    """Return all registered reference types."""
    return REFERENCE_TYPES


def get_reference_type(name: str) -> ReferenceType | None:
    """Return a reference type by name, or None if not found."""
    return REFERENCE_TYPES.get(name)
