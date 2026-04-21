"""Date token resolution for selector default values and filter values.

Tokens are dynamic placeholders like ``LAST_30_DAYS`` that resolve to actual
``YYYY-MM-DD`` strings at request time. This lets clients send a token in
``selector.config.default_value`` (or in raw filter values) instead of a fixed
date — the backend resolves it on every request, so the same default keeps
sliding forward as time passes.

Also provides ``extend_to_end_of_day`` so that ``BETWEEN`` filters with a
``to`` date like ``"2026-04-06"`` cover the full day instead of stopping at
``00:00:00``.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

# Token names — kept as a frozenset for fast membership checks.
DATE_TOKENS: frozenset[str] = frozenset({
    "TODAY",
    "YESTERDAY",
    "TOMORROW",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "LAST_90_DAYS",
    "THIS_MONTH_START",
    "LAST_MONTH_START",
    "THIS_QUARTER_START",
    "LAST_QUARTER_START",
    "THIS_YEAR_START",
    "LAST_YEAR_START",
    "YEAR_START",  # alias for THIS_YEAR_START
})

_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fmt(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _today() -> date:
    return datetime.now().date()


def _quarter_start(d: date) -> date:
    quarter_first_month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, quarter_first_month, 1)


def is_date_token(value: Any) -> bool:
    """Return True if value is a recognized date token string."""
    return isinstance(value, str) and value in DATE_TOKENS


def is_date_only(value: Any) -> bool:
    """Return True if value is a date-only string ``YYYY-MM-DD``."""
    return isinstance(value, str) and bool(_DATE_ONLY_RE.match(value))


def resolve_token(value: Any) -> Any:
    """Resolve a date token to ``YYYY-MM-DD``. Pass through other values.

    Args:
        value: Token name (``TODAY``, ``LAST_30_DAYS``, ...) or any other value.

    Returns:
        ``YYYY-MM-DD`` string for known tokens; the original value otherwise.
    """
    if not is_date_token(value):
        return value

    today = _today()

    if value == "TODAY":
        return _fmt(today)
    if value == "YESTERDAY":
        return _fmt(today - timedelta(days=1))
    if value == "TOMORROW":
        return _fmt(today + timedelta(days=1))
    if value == "LAST_7_DAYS":
        return _fmt(today - timedelta(days=7))
    if value == "LAST_14_DAYS":
        return _fmt(today - timedelta(days=14))
    if value == "LAST_30_DAYS":
        return _fmt(today - timedelta(days=30))
    if value == "LAST_90_DAYS":
        return _fmt(today - timedelta(days=90))
    if value == "THIS_MONTH_START":
        return _fmt(date(today.year, today.month, 1))
    if value == "LAST_MONTH_START":
        first_of_this_month = date(today.year, today.month, 1)
        last_month_last_day = first_of_this_month - timedelta(days=1)
        return _fmt(date(last_month_last_day.year, last_month_last_day.month, 1))
    if value == "THIS_QUARTER_START":
        return _fmt(_quarter_start(today))
    if value == "LAST_QUARTER_START":
        this_q = _quarter_start(today)
        last_q_last_day = this_q - timedelta(days=1)
        return _fmt(_quarter_start(last_q_last_day))
    if value in ("THIS_YEAR_START", "YEAR_START"):
        return _fmt(date(today.year, 1, 1))
    if value == "LAST_YEAR_START":
        return _fmt(date(today.year - 1, 1, 1))

    return value  # unreachable, but keeps type checkers happy


def resolve_filter_value(selector_type: str | None, value: Any) -> Any:
    """Resolve date tokens inside a filter value, respecting its shape.

    - For ``date_range``: ``{from, to}`` → resolves both keys.
    - For ``single_date`` or anything else: passes scalar through ``resolve_token``.
    - Lists are walked element-wise.
    """
    if value is None:
        return value
    if isinstance(value, dict):
        return {k: resolve_token(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_token(v) for v in value]
    return resolve_token(value)


def extend_to_end_of_day(value: Any) -> Any:
    """Append ``23:59:59`` to a date-only string so ``BETWEEN`` covers the day.

    Other values pass through unchanged.
    """
    if is_date_only(value):
        return f"{value} 23:59:59"
    return value
