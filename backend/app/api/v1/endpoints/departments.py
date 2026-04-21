"""Department API endpoints.

Четыре маршрута:

- ``GET    /departments``                         — плоский список
- ``GET    /departments/tree``                    — иерархическое дерево
- ``POST   /departments/sync``                    — триггер фоновой
  синхронизации (``DepartmentSyncService.full_sync``) с дедупом через
  классовый ``_running_syncs`` (повторный вызов при активной синхронизации
  возвращает HTTP 409).
- ``GET    /departments/{id}/managers``           — активные менеджеры
  указанного отдела (опционально включая все вложенные подотделы через
  ``recursive=true``).
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.api.v1.schemas.departments import (
    DepartmentResponse,
    DepartmentSyncResponse,
    DepartmentTreeNode,
    DepartmentTreeResponse,
    ManagerInfo,
    ManagersListResponse,
)
from app.core.logging import get_logger
from app.domain.services.department_service import DepartmentService
from app.domain.services.department_sync_service import DepartmentSyncService

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /departments — плоский список
# ---------------------------------------------------------------------------


@router.get("", response_model=list[DepartmentResponse])
async def list_departments() -> list[DepartmentResponse]:
    """Return flat list of all departments ordered by (sort, bitrix_id)."""
    service = DepartmentService()
    departments = await service.list_departments()
    return [
        DepartmentResponse(
            bitrix_id=d.bitrix_id,
            name=d.name,
            parent_id=d.parent_id,
            sort=d.sort,
            uf_head=d.uf_head,
        )
        for d in departments
    ]


# ---------------------------------------------------------------------------
# GET /departments/tree — иерархия
# ---------------------------------------------------------------------------


@router.get("/tree", response_model=DepartmentTreeResponse)
async def get_departments_tree() -> DepartmentTreeResponse:
    """Return the full department hierarchy as a list of root nodes."""
    service = DepartmentService()
    raw_tree = await service.build_tree()
    return DepartmentTreeResponse(tree=[_tree_dict_to_node(n) for n in raw_tree])


def _tree_dict_to_node(raw: dict[str, Any]) -> DepartmentTreeNode:
    """Recursively convert the plain dict tree (from DepartmentService) to typed nodes."""
    return DepartmentTreeNode(
        id=str(raw["id"]),
        name=raw.get("name"),
        sort=int(raw.get("sort") or 500),
        uf_head=raw.get("uf_head"),
        children=[_tree_dict_to_node(c) for c in raw.get("children", [])],
    )


# ---------------------------------------------------------------------------
# POST /departments/sync — триггер синхронизации
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=DepartmentSyncResponse)
async def trigger_department_sync(
    background_tasks: BackgroundTasks,
) -> DepartmentSyncResponse:
    """Trigger full department sync in the background.

    Вызывает ``DepartmentSyncService.full_sync`` через FastAPI
    ``BackgroundTasks``. Дедуп обеспечивается самим сервисом
    (``_running_syncs``) — при активной синхронизации возвращаем HTTP 409.
    """
    if DepartmentSyncService.is_running():
        raise HTTPException(
            status_code=409,
            detail="Department sync is already running",
        )

    async def _run_sync() -> None:
        service = DepartmentSyncService()
        try:
            await service.full_sync()
        except Exception as e:
            # Ошибка уже залогирована и записана в sync_logs внутри full_sync().
            # BackgroundTasks всё равно поглотит exception — дублирующий лог
            # здесь делает его явным в том же модуле.
            logger.error(
                "Department background sync failed", error=str(e)
            )

    background_tasks.add_task(_run_sync)

    logger.info("Department sync enqueued via BackgroundTasks")
    return DepartmentSyncResponse(
        status="started",
        message="Department sync started in background",
    )


# ---------------------------------------------------------------------------
# GET /departments/{id}/managers — менеджеры отдела
# ---------------------------------------------------------------------------


@router.get("/{dept_id}/managers", response_model=ManagersListResponse)
async def get_department_managers(
    dept_id: str,
    recursive: bool = Query(
        True,
        description=(
            "Если True (default), вернуть также менеджеров всех подотделов. "
            "Если False — только прямых участников указанного отдела."
        ),
    ),
    active_only: bool = Query(
        True, description="Вернуть только активных пользователей (ACTIVE='Y')."
    ),
) -> ManagersListResponse:
    """Return managers belonging to the department (optionally including subdepartments).

    Если ``recursive=True`` (default), сначала собираем все ID подотделов
    через ``DepartmentService.collect_descendant_ids`` и делаем один JOIN-
    запрос. Если отдел не существует — возвращаем пустой список менеджеров
    (без 404 — это удобнее для UI с динамическими ID).
    """
    service = DepartmentService()

    if recursive:
        dept_ids = await service.collect_descendant_ids(dept_id)
    else:
        dept_ids = [str(dept_id)]

    if not dept_ids:
        # Отдел не найден или пустая иерархия → пустой список
        return ManagersListResponse(
            department_id=str(dept_id),
            recursive=recursive,
            managers=[],
        )

    raw_managers = await service.list_managers_in_departments(
        dept_ids, active_only=active_only
    )

    return ManagersListResponse(
        department_id=str(dept_id),
        recursive=recursive,
        managers=[
            ManagerInfo(
                bitrix_id=m["bitrix_id"],
                name=m.get("name"),
                last_name=m.get("last_name"),
                active=m.get("active"),
            )
            for m in raw_managers
        ],
    )
