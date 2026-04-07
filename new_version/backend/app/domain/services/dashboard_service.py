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
        self,
        title: str,
        chart_ids: list[int],
        description: str | None = None,
        refresh_interval_minutes: int = 10,
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
            "refresh_interval_minutes": refresh_interval_minutes,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO published_dashboards (slug, title, description, password_hash, refresh_interval_minutes) "
                "VALUES (:slug, :title, :description, :password_hash, :refresh_interval_minutes)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                dashboard_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO published_dashboards (slug, title, description, password_hash, refresh_interval_minutes) "
                "VALUES (:slug, :title, :description, :password_hash, :refresh_interval_minutes) "
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
            "SELECT d.id, d.slug, d.title, d.description, d.is_active, "
            "d.refresh_interval_minutes, d.created_at, d.updated_at, "
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
            "SELECT id, slug, title, tab_label, description, is_active, "
            "refresh_interval_minutes, created_at, updated_at "
            "FROM published_dashboards WHERE id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": dashboard_id})
            row = result.fetchone()

        if not row:
            return None

        dashboard = dict(zip(list(result.keys()), row))
        dashboard["charts"] = await self._get_dashboard_charts(dashboard_id)
        dashboard["linked_dashboards"] = await self.get_links(dashboard_id)
        dashboard["selectors"] = await self._get_selectors(dashboard_id)
        return dashboard

    async def get_dashboard_by_slug(self, slug: str) -> dict[str, Any] | None:
        engine = get_engine()

        query = text(
            "SELECT id, slug, title, tab_label, description, is_active, "
            "refresh_interval_minutes, created_at, updated_at "
            "FROM published_dashboards WHERE slug = :slug"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug})
            row = result.fetchone()

        if not row:
            return None

        dashboard = dict(zip(list(result.keys()), row))
        dashboard["charts"] = await self._get_dashboard_charts(dashboard["id"])
        dashboard["linked_dashboards"] = await self.get_links(dashboard["id"])
        dashboard["selectors"] = await self._get_selectors(dashboard["id"])
        return dashboard

    async def _get_dashboard_charts(self, dashboard_id: int) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT dc.id, dc.dashboard_id, dc.chart_id, dc.item_type, dc.heading_config, "
            "dc.title_override, dc.description_override, "
            "dc.layout_x, dc.layout_y, dc.layout_w, dc.layout_h, dc.sort_order, dc.created_at, "
            "c.title as chart_title, c.description as chart_description, "
            "c.chart_type, c.chart_config, c.sql_query, c.user_prompt "
            "FROM dashboard_charts dc "
            "LEFT JOIN ai_charts c ON c.id = dc.chart_id "
            "WHERE dc.dashboard_id = :dashboard_id "
            "ORDER BY dc.sort_order, dc.layout_y, dc.layout_x"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"dashboard_id": dashboard_id})
            columns = list(result.keys())
            charts = [dict(zip(columns, row)) for row in result.fetchall()]

        # Parse JSON columns if returned as string (MySQL TEXT/JSON, PG TEXT fallback)
        for chart in charts:
            # Default item_type to 'chart' for legacy rows where the column may be NULL
            if not chart.get("item_type"):
                chart["item_type"] = "chart"

            if isinstance(chart.get("chart_config"), str):
                try:
                    chart["chart_config"] = json_mod.loads(chart["chart_config"])
                except (json_mod.JSONDecodeError, TypeError):
                    chart["chart_config"] = None

            if isinstance(chart.get("heading_config"), str):
                try:
                    chart["heading_config"] = json_mod.loads(chart["heading_config"])
                except (json_mod.JSONDecodeError, TypeError):
                    chart["heading_config"] = None

        return charts

    async def get_dashboard_id_by_slug(self, slug: str) -> int | None:
        """Get dashboard ID by slug (lightweight, no charts/selectors)."""
        engine = get_engine()
        query = text("SELECT id FROM published_dashboards WHERE slug = :slug AND is_active = true")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug})
            row = result.fetchone()
        return row[0] if row else None

    async def get_chart_sql_by_slug(
        self, slug: str, dc_id: int
    ) -> dict[str, Any] | None:
        """Get a single dashboard item (chart or heading) by slug + dc_id.

        For chart items the returned dict contains ``sql_query`` and ``chart_config``.
        For heading items those fields are ``None`` and ``item_type == 'heading'``;
        callers should handle that case (typically: 400 — heading has no data).
        """
        engine = get_engine()

        query = text(
            "SELECT pd.id AS dashboard_id, dc.id AS dc_id, "
            "dc.item_type, c.sql_query, c.chart_config "
            "FROM published_dashboards pd "
            "JOIN dashboard_charts dc ON dc.dashboard_id = pd.id "
            "LEFT JOIN ai_charts c ON c.id = dc.chart_id "
            "WHERE pd.slug = :slug AND dc.id = :dc_id AND pd.is_active = true"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug, "dc_id": dc_id})
            row = result.fetchone()

        if not row:
            return None
        cols = list(result.keys())
        info = dict(zip(cols, row))
        # Parse chart_config JSON if string (some dialects return TEXT for JSON cols)
        if isinstance(info.get("chart_config"), str):
            try:
                info["chart_config"] = json_mod.loads(info["chart_config"])
            except (json_mod.JSONDecodeError, TypeError):
                info["chart_config"] = None
        return info

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
        self,
        dashboard_id: int,
        title: str | None = None,
        description: str | None = None,
        refresh_interval_minutes: int | None = None,
        tab_label: str | None = None,
        clear_tab_label: bool = False,
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
        if refresh_interval_minutes is not None:
            updates.append("refresh_interval_minutes = :refresh_interval_minutes")
            params["refresh_interval_minutes"] = refresh_interval_minutes
        if clear_tab_label:
            updates.append("tab_label = NULL")
        elif tab_label is not None:
            updates.append("tab_label = :tab_label")
            params["tab_label"] = tab_label

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

    async def add_heading(
        self,
        dashboard_id: int,
        heading: dict[str, Any],
        layout: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert a new heading item into a dashboard.

        :param dashboard_id: target dashboard id (must exist).
        :param heading: heading payload (text/level/align/...) — serialized to JSON.
        :param layout: optional layout dict with keys ``layout_x``, ``layout_y``,
            ``layout_w``, ``layout_h``, ``sort_order``. Missing keys fall back to
            sensible defaults; missing ``sort_order`` is computed as MAX+1 for the
            dashboard.
        :returns: dict compatible with ``DashboardChartResponse``.
        """
        engine = get_engine()
        dialect = get_dialect()
        layout = layout or {}

        # 1. Verify the dashboard exists (404 contract via DashboardServiceError)
        check_query = text("SELECT id FROM published_dashboards WHERE id = :id")
        async with engine.begin() as conn:
            check_row = (await conn.execute(check_query, {"id": dashboard_id})).fetchone()
        if not check_row:
            raise DashboardServiceError("Дашборд не найден")

        # 2. Compute sort_order = MAX(sort_order) + 1 if not provided
        sort_order = layout.get("sort_order")
        if sort_order is None:
            sort_query = text(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 "
                "FROM dashboard_charts WHERE dashboard_id = :dashboard_id"
            )
            async with engine.begin() as conn:
                sort_order = (
                    await conn.execute(sort_query, {"dashboard_id": dashboard_id})
                ).scalar() or 0

        # 3. Serialize heading payload to JSON (kyrillic preserved)
        heading_json = json_mod.dumps(heading, ensure_ascii=False)

        params: dict[str, Any] = {
            "dashboard_id": dashboard_id,
            "item_type": "heading",
            "heading_config": heading_json,
            "layout_x": int(layout.get("layout_x", 0) or 0),
            "layout_y": int(layout.get("layout_y", 0) or 0),
            "layout_w": int(layout.get("layout_w", 12) or 12),
            "layout_h": int(layout.get("layout_h", 1) or 1),
            "sort_order": int(sort_order),
        }

        # 4. INSERT and grab inserted id (cross-DB pattern, see create_dashboard)
        if dialect == "mysql":
            insert_query = text(
                "INSERT INTO dashboard_charts "
                "(dashboard_id, chart_id, item_type, heading_config, "
                "layout_x, layout_y, layout_w, layout_h, sort_order) "
                "VALUES (:dashboard_id, NULL, :item_type, :heading_config, "
                ":layout_x, :layout_y, :layout_w, :layout_h, :sort_order)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(insert_query, params)
                dc_id = result.lastrowid
        else:
            insert_query = text(
                "INSERT INTO dashboard_charts "
                "(dashboard_id, chart_id, item_type, heading_config, "
                "layout_x, layout_y, layout_w, layout_h, sort_order) "
                "VALUES (:dashboard_id, NULL, :item_type, :heading_config, "
                ":layout_x, :layout_y, :layout_w, :layout_h, :sort_order) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(insert_query, params)
                dc_id = result.scalar()

        logger.info(
            "Dashboard heading added",
            dashboard_id=dashboard_id,
            dc_id=dc_id,
            sort_order=params["sort_order"],
        )

        # 5. Return the created item using the same projection as _get_dashboard_charts
        items = await self._get_dashboard_charts(dashboard_id)
        for item in items:
            if item.get("id") == dc_id:
                return item
        # Fallback: synthesize minimal dict (should not normally happen)
        return {
            "id": dc_id,
            "dashboard_id": dashboard_id,
            "chart_id": None,
            "item_type": "heading",
            "heading_config": heading,
            "title_override": None,
            "description_override": None,
            "layout_x": params["layout_x"],
            "layout_y": params["layout_y"],
            "layout_w": params["layout_w"],
            "layout_h": params["layout_h"],
            "sort_order": params["sort_order"],
            "chart_title": None,
            "chart_description": None,
            "chart_type": None,
            "chart_config": None,
            "sql_query": None,
            "user_prompt": None,
            "created_at": None,
        }

    async def add_chart(
        self,
        dashboard_id: int,
        chart_id: int,
        layout: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an existing AI chart to a dashboard as a new dashboard_chart row.

        Mirrors :meth:`add_heading` but inserts an ``item_type='chart'`` row
        with the given ``chart_id``. Used by the editor's "Add chart" UI to
        attach charts to dashboards that have already been published.

        :param dashboard_id: target dashboard id (must exist).
        :param chart_id: ai_charts.id of the chart to attach (must exist).
        :param layout: optional layout dict with keys ``layout_x``, ``layout_y``,
            ``layout_w``, ``layout_h``, ``sort_order``. Missing keys fall back to
            sensible defaults (6×4 in the bottom-left); missing ``sort_order`` is
            computed as MAX+1 for the dashboard so the new chart appears last.
        :returns: dict compatible with ``DashboardChartResponse`` (including the
            joined chart_title/chart_type/chart_config/sql_query fields).
        :raises DashboardServiceError: if the dashboard or chart doesn't exist.
        """
        engine = get_engine()
        dialect = get_dialect()
        layout = layout or {}

        # 1. Verify the dashboard exists
        dashboard_check = text("SELECT id FROM published_dashboards WHERE id = :id")
        async with engine.begin() as conn:
            dashboard_row = (
                await conn.execute(dashboard_check, {"id": dashboard_id})
            ).fetchone()
        if not dashboard_row:
            raise DashboardServiceError("Дашборд не найден")

        # 2. Verify the chart exists (FK constraint would also catch this but
        # the user-facing error is much nicer than a SQL violation)
        chart_check = text("SELECT id FROM ai_charts WHERE id = :id")
        async with engine.begin() as conn:
            chart_row = (await conn.execute(chart_check, {"id": chart_id})).fetchone()
        if not chart_row:
            raise DashboardServiceError("Чарт не найден")

        # 3. Compute sort_order = MAX(sort_order) + 1 if not provided
        sort_order = layout.get("sort_order")
        if sort_order is None:
            sort_query = text(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 "
                "FROM dashboard_charts WHERE dashboard_id = :dashboard_id"
            )
            async with engine.begin() as conn:
                sort_order = (
                    await conn.execute(sort_query, {"dashboard_id": dashboard_id})
                ).scalar() or 0

        # 4. Resolve layout fields. ``None`` is treated as "use default" while
        # an explicit ``0`` is preserved (so callers can pin the new chart to
        # the top-left when they really want to). For ``layout_y`` the default
        # is ``MAX(layout_y + layout_h)`` of the existing rows so the new chart
        # lands at the bottom of the layout instead of overlapping the top —
        # this avoids the editor's react-grid-layout having to compact a
        # sentinel ``9999`` value, which otherwise causes a visible jump.
        layout_x_val = layout.get("layout_x")
        layout_x_resolved = 0 if layout_x_val is None else int(layout_x_val)
        layout_w_val = layout.get("layout_w")
        layout_w_resolved = 6 if layout_w_val is None else int(layout_w_val)
        layout_h_val = layout.get("layout_h")
        layout_h_resolved = 4 if layout_h_val is None else int(layout_h_val)

        layout_y_val = layout.get("layout_y")
        if layout_y_val is None:
            max_y_query = text(
                "SELECT COALESCE(MAX(layout_y + layout_h), 0) "
                "FROM dashboard_charts WHERE dashboard_id = :dashboard_id"
            )
            async with engine.begin() as conn:
                layout_y_resolved = (
                    await conn.execute(
                        max_y_query, {"dashboard_id": dashboard_id}
                    )
                ).scalar() or 0
            layout_y_resolved = int(layout_y_resolved)
        else:
            layout_y_resolved = int(layout_y_val)

        params: dict[str, Any] = {
            "dashboard_id": dashboard_id,
            "chart_id": chart_id,
            "item_type": "chart",
            "layout_x": layout_x_resolved,
            "layout_y": layout_y_resolved,
            "layout_w": layout_w_resolved,
            "layout_h": layout_h_resolved,
            "sort_order": int(sort_order),
        }

        # 5. INSERT and grab inserted id (cross-DB pattern, see add_heading)
        if dialect == "mysql":
            insert_query = text(
                "INSERT INTO dashboard_charts "
                "(dashboard_id, chart_id, item_type, "
                "layout_x, layout_y, layout_w, layout_h, sort_order) "
                "VALUES (:dashboard_id, :chart_id, :item_type, "
                ":layout_x, :layout_y, :layout_w, :layout_h, :sort_order)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(insert_query, params)
                dc_id = result.lastrowid
        else:
            insert_query = text(
                "INSERT INTO dashboard_charts "
                "(dashboard_id, chart_id, item_type, "
                "layout_x, layout_y, layout_w, layout_h, sort_order) "
                "VALUES (:dashboard_id, :chart_id, :item_type, "
                ":layout_x, :layout_y, :layout_w, :layout_h, :sort_order) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(insert_query, params)
                dc_id = result.scalar()

        logger.info(
            "Dashboard chart added",
            dashboard_id=dashboard_id,
            chart_id=chart_id,
            dc_id=dc_id,
            sort_order=params["sort_order"],
        )

        # 6. Return the created item using the same projection as _get_dashboard_charts
        items = await self._get_dashboard_charts(dashboard_id)
        for item in items:
            if item.get("id") == dc_id:
                return item
        raise DashboardServiceError("Чарт не найден после добавления")

    async def update_heading(
        self,
        dc_id: int,
        heading: dict[str, Any],
    ) -> dict[str, Any]:
        """Update the configuration of an existing heading item.

        :param dc_id: dashboard_charts.id of the heading row.
        :param heading: new heading payload (text/level/align/...).
        :returns: dict compatible with ``DashboardChartResponse``.
        :raises DashboardServiceError: if the row is missing or is not a heading.
        """
        engine = get_engine()

        # Validate the row exists and is actually a heading
        check_query = text(
            "SELECT id, dashboard_id, item_type FROM dashboard_charts WHERE id = :id"
        )
        async with engine.begin() as conn:
            row = (await conn.execute(check_query, {"id": dc_id})).fetchone()

        if not row:
            raise DashboardServiceError("Заголовок не найден")
        if row[2] != "heading":
            raise DashboardServiceError(
                "Нельзя обновить heading на элементе типа chart"
            )
        dashboard_id = row[1]

        heading_json = json_mod.dumps(heading, ensure_ascii=False)

        update_query = text(
            "UPDATE dashboard_charts SET heading_config = :heading_config "
            "WHERE id = :id AND item_type = 'heading'"
        )
        async with engine.begin() as conn:
            result = await conn.execute(
                update_query, {"id": dc_id, "heading_config": heading_json}
            )

        if result.rowcount == 0:
            raise DashboardServiceError("Заголовок не найден")

        logger.info("Dashboard heading updated", dc_id=dc_id, dashboard_id=dashboard_id)

        # Return the updated item via shared projection
        items = await self._get_dashboard_charts(dashboard_id)
        for item in items:
            if item.get("id") == dc_id:
                return item
        raise DashboardServiceError("Заголовок не найден после обновления")

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

    # === Dashboard Links ===

    async def add_link(
        self,
        dashboard_id: int,
        linked_dashboard_id: int,
        label: str | None = None,
        sort_order: int = 0,
    ) -> dict[str, Any]:
        if dashboard_id == linked_dashboard_id:
            raise DashboardServiceError("Нельзя связать дашборд с самим собой")

        engine = get_engine()
        dialect = get_dialect()

        params = {
            "dashboard_id": dashboard_id,
            "linked_dashboard_id": linked_dashboard_id,
            "label": label,
            "sort_order": sort_order,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO dashboard_links (dashboard_id, linked_dashboard_id, label, sort_order) "
                "VALUES (:dashboard_id, :linked_dashboard_id, :label, :sort_order)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                link_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO dashboard_links (dashboard_id, linked_dashboard_id, label, sort_order) "
                "VALUES (:dashboard_id, :linked_dashboard_id, :label, :sort_order) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                link_id = result.scalar()

        logger.info("Dashboard link added", dashboard_id=dashboard_id, linked_id=linked_dashboard_id)

        # Return the created link with joined info
        links = await self.get_links(dashboard_id)
        for link in links:
            if link["id"] == link_id:
                return link
        return {"id": link_id, **params}

    async def remove_link(self, link_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM dashboard_links WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": link_id})

        return result.rowcount > 0

    async def get_links(self, dashboard_id: int) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT dl.id, dl.dashboard_id, dl.linked_dashboard_id, dl.sort_order, dl.label, "
            "pd.title as linked_title, pd.slug as linked_slug "
            "FROM dashboard_links dl "
            "JOIN published_dashboards pd ON pd.id = dl.linked_dashboard_id "
            "WHERE dl.dashboard_id = :dashboard_id "
            "ORDER BY dl.sort_order, dl.id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"dashboard_id": dashboard_id})
            columns = list(result.keys())
            links = [dict(zip(columns, row)) for row in result.fetchall()]

        return links

    async def update_link_order(
        self, dashboard_id: int, links: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        engine = get_engine()

        for item in links:
            query = text(
                "UPDATE dashboard_links SET sort_order = :sort_order "
                "WHERE id = :id AND dashboard_id = :dashboard_id"
            )
            async with engine.begin() as conn:
                await conn.execute(query, {
                    "id": item["id"],
                    "sort_order": item.get("sort_order", 0),
                    "dashboard_id": dashboard_id,
                })

        logger.info("Dashboard link order updated", dashboard_id=dashboard_id, items=len(links))
        return await self.get_links(dashboard_id)

    async def verify_linked_access(self, main_slug: str, linked_slug: str) -> bool:
        """Verify that linked_slug is linked to main_slug and both are active."""
        engine = get_engine()

        query = text(
            "SELECT 1 FROM dashboard_links dl "
            "JOIN published_dashboards main_d ON main_d.id = dl.dashboard_id "
            "JOIN published_dashboards linked_d ON linked_d.id = dl.linked_dashboard_id "
            "WHERE main_d.slug = :main_slug AND linked_d.slug = :linked_slug "
            "AND main_d.is_active = true AND linked_d.is_active = true"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {
                "main_slug": main_slug,
                "linked_slug": linked_slug,
            })
            return result.fetchone() is not None

    async def _get_selectors(self, dashboard_id: int) -> list[dict[str, Any]]:
        """Load selectors for a dashboard (delegated to SelectorService)."""
        from app.domain.services.selector_service import SelectorService

        svc = SelectorService()
        return await svc.get_selectors_for_dashboard(dashboard_id)
