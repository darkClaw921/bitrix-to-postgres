"""Pydantic schemas for plan (target value) endpoints.

Covers the request/response shapes used by ``/api/v1/plans`` — CRUD,
plan-vs-actual and the small meta-endpoints (``/meta/tables``,
``/meta/numeric-fields``).

The request validators mirror the logic in
``app.domain.services.plan_service.PlanService._validate_period`` so that
obviously invalid payloads fail fast at the HTTP boundary.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Shared constants (must stay in sync with PlanService)
# ---------------------------------------------------------------------------


FIXED_PERIOD_TYPES: frozenset[str] = frozenset({"month", "quarter", "year"})
ALL_PERIOD_TYPES: frozenset[str] = FIXED_PERIOD_TYPES | {"custom"}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class PlanCreateRequest(BaseModel):
    """Payload to create a new plan row.

    Exactly one of the two period modes must be provided:

    * **fixed** — ``period_type ∈ {month, quarter, year}`` + ``period_value``
      (e.g. ``"2026-04"``, ``"2026-Q2"``, ``"2026"``).
    * **custom** — ``period_type == "custom"`` + ``date_from`` + ``date_to``.
    """

    table_name: str = Field(..., min_length=1, max_length=64)
    field_name: str = Field(..., min_length=1, max_length=128)
    assigned_by_id: Optional[str] = Field(
        None,
        max_length=32,
        description="Manager id; NULL means a plan for everyone.",
    )
    period_type: str = Field(
        ...,
        description="One of: month, quarter, year, custom.",
    )
    period_value: Optional[str] = Field(
        None,
        max_length=16,
        description="Required for fixed period_type; NULL for 'custom'.",
    )
    date_from: Optional[date] = Field(
        None, description="Required for period_type='custom'."
    )
    date_to: Optional[date] = Field(
        None, description="Required for period_type='custom'."
    )
    plan_value: Decimal = Field(..., description="Planned numeric value.")
    description: Optional[str] = None
    created_by_id: Optional[str] = Field(None, max_length=32)

    @model_validator(mode="after")
    def _validate_period_mode(self) -> "PlanCreateRequest":
        if self.period_type not in ALL_PERIOD_TYPES:
            raise ValueError(
                f"period_type must be one of {sorted(ALL_PERIOD_TYPES)}, "
                f"got '{self.period_type}'"
            )

        if self.period_type in FIXED_PERIOD_TYPES:
            if not self.period_value:
                raise ValueError(
                    f"period_value is required for period_type='{self.period_type}'"
                )
            if self.date_from is not None or self.date_to is not None:
                raise ValueError(
                    "date_from/date_to must be NULL for fixed period_type "
                    f"'{self.period_type}'"
                )
        else:  # custom
            if self.date_from is None or self.date_to is None:
                raise ValueError(
                    "date_from and date_to are required for period_type='custom'"
                )
            if self.period_value:
                raise ValueError(
                    "period_value must be NULL for period_type='custom'"
                )
            if self.date_to < self.date_from:
                raise ValueError("date_to must be >= date_from")
        return self


class PlanUpdateRequest(BaseModel):
    """Payload to update an existing plan.

    All fields are optional: the service performs a partial update when
    only ``plan_value`` / ``description`` are sent, and a full update
    (re-validating the logical key) when any of the key fields are
    present.

    For a full update, the period-mode invariant is verified inside
    ``PlanService.update_plan`` against the merged row, so this schema
    intentionally does not run the same ``model_validator`` as
    ``PlanCreateRequest``.
    """

    table_name: Optional[str] = Field(None, min_length=1, max_length=64)
    field_name: Optional[str] = Field(None, min_length=1, max_length=128)
    assigned_by_id: Optional[str] = Field(None, max_length=32)
    period_type: Optional[str] = None
    period_value: Optional[str] = Field(None, max_length=16)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    plan_value: Optional[Decimal] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    """A single plan row as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_name: str
    field_name: str
    assigned_by_id: Optional[str] = None
    period_type: Optional[str] = None
    period_value: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    plan_value: Decimal
    description: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlanVsActualResponse(BaseModel):
    """Plan vs actual snapshot for a single plan.

    ``variance = actual_value - plan_value``. ``variance_pct`` is ``None`` when
    ``plan_value == 0`` to avoid division-by-zero on the client.
    ``period_effective_from`` / ``period_effective_to`` are the concrete
    ``[from, to)`` bounds used for the SUM, materialised from
    ``period_type``/``period_value`` (or copied from ``date_from``/``date_to``
    for custom periods).
    """

    plan_id: int
    plan_value: Decimal
    actual_value: Decimal
    variance: Decimal
    variance_pct: Optional[float] = None
    period_effective_from: date
    period_effective_to: date


class NumericFieldInfo(BaseModel):
    """A single numeric column descriptor returned by /meta/numeric-fields."""

    name: str
    data_type: str


class NumericFieldsResponse(BaseModel):
    """Response of /meta/numeric-fields."""

    table_name: str
    fields: list[NumericFieldInfo]


class TableInfo(BaseModel):
    """A single table descriptor returned by /meta/tables."""

    name: str
    label: Optional[str] = None


class TablesResponse(BaseModel):
    """Response of /meta/tables."""

    tables: list[TableInfo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def plan_row_to_response(row: dict[str, Any]) -> PlanResponse:
    """Convert a raw ``plans`` row (dict) into a ``PlanResponse``.

    ``PlanService`` returns plain dicts via ``_row_to_dict``; this helper
    centralises the conversion so endpoints stay thin.
    """
    return PlanResponse.model_validate(row)
