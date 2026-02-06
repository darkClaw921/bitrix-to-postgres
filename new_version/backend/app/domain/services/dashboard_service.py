"""Dashboard service: CRUD, authentication, layout management for published dashboards."""

import json as json_mod
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import DashboardAuthError, DashboardServiceError
from app.core.logging import get_logger
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


class DashboardService:
    """Service for published dashboard operations."""

    # === Password & Token ===

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = _bcrypt.gensalt()
        return _bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    @staticmethod
    def _generate_slug() -> str:
        return secrets.token_urlsafe(16)[:32]

    @staticmethod
    def _generate_password() -> str:
        return secrets.token_urlsafe(9)

    def generate_token(self, slug: str) -> str:
        settings = get_settings()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.dashboard_token_expiry_minutes
        )
        payload = {"sub": slug, "exp": expire}
        return jwt.encode(payload, settings.dashboard_secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> str:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token, settings.dashboard_secret_key, algorithms=["HS256"]
            )
            slug: str | None = payload.get("sub")
            if slug is None:
                raise DashboardAuthError("Невалидный токен")
            return slug
        except JWTError as e:
            raise DashboardAuthError("Токен истёк или невалиден") from e

    # === CRUD ===

    async def create_dashboard(
        self, title: str, chart_ids: list[int], description: str | None = None
    ) -> dict[str, Any]:
        engine = get_engine()
        dialect = get_dialect()

        slug = self._generate_slug()
        password = self._generate_password()
        password_hash = self._hash_password(password)

        params = {
            "slug": slug,
            "title": title,
            "description": description,
            "password_hash": password_hash,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO published_dashboards (slug, title, description, password_hash) "
                "VALUES (:slug, :title, :description, :password_hash)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                dashboard_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO published_dashboards (slug, title, description, password_hash) "
                "VALUES (:slug, :title, :description, :password_hash) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                dashboard_id = result.scalar()

        # Insert dashboard_charts
        for i, chart_id in enumerate(chart_ids):
            chart_params = {
                "dashboard_id": dashboard_id,
                "chart_id": chart_id,
                "layout_x": (i % 2) * 6,
                "layout_y": (i // 2) * 4,
                "layout_w": 6,
                "layout_h": 4,
                "sort_order": i,
            }
            insert_chart = text(
                "INSERT INTO dashboard_charts "
                "(dashboard_id, chart_id, layout_x, layout_y, layout_w, layout_h, sort_order) "
                "VALUES (:dashboard_id, :chart_id, :layout_x, :layout_y, :layout_w, :layout_h, :sort_order)"
            )
            async with engine.begin() as conn:
                await conn.execute(insert_chart, chart_params)

        logger.info("Dashboard created", id=dashboard_id, slug=slug, charts=len(chart_ids))

        dashboard = await self.get_dashboard_by_id(dashboard_id)
        return {"dashboard": dashboard, "password": password}

    async def get_dashboards(
        self, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        engine = get_engine()
        offset = (page - 1) * per_page

        count_query = text("SELECT COUNT(*) FROM published_dashboards")
        list_query = text(
            "SELECT d.id, d.slug, d.title, d.description, d.is_active, d.created_at, d.updated_at, "
            "(SELECT COUNT(*) FROM dashboard_charts dc WHERE dc.dashboard_id = d.id) as chart_count "
            "FROM published_dashboards d "
            "ORDER BY d.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )

        async with engine.begin() as conn:
            total = (await conn.execute(count_query)).scalar() or 0
            result = await conn.execute(list_query, {"limit": per_page, "offset": offset})
            columns = list(result.keys())
            dashboards = [dict(zip(columns, row)) for row in result.fetchall()]

        return dashboards, total

    async def get_dashboard_by_id(self, dashboard_id: int) -> dict[str, Any] | None:
        engine = get_engine()

        query = text(
            "SELECT id, slug, title, description, is_active, created_at, updated_at "
            "FROM published_dashboards WHERE id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": dashboard_id})
            row = result.fetchone()

        if not row:
            return None

        dashboard = dict(zip(list(result.keys()), row))
        dashboard["charts"] = await self._get_dashboard_charts(dashboard_id)
        return dashboard

    async def get_dashboard_by_slug(self, slug: str) -> dict[str, Any] | None:
        engine = get_engine()

        query = text(
            "SELECT id, slug, title, description, is_active, created_at, updated_at "
            "FROM published_dashboards WHERE slug = :slug"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug})
            row = result.fetchone()

        if not row:
            return None

        dashboard = dict(zip(list(result.keys()), row))
        dashboard["charts"] = await self._get_dashboard_charts(dashboard["id"])
        return dashboard

    async def _get_dashboard_charts(self, dashboard_id: int) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT dc.id, dc.dashboard_id, dc.chart_id, dc.title_override, dc.description_override, "
            "dc.layout_x, dc.layout_y, dc.layout_w, dc.layout_h, dc.sort_order, dc.created_at, "
            "c.title as chart_title, c.description as chart_description, "
            "c.chart_type, c.chart_config, c.sql_query, c.user_prompt "
            "FROM dashboard_charts dc "
            "JOIN ai_charts c ON c.id = dc.chart_id "
            "WHERE dc.dashboard_id = :dashboard_id "
            "ORDER BY dc.sort_order, dc.layout_y, dc.layout_x"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"dashboard_id": dashboard_id})
            columns = list(result.keys())
            charts = [dict(zip(columns, row)) for row in result.fetchall()]

        # Parse chart_config JSON if string
        for chart in charts:
            if isinstance(chart.get("chart_config"), str):
                chart["chart_config"] = json_mod.loads(chart["chart_config"])

        return charts

    async def verify_password(self, slug: str, password: str) -> bool:
        engine = get_engine()

        query = text(
            "SELECT password_hash, is_active FROM published_dashboards WHERE slug = :slug"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug})
            row = result.fetchone()

        if not row:
            raise DashboardServiceError("Дашборд не найден")

        if not row[1]:  # is_active
            raise DashboardServiceError("Дашборд деактивирован")

        return self._verify_password(password, row[0])

    async def update_dashboard(
        self, dashboard_id: int, title: str | None = None, description: str | None = None
    ) -> dict[str, Any]:
        engine = get_engine()

        updates: list[str] = []
        params: dict[str, Any] = {"id": dashboard_id}

        if title is not None:
            updates.append("title = :title")
            params["title"] = title
        if description is not None:
            updates.append("description = :description")
            params["description"] = description

        if not updates:
            raise DashboardServiceError("Нет полей для обновления")

        updates.append("updated_at = NOW()")
        set_clause = ", ".join(updates)

        query = text(f"UPDATE published_dashboards SET {set_clause} WHERE id = :id")  # noqa: S608
        async with engine.begin() as conn:
            result = await conn.execute(query, params)

        if result.rowcount == 0:
            raise DashboardServiceError("Дашборд не найден")

        dashboard = await self.get_dashboard_by_id(dashboard_id)
        if not dashboard:
            raise DashboardServiceError("Дашборд не найден")
        return dashboard

    async def update_layout(
        self, dashboard_id: int, layouts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        engine = get_engine()

        for item in layouts:
            query = text(
                "UPDATE dashboard_charts "
                "SET layout_x = :x, layout_y = :y, layout_w = :w, layout_h = :h, sort_order = :sort_order "
                "WHERE id = :id AND dashboard_id = :dashboard_id"
            )
            params = {
                "id": item["id"],
                "dashboard_id": dashboard_id,
                "x": item.get("x", 0),
                "y": item.get("y", 0),
                "w": item.get("w", 6),
                "h": item.get("h", 4),
                "sort_order": item.get("sort_order", 0),
            }
            async with engine.begin() as conn:
                await conn.execute(query, params)

        logger.info("Dashboard layout updated", dashboard_id=dashboard_id, items=len(layouts))

        dashboard = await self.get_dashboard_by_id(dashboard_id)
        if not dashboard:
            raise DashboardServiceError("Дашборд не найден")
        return dashboard

    async def update_chart_override(
        self,
        dc_id: int,
        title_override: str | None = None,
        description_override: str | None = None,
    ) -> dict[str, Any]:
        engine = get_engine()

        updates: list[str] = []
        params: dict[str, Any] = {"id": dc_id}

        if title_override is not None:
            updates.append("title_override = :title_override")
            params["title_override"] = title_override
        if description_override is not None:
            updates.append("description_override = :description_override")
            params["description_override"] = description_override

        if not updates:
            raise DashboardServiceError("Нет полей для обновления")

        set_clause = ", ".join(updates)
        query = text(f"UPDATE dashboard_charts SET {set_clause} WHERE id = :id")  # noqa: S608

        async with engine.begin() as conn:
            result = await conn.execute(query, params)

        if result.rowcount == 0:
            raise DashboardServiceError("Элемент дашборда не найден")

        # Return the updated chart info
        select_query = text(
            "SELECT dc.id, dc.dashboard_id, dc.chart_id, dc.title_override, dc.description_override, "
            "dc.layout_x, dc.layout_y, dc.layout_w, dc.layout_h, dc.sort_order "
            "FROM dashboard_charts dc WHERE dc.id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(select_query, {"id": dc_id})
            row = result.fetchone()

        if not row:
            raise DashboardServiceError("Элемент дашборда не найден")

        return dict(zip(list(result.keys()), row))

    async def remove_chart(self, dc_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM dashboard_charts WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": dc_id})

        return result.rowcount > 0

    async def change_password(self, dashboard_id: int) -> str:
        engine = get_engine()

        password = self._generate_password()
        password_hash = self._hash_password(password)

        query = text(
            "UPDATE published_dashboards SET password_hash = :password_hash, updated_at = NOW() "
            "WHERE id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(
                query, {"id": dashboard_id, "password_hash": password_hash}
            )

        if result.rowcount == 0:
            raise DashboardServiceError("Дашборд не найден")

        logger.info("Dashboard password changed", dashboard_id=dashboard_id)
        return password

    async def delete_dashboard(self, dashboard_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM published_dashboards WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": dashboard_id})

        return result.rowcount > 0
