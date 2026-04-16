"""Department entity for Bitrix24 department hierarchy.

Чистая доменная модель отдела (без зависимостей от БД). Используется
``DepartmentSyncService`` и ``DepartmentService`` для типизированной передачи
данных между слоями.

Поля соответствуют колонкам таблицы ``bitrix_departments`` (см. миграцию
``023_create_bitrix_departments_table.py``) и нормализованным значениям из
ответа ``department.get`` Bitrix24 API:

- ``bitrix_id`` — строковый идентификатор отдела в Bitrix24 (``ID``).
- ``name`` — название отдела (``NAME``).
- ``parent_id`` — ID родительского отдела (``PARENT``); ``None`` у корня.
- ``sort`` — порядок сортировки (``SORT``); default 500, как в Bitrix24.
- ``uf_head`` — ID пользователя-руководителя отдела (``UF_HEAD``); опционален.
"""

from dataclasses import dataclass


@dataclass
class DepartmentEntity:
    """Bitrix24 department entity (plain data class, no DB dependencies)."""

    bitrix_id: str
    name: str | None = None
    parent_id: str | None = None
    sort: int = 500
    uf_head: str | None = None
