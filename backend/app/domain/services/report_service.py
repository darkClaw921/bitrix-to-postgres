"""Report service: CRUD, execution, conversations, prompt templates, publishing."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt as jose_jwt
from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import PublishedReportAuthError, ReportServiceError
from app.core.logging import get_logger
from app.domain.services.chart_service import ChartService
from app.domain.services.dashboard_service import DashboardService
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)

chart_service = ChartService()


class ReportService:
    """Service for report management, execution, and conversations."""

    # === Conversation ===

    async def save_conversation_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        report_id: int | None = None,
    ) -> None:
        """Save a conversation message."""
        engine = get_engine()
        dialect = get_dialect()

        params: dict[str, Any] = {
            "session_id": session_id,
            "report_id": report_id,
            "role": role,
            "content": content,
            "metadata": json.dumps(metadata, ensure_ascii=False) if metadata else None,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO ai_report_conversations (session_id, report_id, role, content, metadata) "
                "VALUES (:session_id, :report_id, :role, :content, :metadata)"
            )
        else:
            query = text(
                "INSERT INTO ai_report_conversations (session_id, report_id, role, content, metadata) "
                "VALUES (:session_id, :report_id, :role, :content, :metadata)"
            )

        async with engine.begin() as conn:
            await conn.execute(query, params)

    async def get_conversation_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get conversation history for a session."""
        engine = get_engine()
        query = text(
            "SELECT role, content, metadata, created_at "
            "FROM ai_report_conversations "
            "WHERE session_id = :session_id "
            "ORDER BY created_at ASC"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"session_id": session_id})
            rows = result.fetchall()

        messages = []
        for row in rows:
            msg: dict[str, Any] = {
                "role": row[0],
                "content": row[1],
            }
            if row[2]:
                meta = row[2]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                msg["metadata"] = meta
            messages.append(msg)

        return messages

    def generate_session_id(self) -> str:
        """Generate a new session ID."""
        return str(uuid.uuid4())

    # === CRUD ===

    async def save_report(self, data: dict[str, Any]) -> dict[str, Any]:
        """Save a new report."""
        engine = get_engine()
        dialect = get_dialect()

        sql_queries_json = (
            json.dumps(data.get("sql_queries"), ensure_ascii=False)
            if data.get("sql_queries")
            else None
        )
        schedule_config_json = (
            json.dumps(data.get("schedule_config"), ensure_ascii=False)
            if data.get("schedule_config")
            else None
        )

        params = {
            "title": data["title"],
            "description": data.get("description"),
            "user_prompt": data["user_prompt"],
            "status": data.get("status", "draft"),
            "schedule_type": data.get("schedule_type", "once"),
            "schedule_config": schedule_config_json,
            "sql_queries": sql_queries_json,
            "report_template": data.get("report_template"),
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO ai_reports (title, description, user_prompt, status, "
                "schedule_type, schedule_config, sql_queries, report_template) "
                "VALUES (:title, :description, :user_prompt, :status, "
                ":schedule_type, :schedule_config, :sql_queries, :report_template)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                report_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO ai_reports (title, description, user_prompt, status, "
                "schedule_type, schedule_config, sql_queries, report_template) "
                "VALUES (:title, :description, :user_prompt, :status, "
                ":schedule_type, :schedule_config, :sql_queries, :report_template) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                report_id = result.scalar()

        logger.info("Report saved", report_id=report_id)
        return await self.get_report_by_id(report_id)  # type: ignore[return-value]

    async def get_reports(
        self, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated list of reports (pinned first, then newest)."""
        engine = get_engine()
        offset = (page - 1) * per_page

        count_query = text("SELECT COUNT(*) FROM ai_reports")
        list_query = text(
            "SELECT id, title, description, user_prompt, status, schedule_type, "
            "schedule_config, next_run_at, last_run_at, sql_queries, report_template, "
            "is_pinned, created_at, updated_at "
            "FROM ai_reports "
            "ORDER BY is_pinned DESC, created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )

        async with engine.begin() as conn:
            total = (await conn.execute(count_query)).scalar() or 0
            result = await conn.execute(
                list_query, {"limit": per_page, "offset": offset}
            )
            columns = list(result.keys())
            reports = [dict(zip(columns, row)) for row in result.fetchall()]

        return reports, total

    async def get_report_by_id(self, report_id: int) -> dict[str, Any] | None:
        """Get a single report by ID."""
        engine = get_engine()
        query = text(
            "SELECT id, title, description, user_prompt, status, schedule_type, "
            "schedule_config, next_run_at, last_run_at, sql_queries, report_template, "
            "is_pinned, created_at, updated_at "
            "FROM ai_reports WHERE id = :id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": report_id})
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def delete_report(self, report_id: int) -> bool:
        """Delete a report by ID. Returns True if deleted."""
        engine = get_engine()
        query = text("DELETE FROM ai_reports WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": report_id})

        return result.rowcount > 0

    async def update_schedule(
        self, report_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update report schedule and/or status."""
        report = await self.get_report_by_id(report_id)
        if not report:
            raise ReportServiceError(f"Отчёт с id={report_id} не найден")

        set_parts = []
        params: dict[str, Any] = {"id": report_id}

        if "schedule_type" in data and data["schedule_type"] is not None:
            set_parts.append("schedule_type = :schedule_type")
            params["schedule_type"] = data["schedule_type"]

        if "schedule_config" in data:
            set_parts.append("schedule_config = :schedule_config")
            params["schedule_config"] = (
                json.dumps(data["schedule_config"], ensure_ascii=False)
                if data["schedule_config"]
                else None
            )

        if "status" in data and data["status"] is not None:
            set_parts.append("status = :status")
            params["status"] = data["status"]

        if not set_parts:
            return report

        set_parts.append("updated_at = NOW()")
        set_clause = ", ".join(set_parts)

        engine = get_engine()
        query = text(f"UPDATE ai_reports SET {set_clause} WHERE id = :id")

        async with engine.begin() as conn:
            await conn.execute(query, params)

        logger.info("Report schedule updated", report_id=report_id)
        return await self.get_report_by_id(report_id)  # type: ignore[return-value]

    async def update_report(
        self, report_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update report fields (title, description, user_prompt, sql_queries, report_template)."""
        report = await self.get_report_by_id(report_id)
        if not report:
            raise ReportServiceError(f"Отчёт с id={report_id} не найден")

        set_parts = []
        params: dict[str, Any] = {"id": report_id}

        for field in ("title", "description", "user_prompt", "report_template"):
            if field in data and data[field] is not None:
                set_parts.append(f"{field} = :{field}")
                params[field] = data[field]

        if "sql_queries" in data and data["sql_queries"] is not None:
            set_parts.append("sql_queries = :sql_queries")
            params["sql_queries"] = json.dumps(data["sql_queries"], ensure_ascii=False)

        if not set_parts:
            return report

        set_parts.append("updated_at = NOW()")
        set_clause = ", ".join(set_parts)

        engine = get_engine()
        query = text(f"UPDATE ai_reports SET {set_clause} WHERE id = :id")

        async with engine.begin() as conn:
            await conn.execute(query, params)

        logger.info("Report updated", report_id=report_id)
        return await self.get_report_by_id(report_id)  # type: ignore[return-value]

    async def toggle_pin(self, report_id: int) -> dict[str, Any]:
        """Toggle the is_pinned flag on a report."""
        engine = get_engine()
        update_query = text(
            "UPDATE ai_reports SET is_pinned = NOT is_pinned, updated_at = NOW() "
            "WHERE id = :id"
        )

        async with engine.begin() as conn:
            await conn.execute(update_query, {"id": report_id})

        report = await self.get_report_by_id(report_id)
        if not report:
            raise ReportServiceError(f"Отчёт с id={report_id} не найден")
        return report

    # === Execution ===

    async def execute_report(
        self, report_id: int, trigger_type: str = "manual"
    ) -> dict[str, Any]:
        """Execute a report: run all SQL queries, analyze with LLM, save result."""
        from app.domain.services.ai_service import AIService

        ai_service = AIService()

        report = await self.get_report_by_id(report_id)
        if not report:
            raise ReportServiceError(f"Отчёт с id={report_id} не найден")

        sql_queries = report.get("sql_queries")
        if isinstance(sql_queries, str):
            sql_queries = json.loads(sql_queries)
        if not sql_queries:
            raise ReportServiceError("Отчёт не содержит SQL-запросов")

        # Create run record
        run_id = await self._create_run(report_id, trigger_type)
        start_time = time.monotonic()

        settings = get_settings()
        sql_results: list[dict[str, Any]] = []
        all_success = True

        try:
            # Execute each SQL query
            for q in sql_queries:
                sql = q.get("sql", "")
                purpose = q.get("purpose", "")

                try:
                    chart_service.validate_sql_query(sql)
                    allowed_tables = await chart_service.get_allowed_tables()
                    chart_service.validate_table_names(sql, allowed_tables)
                    sql = chart_service.ensure_limit(sql, settings.chart_max_rows)

                    data, exec_time = await chart_service.execute_chart_query(sql)
                    sql_results.append({
                        "sql": sql,
                        "purpose": purpose,
                        "rows": data,
                        "row_count": len(data),
                        "time_ms": round(exec_time, 2),
                    })
                except Exception as e:
                    logger.warning("SQL query failed during report execution", sql=sql, error=str(e))
                    sql_results.append({
                        "sql": sql,
                        "purpose": purpose,
                        "rows": [],
                        "row_count": 0,
                        "time_ms": 0,
                        "error": str(e),
                    })
                    all_success = False

            # Analyze data with LLM
            analysis_prompt = report.get("report_template", "")
            user_prompt = report.get("user_prompt", "")

            # Load report_context from prompt templates
            report_context = ""
            tpl = await self.get_report_prompt_template("report_context")
            if tpl and tpl.get("is_active"):
                report_context = tpl.get("content", "")

            result_markdown, llm_prompt = await ai_service.analyze_report_data(
                report_title=report["title"],
                sql_results=sql_results,
                analysis_prompt=analysis_prompt,
                user_prompt=user_prompt,
                report_context=report_context,
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # Update run record
            await self._update_run(
                run_id=run_id,
                status="completed",
                result_markdown=result_markdown,
                result_data=sql_results,
                sql_queries_executed=sql_results,
                execution_time_ms=elapsed_ms,
                llm_prompt=llm_prompt,
            )

            # Update report last_run_at
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    text("UPDATE ai_reports SET last_run_at = NOW(), updated_at = NOW() WHERE id = :id"),
                    {"id": report_id},
                )

            logger.info("Report executed", report_id=report_id, run_id=run_id, time_ms=elapsed_ms)
            return await self.get_run_by_id(run_id)  # type: ignore[return-value]

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            await self._update_run(
                run_id=run_id,
                status="failed",
                error_message=str(e),
                execution_time_ms=elapsed_ms,
            )
            logger.error("Report execution failed", report_id=report_id, error=str(e))
            raise ReportServiceError(f"Ошибка выполнения отчёта: {str(e)}") from e

    async def _create_run(self, report_id: int, trigger_type: str) -> int:
        """Create a new report run record."""
        engine = get_engine()
        dialect = get_dialect()

        params = {
            "report_id": report_id,
            "status": "running",
            "trigger_type": trigger_type,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO ai_report_runs (report_id, status, trigger_type, started_at) "
                "VALUES (:report_id, :status, :trigger_type, NOW())"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                return result.lastrowid  # type: ignore[return-value]
        else:
            query = text(
                "INSERT INTO ai_report_runs (report_id, status, trigger_type, started_at) "
                "VALUES (:report_id, :status, :trigger_type, NOW()) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                return result.scalar()  # type: ignore[return-value]

    async def _update_run(
        self,
        run_id: int,
        status: str,
        result_markdown: str | None = None,
        result_data: list[dict[str, Any]] | None = None,
        sql_queries_executed: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
        execution_time_ms: int | None = None,
        llm_prompt: str | None = None,
    ) -> None:
        """Update a report run record."""
        engine = get_engine()

        params: dict[str, Any] = {
            "id": run_id,
            "status": status,
            "result_markdown": result_markdown,
            "result_data": json.dumps(result_data, ensure_ascii=False, default=str) if result_data else None,
            "sql_queries_executed": json.dumps(sql_queries_executed, ensure_ascii=False, default=str) if sql_queries_executed else None,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms,
            "llm_prompt": llm_prompt,
        }

        query = text(
            "UPDATE ai_report_runs SET status = :status, result_markdown = :result_markdown, "
            "result_data = :result_data, sql_queries_executed = :sql_queries_executed, "
            "error_message = :error_message, execution_time_ms = :execution_time_ms, "
            "llm_prompt = :llm_prompt, "
            "completed_at = NOW() WHERE id = :id"
        )

        async with engine.begin() as conn:
            await conn.execute(query, params)

    # === Runs ===

    async def get_runs(
        self, report_id: int, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated list of runs for a report."""
        engine = get_engine()
        offset = (page - 1) * per_page

        count_query = text(
            "SELECT COUNT(*) FROM ai_report_runs WHERE report_id = :report_id"
        )
        list_query = text(
            "SELECT id, report_id, status, trigger_type, result_markdown, result_data, "
            "sql_queries_executed, error_message, execution_time_ms, "
            "started_at, completed_at, created_at, llm_prompt "
            "FROM ai_report_runs "
            "WHERE report_id = :report_id "
            "ORDER BY created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )

        async with engine.begin() as conn:
            total = (await conn.execute(count_query, {"report_id": report_id})).scalar() or 0
            result = await conn.execute(
                list_query, {"report_id": report_id, "limit": per_page, "offset": offset}
            )
            columns = list(result.keys())
            runs = [dict(zip(columns, row)) for row in result.fetchall()]

        return runs, total

    async def get_run_by_id(self, run_id: int) -> dict[str, Any] | None:
        """Get a single run by ID."""
        engine = get_engine()
        query = text(
            "SELECT id, report_id, status, trigger_type, result_markdown, result_data, "
            "sql_queries_executed, error_message, execution_time_ms, "
            "started_at, completed_at, created_at, llm_prompt "
            "FROM ai_report_runs WHERE id = :id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": run_id})
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    # === Prompt Templates ===

    async def get_report_prompt_template(
        self, name: str = "report_context"
    ) -> dict[str, Any] | None:
        """Get report prompt template by name."""
        engine = get_engine()
        query = text(
            "SELECT id, name, content, is_active, created_at, updated_at "
            "FROM report_prompt_templates WHERE name = :name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"name": name})
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def update_report_prompt_template(
        self, name: str, content: str
    ) -> dict[str, Any]:
        """Update report prompt template content."""
        engine = get_engine()

        query = text(
            "UPDATE report_prompt_templates SET content = :content, updated_at = NOW() "
            "WHERE name = :name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"name": name, "content": content})

        if result.rowcount == 0:
            raise ReportServiceError(f"Промпт с именем '{name}' не найден")

        logger.info("Report prompt template updated", name=name)
        template = await self.get_report_prompt_template(name)
        if not template:
            raise ReportServiceError(f"Промпт с именем '{name}' не найден")
        return template

    # === Scheduled Reports ===

    async def get_active_scheduled_reports(self) -> list[dict[str, Any]]:
        """Get all active reports with schedules (not 'once')."""
        engine = get_engine()
        query = text(
            "SELECT id, title, schedule_type, schedule_config, next_run_at "
            "FROM ai_reports "
            "WHERE status = 'active' AND schedule_type != 'once'"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    # === Published Reports ===

    def generate_report_token(self, slug: str) -> str:
        """Generate JWT token for published report access."""
        settings = get_settings()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.dashboard_token_expiry_minutes
        )
        payload = {"sub": slug, "type": "report", "exp": expire}
        return jose_jwt.encode(payload, settings.dashboard_secret_key, algorithm="HS256")

    def verify_report_token(self, token: str) -> str:
        """Verify JWT token and return slug."""
        settings = get_settings()
        try:
            payload = jose_jwt.decode(
                token, settings.dashboard_secret_key, algorithms=["HS256"]
            )
            slug: str | None = payload.get("sub")
            token_type: str | None = payload.get("type")
            if slug is None or token_type != "report":
                raise PublishedReportAuthError("Невалидный токен")
            return slug
        except JWTError as e:
            raise PublishedReportAuthError("Токен истёк или невалиден") from e

    async def publish_report(
        self,
        report_id: int,
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Publish a report with password protection."""
        report = await self.get_report_by_id(report_id)
        if not report:
            raise ReportServiceError(f"Отчёт с id={report_id} не найден")

        engine = get_engine()
        dialect = get_dialect()

        slug = DashboardService._generate_slug()
        password = DashboardService._generate_password()
        password_hash = DashboardService._hash_password(password)

        pub_title = title or report["title"]

        params = {
            "slug": slug,
            "title": pub_title,
            "description": description,
            "report_id": report_id,
            "password_hash": password_hash,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO published_reports (slug, title, description, report_id, password_hash) "
                "VALUES (:slug, :title, :description, :report_id, :password_hash)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                pub_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO published_reports (slug, title, description, report_id, password_hash) "
                "VALUES (:slug, :title, :description, :report_id, :password_hash) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                pub_id = result.scalar()

        logger.info("Report published", published_report_id=pub_id, slug=slug, report_id=report_id)

        published = await self.get_published_report_by_id(pub_id)
        return {"published_report": published, "password": password}

    async def get_published_reports(
        self, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated list of published reports with JOIN to ai_reports for report_title."""
        engine = get_engine()
        offset = (page - 1) * per_page

        count_query = text("SELECT COUNT(*) FROM published_reports")
        list_query = text(
            "SELECT pr.id, pr.slug, pr.title, pr.description, pr.report_id, "
            "pr.is_active, pr.created_at, pr.updated_at, "
            "r.title as report_title "
            "FROM published_reports pr "
            "LEFT JOIN ai_reports r ON r.id = pr.report_id "
            "ORDER BY pr.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )

        async with engine.begin() as conn:
            total = (await conn.execute(count_query)).scalar() or 0
            result = await conn.execute(list_query, {"limit": per_page, "offset": offset})
            columns = list(result.keys())
            reports = [dict(zip(columns, row)) for row in result.fetchall()]

        return reports, total

    async def get_published_report_by_id(self, pub_id: int) -> dict[str, Any] | None:
        """Get a published report by ID."""
        engine = get_engine()

        query = text(
            "SELECT id, slug, title, description, report_id, is_active, created_at, updated_at "
            "FROM published_reports WHERE id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": pub_id})
            row = result.fetchone()

        if not row:
            return None

        pub = dict(zip(list(result.keys()), row))
        pub["linked_reports"] = await self.get_published_report_links(pub_id)
        return pub

    async def delete_published_report(self, pub_id: int) -> bool:
        """Delete a published report."""
        engine = get_engine()
        query = text("DELETE FROM published_reports WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": pub_id})

        return result.rowcount > 0

    async def change_published_report_password(self, pub_id: int) -> str:
        """Generate a new password for a published report."""
        engine = get_engine()

        password = DashboardService._generate_password()
        password_hash = DashboardService._hash_password(password)

        query = text(
            "UPDATE published_reports SET password_hash = :password_hash, updated_at = NOW() "
            "WHERE id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(
                query, {"id": pub_id, "password_hash": password_hash}
            )

        if result.rowcount == 0:
            raise ReportServiceError("Опубликованный отчёт не найден")

        logger.info("Published report password changed", pub_id=pub_id)
        return password

    async def verify_published_report_password(self, slug: str, password: str) -> bool:
        """Verify password for a published report."""
        engine = get_engine()

        query = text(
            "SELECT password_hash, is_active FROM published_reports WHERE slug = :slug"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug})
            row = result.fetchone()

        if not row:
            raise ReportServiceError("Опубликованный отчёт не найден")

        if not row[1]:  # is_active
            raise ReportServiceError("Опубликованный отчёт деактивирован")

        return DashboardService._verify_password(password, row[0])

    async def get_published_report_by_slug(self, slug: str) -> dict[str, Any] | None:
        """Get published report by slug with runs and links."""
        engine = get_engine()

        query = text(
            "SELECT pr.id, pr.slug, pr.title, pr.description, pr.report_id, "
            "pr.is_active, pr.created_at, pr.updated_at, "
            "r.title as report_title "
            "FROM published_reports pr "
            "LEFT JOIN ai_reports r ON r.id = pr.report_id "
            "WHERE pr.slug = :slug"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"slug": slug})
            row = result.fetchone()

        if not row:
            return None

        pub = dict(zip(list(result.keys()), row))

        # Get completed runs
        runs = await self.get_published_report_runs(pub["report_id"])
        pub["runs"] = runs

        # Get links
        pub["linked_reports"] = await self.get_published_report_links(pub["id"])

        return pub

    async def get_published_report_runs(
        self, report_id: int, page: int = 1, per_page: int = 50
    ) -> list[dict[str, Any]]:
        """Get completed runs for a report (public-facing: only result_markdown)."""
        engine = get_engine()
        offset = (page - 1) * per_page

        query = text(
            "SELECT id, status, trigger_type, result_markdown, execution_time_ms, "
            "created_at, completed_at "
            "FROM ai_report_runs "
            "WHERE report_id = :report_id AND status = 'completed' "
            "ORDER BY created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {
                "report_id": report_id,
                "limit": per_page,
                "offset": offset,
            })
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    # === Published Report Links ===

    async def add_published_report_link(
        self,
        published_report_id: int,
        linked_id: int,
        label: str | None = None,
        sort_order: int = 0,
    ) -> dict[str, Any]:
        """Add a link between published reports."""
        if published_report_id == linked_id:
            raise ReportServiceError("Нельзя связать отчёт с самим собой")

        engine = get_engine()
        dialect = get_dialect()

        params = {
            "published_report_id": published_report_id,
            "linked_published_report_id": linked_id,
            "label": label,
            "sort_order": sort_order,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO published_report_links "
                "(published_report_id, linked_published_report_id, label, sort_order) "
                "VALUES (:published_report_id, :linked_published_report_id, :label, :sort_order)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                link_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO published_report_links "
                "(published_report_id, linked_published_report_id, label, sort_order) "
                "VALUES (:published_report_id, :linked_published_report_id, :label, :sort_order) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                link_id = result.scalar()

        logger.info("Published report link added", published_report_id=published_report_id, linked_id=linked_id)

        links = await self.get_published_report_links(published_report_id)
        for link in links:
            if link["id"] == link_id:
                return link
        return {"id": link_id, **params}

    async def remove_published_report_link(self, link_id: int) -> bool:
        """Remove a published report link."""
        engine = get_engine()
        query = text("DELETE FROM published_report_links WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": link_id})

        return result.rowcount > 0

    async def get_published_report_links(self, published_report_id: int) -> list[dict[str, Any]]:
        """Get links for a published report."""
        engine = get_engine()

        query = text(
            "SELECT prl.id, prl.published_report_id, prl.linked_published_report_id, "
            "prl.sort_order, prl.label, "
            "pr.title as linked_title, pr.slug as linked_slug "
            "FROM published_report_links prl "
            "JOIN published_reports pr ON pr.id = prl.linked_published_report_id "
            "WHERE prl.published_report_id = :published_report_id "
            "ORDER BY prl.sort_order, prl.id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"published_report_id": published_report_id})
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    async def update_published_report_link_order(
        self, published_report_id: int, links: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Update sort order of published report links."""
        engine = get_engine()

        for item in links:
            query = text(
                "UPDATE published_report_links SET sort_order = :sort_order "
                "WHERE id = :id AND published_report_id = :published_report_id"
            )
            async with engine.begin() as conn:
                await conn.execute(query, {
                    "id": item["id"],
                    "sort_order": item.get("sort_order", 0),
                    "published_report_id": published_report_id,
                })

        logger.info("Published report link order updated", published_report_id=published_report_id)
        return await self.get_published_report_links(published_report_id)

    async def verify_published_report_linked_access(
        self, main_slug: str, linked_slug: str
    ) -> bool:
        """Verify that linked_slug is linked to main_slug and both are active."""
        engine = get_engine()

        query = text(
            "SELECT 1 FROM published_report_links prl "
            "JOIN published_reports main_pr ON main_pr.id = prl.published_report_id "
            "JOIN published_reports linked_pr ON linked_pr.id = prl.linked_published_report_id "
            "WHERE main_pr.slug = :main_slug AND linked_pr.slug = :linked_slug "
            "AND main_pr.is_active = true AND linked_pr.is_active = true"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {
                "main_slug": main_slug,
                "linked_slug": linked_slug,
            })
            return result.fetchone() is not None
