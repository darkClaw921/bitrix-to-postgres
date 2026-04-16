"""Service for reading the Bitrix24 department hierarchy.

Read-only сервис над таблицами ``bitrix_departments`` и
``bitrix_user_departments``: плоский список, иерархическое дерево,
сбор всех потомков по ID и выборка активных менеджеров в заданных отделах.

Запись (UPSERT из Bitrix24) — в ``DepartmentSyncService``; запись связи
юзер↔отдел — в ``SyncService._sync_user_departments`` при синхронизации
пользователей.

Рекурсивный обход (``collect_descendant_ids``, ``build_tree``) сделан в
Python, а не ``WITH RECURSIVE``, сознательно: поддержка рекурсивных
CTE различается между PG и MySQL/MariaDB, а число отделов в Bitrix24
обычно небольшое (сотни max) — in-memory BFS тривиален и детерминирован.
"""

from collections import defaultdict, deque
from typing import Any

from sqlalchemy import text

from app.core.logging import get_logger
from app.domain.entities.department import DepartmentEntity
from app.infrastructure.database.connection import get_engine

logger = get_logger(__name__)


class DepartmentService:
    """Read-only service for the Bitrix24 department hierarchy."""

    async def list_departments(self) -> list[DepartmentEntity]:
        """Return flat list of all departments ordered by (parent_id, sort, bitrix_id)."""
        engine = get_engine()
        query = text(
            "SELECT bitrix_id, name, parent_id, sort, uf_head "
            "FROM bitrix_departments "
            "ORDER BY sort, bitrix_id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        return [
            DepartmentEntity(
                bitrix_id=str(row[0]),
                name=row[1],
                parent_id=str(row[2]) if row[2] is not None else None,
                sort=int(row[3]) if row[3] is not None else 500,
                uf_head=str(row[4]) if row[4] is not None else None,
            )
            for row in rows
        ]

    async def get_department(self, bitrix_id: str) -> DepartmentEntity | None:
        """Return a single department by bitrix_id, or None if not found."""
        engine = get_engine()
        query = text(
            "SELECT bitrix_id, name, parent_id, sort, uf_head "
            "FROM bitrix_departments "
            "WHERE bitrix_id = :bitrix_id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"bitrix_id": str(bitrix_id)})
            row = result.fetchone()

        if not row:
            return None

        return DepartmentEntity(
            bitrix_id=str(row[0]),
            name=row[1],
            parent_id=str(row[2]) if row[2] is not None else None,
            sort=int(row[3]) if row[3] is not None else 500,
            uf_head=str(row[4]) if row[4] is not None else None,
        )

    async def build_tree(self) -> list[dict[str, Any]]:
        """Return full department hierarchy as list of root nodes.

        Каждый узел — dict ``{id, name, sort, uf_head, children: [...]}``.
        Сортировка детей и корней — по (``sort``, ``bitrix_id``).
        """
        departments = await self.list_departments()
        return self._build_tree_in_memory(departments)

    @staticmethod
    def _build_tree_in_memory(
        departments: list[DepartmentEntity],
    ) -> list[dict[str, Any]]:
        """Convert flat list → hierarchical tree (pure function, no I/O)."""
        # bitrix_id → node
        nodes: dict[str, dict[str, Any]] = {
            d.bitrix_id: {
                "id": d.bitrix_id,
                "name": d.name,
                "sort": d.sort,
                "uf_head": d.uf_head,
                "parent_id": d.parent_id,
                "children": [],
            }
            for d in departments
        }

        roots: list[dict[str, Any]] = []
        for node in nodes.values():
            parent_id = node["parent_id"]
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                # Корень либо сирота (родитель не найден) — поднимаем на верхний уровень
                roots.append(node)

        # Сортировка детей по sort, затем по id
        def sort_children(node: dict[str, Any]) -> None:
            node["children"].sort(key=lambda n: (n["sort"] or 500, n["id"]))
            for child in node["children"]:
                sort_children(child)

        for root in roots:
            sort_children(root)
        roots.sort(key=lambda n: (n["sort"] or 500, n["id"]))

        return roots

    async def collect_descendant_ids(
        self, root_bitrix_id: str
    ) -> list[str]:
        """Return ``[root_bitrix_id, ...all descendants]`` as a list of bitrix_ids.

        BFS по in-memory карте parent→children. Root включается в ответ.
        Дубликатов нет; циклы (если в данных случайно появятся) защищены
        set'ом посещённых узлов.
        """
        root_bitrix_id = str(root_bitrix_id)
        departments = await self.list_departments()

        # parent_id → list of child bitrix_ids
        children_map: dict[str, list[str]] = defaultdict(list)
        known_ids: set[str] = set()
        for d in departments:
            known_ids.add(d.bitrix_id)
            if d.parent_id:
                children_map[d.parent_id].append(d.bitrix_id)

        if root_bitrix_id not in known_ids:
            return []

        visited: set[str] = set()
        order: list[str] = []
        queue: deque[str] = deque([root_bitrix_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            order.append(current)
            for child in children_map.get(current, []):
                if child not in visited:
                    queue.append(child)

        return order

    async def list_managers_in_departments(
        self,
        department_ids: list[str],
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Return managers (users) belonging to the given departments.

        Результат — список dict ``{bitrix_id, name, last_name, active}`` с
        уникальными ``bitrix_id`` (DISTINCT поверх junction JOIN bitrix_users).
        Если ``active_only=True``, фильтруются только ``ACTIVE='Y'``
        (хранится в колонке ``active`` таблицы ``bitrix_users``).

        Пустой список ``department_ids`` → пустой результат.
        """
        if not department_ids:
            return []

        engine = get_engine()

        # Используем expanding bindparam для IN-клаузы, чтобы список из N элементов
        # расширился в :p_1,:p_2,... на уровне SQLAlchemy (cross-DB безопасно).
        from sqlalchemy import bindparam

        ids_str = [str(i) for i in department_ids]

        where_active = ""
        if active_only:
            # bitrix_users.active хранится в разных форматах в зависимости от
            # того, как Bitrix отдал значение при sync: 'Y'/'N' (классическая
            # ACTIVE-конвенция) или '1'/'0' (boolean-cast). Принимаем оба +
            # NULL (неизвестный статус считаем активным).
            where_active = (
                " AND (bu.active IN ('Y', 'y', '1', 'true', 'TRUE') "
                "OR bu.active IS NULL)"
            )

        # DISTINCT на случай, если один юзер числится в нескольких запрошенных отделах.
        # Поле `name` / `last_name` — нижний регистр (колонки создаются DynamicTableBuilder
        # из Bitrix NAME/LAST_NAME).
        query = text(
            "SELECT DISTINCT bu.bitrix_id, bu.name, bu.last_name, bu.active "
            "FROM bitrix_user_departments bud "
            "JOIN bitrix_users bu ON bu.bitrix_id = bud.user_id "
            "WHERE bud.department_id IN :dept_ids"
            + where_active
        ).bindparams(bindparam("dept_ids", expanding=True))

        async with engine.begin() as conn:
            result = await conn.execute(query, {"dept_ids": ids_str})
            rows = result.fetchall()

        return [
            {
                "bitrix_id": str(row[0]),
                "name": row[1],
                "last_name": row[2],
                "active": row[3],
            }
            for row in rows
        ]
