"""Pydantic schemas for department endpoints.

Покрывает request/response-формы ``/api/v1/departments`` — плоский список,
иерархическое дерево, триггер sync и выборку менеджеров отдела.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DepartmentResponse(BaseModel):
    """Одна запись из ``bitrix_departments`` — плоский DTO."""

    bitrix_id: str = Field(..., description="ID отдела в Bitrix24")
    name: Optional[str] = None
    parent_id: Optional[str] = Field(
        None, description="ID родительского отдела, NULL у корня"
    )
    sort: int = 500
    uf_head: Optional[str] = Field(
        None, description="bitrix_id пользователя-руководителя"
    )

    model_config = ConfigDict(from_attributes=True)


class DepartmentTreeNode(BaseModel):
    """Узел иерархического дерева отделов.

    Использует self-reference через строковый тип — Pydantic v2 резолвит его
    при валидации. Листовые отделы имеют ``children=[]``.
    """

    id: str = Field(..., description="bitrix_id узла")
    name: Optional[str] = None
    sort: int = 500
    uf_head: Optional[str] = None
    children: List["DepartmentTreeNode"] = Field(default_factory=list)


DepartmentTreeNode.model_rebuild()


class DepartmentTreeResponse(BaseModel):
    """Ответ эндпоинта ``GET /departments/tree`` — список корневых узлов."""

    tree: List[DepartmentTreeNode] = Field(default_factory=list)


class DepartmentSyncResponse(BaseModel):
    """Ответ эндпоинта ``POST /departments/sync``.

    Значения ``status``: ``started`` (фоновая задача запущена),
    ``already_running`` (одна из синхронизаций уже идёт — HTTP 409).
    """

    status: str
    message: Optional[str] = None


class ManagerInfo(BaseModel):
    """Менеджер (юзер) из ``bitrix_users``, состоящий в запрошенных отделах."""

    bitrix_id: str
    name: Optional[str] = None
    last_name: Optional[str] = None
    active: Optional[str] = None


class ManagersListResponse(BaseModel):
    """Ответ эндпоинта ``GET /departments/{id}/managers``."""

    department_id: str
    recursive: bool
    managers: List[ManagerInfo] = Field(default_factory=list)
