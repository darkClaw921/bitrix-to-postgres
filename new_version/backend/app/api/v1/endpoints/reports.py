"""Report generation and management endpoints."""

import json

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.reports import (
    PublishReportRequest,
    PublishReportResponse,
    PublishedReportLinkRequest,
    PublishedReportLinkResponse,
    PublishedReportLinkUpdateRequest,
    PublishedReportListItem,
    PublishedReportListResponse,
    PublishedReportResponse,
    ReportConversationRequest,
    ReportConversationResponse,
    ReportListResponse,
    ReportPreview,
    ReportPromptTemplateResponse,
    ReportPromptTemplateUpdateRequest,
    ReportResponse,
    ReportRunListResponse,
    ReportRunResponse,
    ReportSaveRequest,
    ReportScheduleUpdateRequest,
    ReportUpdateRequest,
    SqlQueryItem,
)
from app.api.v1.schemas.dashboards import PasswordChangeResponse
from app.config import get_settings
from app.core.exceptions import AIServiceError, ChartServiceError, ReportServiceError
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.chart_service import ChartService
from app.domain.services.report_service import ReportService

logger = get_logger(__name__)

router = APIRouter()

ai_service = AIService()
chart_service = ChartService()
report_service = ReportService()


@router.post("/converse", response_model=ReportConversationResponse)
async def converse(request: ReportConversationRequest) -> ReportConversationResponse:
    """One step of report generation dialog with LLM."""
    try:
        # Generate or use existing session ID
        session_id = request.session_id or report_service.generate_session_id()

        # Save user message
        await report_service.save_conversation_message(
            session_id=session_id,
            role="user",
            content=request.message,
        )

        # Get conversation history
        history = await report_service.get_conversation_history(session_id)
        conversation_messages = [
            {"role": m["role"], "content": m["content"]} for m in history
        ]

        # Get schema context
        schema_desc = await chart_service.get_any_latest_schema_description()
        if not schema_desc:
            raise HTTPException(
                status_code=400,
                detail="Сначала сгенерируйте описание схемы базы данных.",
            )
        schema_context = schema_desc["markdown"]

        # Generate LLM response
        result = await ai_service.generate_report_step(
            conversation_history=conversation_messages,
            schema_context=schema_context,
        )

        is_complete = result.get("is_complete", False)

        if is_complete:
            # LLM generated a complete report spec
            content = result.get("title", "Отчёт")
            sql_queries = result.get("sql_queries", [])
            analysis_prompt = result.get("analysis_prompt", "")

            # Execute SQL queries for preview
            settings = get_settings()
            data_results = []
            for q in sql_queries:
                sql = q.get("sql", "")
                purpose = q.get("purpose", "")
                try:
                    chart_service.validate_sql_query(sql)
                    allowed_tables = await chart_service.get_allowed_tables()
                    chart_service.validate_table_names(sql, allowed_tables)
                    sql = chart_service.ensure_limit(sql, settings.chart_max_rows)
                    data, exec_time = await chart_service.execute_chart_query(sql)
                    data_results.append({
                        "sql": sql,
                        "purpose": purpose,
                        "rows": data[:100],  # Limit preview rows
                        "row_count": len(data),
                        "time_ms": round(exec_time, 2),
                    })
                except (ChartServiceError, Exception) as e:
                    data_results.append({
                        "sql": sql,
                        "purpose": purpose,
                        "rows": [],
                        "row_count": 0,
                        "time_ms": 0,
                        "error": str(e),
                    })

            # Build preview
            preview = ReportPreview(
                title=result.get("title", "Отчёт"),
                description=result.get("description"),
                sql_queries=[SqlQueryItem(**q) for q in sql_queries],
                report_template=analysis_prompt,
                data_results=data_results,
            )

            # Format response content
            content_text = f"Отчёт готов: **{preview.title}**"
            if preview.description:
                content_text += f"\n\n{preview.description}"
            content_text += f"\n\nSQL-запросов: {len(sql_queries)}"

            # Save assistant message with metadata
            await report_service.save_conversation_message(
                session_id=session_id,
                role="assistant",
                content=content_text,
                metadata={
                    "is_complete": True,
                    "report_spec": result,
                },
            )

            return ReportConversationResponse(
                session_id=session_id,
                content=content_text,
                is_complete=True,
                report_preview=preview,
            )
        else:
            # LLM is asking a clarifying question
            question = result.get("question", "Пожалуйста, уточните запрос.")

            # Save assistant message
            await report_service.save_conversation_message(
                session_id=session_id,
                role="assistant",
                content=question,
            )

            return ReportConversationResponse(
                session_id=session_id,
                content=question,
                is_complete=False,
            )

    except AIServiceError as e:
        logger.error("AI service error in converse", error=e.message)
        raise HTTPException(status_code=502, detail=e.message) from e
    except ReportServiceError as e:
        logger.error("Report service error in converse", error=e.message)
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/save", response_model=ReportResponse)
async def save_report(request: ReportSaveRequest) -> ReportResponse:
    """Save a report from a completed conversation session."""
    try:
        # Get the last assistant message with report spec
        history = await report_service.get_conversation_history(request.session_id)
        if not history:
            raise HTTPException(status_code=400, detail="Сессия не найдена")

        # Find the complete report spec in conversation metadata
        report_spec = None
        user_prompt_parts = []
        for msg in history:
            if msg["role"] == "user":
                user_prompt_parts.append(msg["content"])
            if msg["role"] == "assistant" and msg.get("metadata", {}).get("is_complete"):
                report_spec = msg["metadata"].get("report_spec")

        if not report_spec:
            raise HTTPException(
                status_code=400,
                detail="Отчёт не был сгенерирован в этой сессии",
            )

        # Save report
        report_data = {
            "title": request.title,
            "description": request.description,
            "user_prompt": "\n".join(user_prompt_parts),
            "status": "draft",
            "schedule_type": request.schedule_type or "once",
            "schedule_config": request.schedule_config,
            "sql_queries": report_spec.get("sql_queries", []),
            "report_template": report_spec.get("analysis_prompt", ""),
        }

        report = await report_service.save_report(report_data)

        # Link conversation to report
        engine = chart_service._get_enum_values_map  # just need the engine import
        from app.infrastructure.database.connection import get_engine
        eng = get_engine()
        async with eng.begin() as conn:
            from sqlalchemy import text
            await conn.execute(
                text("UPDATE ai_report_conversations SET report_id = :report_id WHERE session_id = :session_id"),
                {"report_id": report["id"], "session_id": request.session_id},
            )

        return ReportResponse(**report)

    except ReportServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        logger.error("Failed to save report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}") from e


@router.get("/list", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ReportListResponse:
    """Get paginated list of saved reports."""
    reports, total = await report_service.get_reports(page, per_page)
    return ReportListResponse(
        reports=[ReportResponse(**r) for r in reports],
        total=total,
        page=page,
        per_page=per_page,
    )


# === Published Reports (protected) ===
# NOTE: these MUST be before /{report_id} to avoid route conflicts


@router.post("/publish", response_model=PublishReportResponse)
async def publish_report(request: PublishReportRequest) -> PublishReportResponse:
    """Publish a report with password protection."""
    try:
        result = await report_service.publish_report(
            report_id=request.report_id,
            title=request.title,
            description=request.description,
        )
        return PublishReportResponse(
            published_report=PublishedReportResponse(**result["published_report"]),
            password=result["password"],
        )
    except ReportServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/published", response_model=PublishedReportListResponse)
async def list_published_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PublishedReportListResponse:
    """Get paginated list of published reports."""
    reports, total = await report_service.get_published_reports(page, per_page)
    return PublishedReportListResponse(
        reports=[PublishedReportListItem(**r) for r in reports],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/published/{pub_id}", response_model=PublishedReportResponse)
async def get_published_report(pub_id: int) -> PublishedReportResponse:
    """Get a published report by ID with linked_reports."""
    report = await report_service.get_published_report_by_id(pub_id)
    if not report:
        raise HTTPException(status_code=404, detail="Опубликованный отчёт не найден")
    return PublishedReportResponse(**report)


@router.post("/published/{pub_id}/change-password", response_model=PasswordChangeResponse)
async def change_published_report_password(pub_id: int) -> PasswordChangeResponse:
    """Generate a new password for a published report."""
    try:
        password = await report_service.change_published_report_password(pub_id)
        return PasswordChangeResponse(password=password)
    except ReportServiceError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.delete("/published/{pub_id}")
async def delete_published_report(pub_id: int) -> dict:
    """Delete a published report."""
    deleted = await report_service.delete_published_report(pub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Опубликованный отчёт не найден")
    return {"deleted": True}


@router.post("/published/{pub_id}/links", response_model=PublishedReportLinkResponse)
async def add_published_report_link(
    pub_id: int, request: PublishedReportLinkRequest
) -> PublishedReportLinkResponse:
    """Add a linked published report."""
    try:
        link = await report_service.add_published_report_link(
            published_report_id=pub_id,
            linked_id=request.linked_published_report_id,
            label=request.label,
            sort_order=request.sort_order or 0,
        )
        return PublishedReportLinkResponse(**link)
    except ReportServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/published/{pub_id}/links/{link_id}")
async def remove_published_report_link(pub_id: int, link_id: int) -> dict:
    """Remove a published report link."""
    deleted = await report_service.remove_published_report_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    return {"deleted": True}


@router.put("/published/{pub_id}/links", response_model=list[PublishedReportLinkResponse])
async def update_published_report_link_order(
    pub_id: int, request: PublishedReportLinkUpdateRequest
) -> list[PublishedReportLinkResponse]:
    """Update sort order of published report links."""
    links = await report_service.update_published_report_link_order(
        pub_id, [item.model_dump() for item in request.links]
    )
    return [PublishedReportLinkResponse(**link) for link in links]


# === Single report routes (after /publish, /published) ===


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int) -> ReportResponse:
    """Get report details by ID."""
    report = await report_service.get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return ReportResponse(**report)


@router.delete("/{report_id}")
async def delete_report(report_id: int) -> dict:
    """Delete a report by ID."""
    deleted = await report_service.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return {"deleted": True}


@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report(report_id: int, request: ReportUpdateRequest) -> ReportResponse:
    """Update report fields (title, description, user_prompt, sql_queries, report_template)."""
    try:
        report = await report_service.update_report(
            report_id, request.model_dump(exclude_none=True)
        )
        return ReportResponse(**report)
    except ReportServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.patch("/{report_id}/schedule", response_model=ReportResponse)
async def update_schedule(
    report_id: int, request: ReportScheduleUpdateRequest
) -> ReportResponse:
    """Update report schedule and/or status."""
    try:
        report = await report_service.update_schedule(
            report_id, request.model_dump(exclude_none=True)
        )

        # Reschedule in APScheduler if needed
        if request.schedule_type or request.status:
            try:
                from app.infrastructure.scheduler.scheduler import (
                    remove_report_job,
                    reschedule_report,
                )
                report_data = await report_service.get_report_by_id(report_id)
                if report_data and report_data["status"] == "active" and report_data["schedule_type"] != "once":
                    schedule_config = report_data.get("schedule_config")
                    if isinstance(schedule_config, str):
                        schedule_config = json.loads(schedule_config)
                    await reschedule_report(
                        report_id,
                        report_data["schedule_type"],
                        schedule_config or {},
                    )
                else:
                    await remove_report_job(report_id)
            except Exception as e:
                logger.warning("Failed to update scheduler", error=str(e))

        return ReportResponse(**report)
    except ReportServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/{report_id}/run", response_model=ReportRunResponse)
async def run_report(report_id: int) -> ReportRunResponse:
    """Manually trigger report execution."""
    try:
        run = await report_service.execute_report(report_id, trigger_type="manual")
        return ReportRunResponse(**run)
    except ReportServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    except AIServiceError as e:
        raise HTTPException(status_code=502, detail=e.message) from e


@router.post("/{report_id}/pin", response_model=ReportResponse)
async def toggle_pin_report(report_id: int) -> ReportResponse:
    """Toggle pin status of a report."""
    try:
        report = await report_service.toggle_pin(report_id)
        return ReportResponse(**report)
    except ReportServiceError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.get("/{report_id}/runs", response_model=ReportRunListResponse)
async def list_runs(
    report_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ReportRunListResponse:
    """Get paginated list of runs for a report."""
    runs, total = await report_service.get_runs(report_id, page, per_page)
    return ReportRunListResponse(
        runs=[ReportRunResponse(**r) for r in runs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{report_id}/runs/{run_id}", response_model=ReportRunResponse)
async def get_run(report_id: int, run_id: int) -> ReportRunResponse:
    """Get details of a specific report run."""
    run = await report_service.get_run_by_id(run_id)
    if not run or run["report_id"] != report_id:
        raise HTTPException(status_code=404, detail="Запуск не найден")
    return ReportRunResponse(**run)


@router.get(
    "/prompt-template/report-context",
    response_model=ReportPromptTemplateResponse,
)
async def get_report_prompt_template() -> ReportPromptTemplateResponse:
    """Get the report context prompt template."""
    template = await report_service.get_report_prompt_template("report_context")
    if not template:
        raise HTTPException(status_code=404, detail="Промпт не найден")
    return ReportPromptTemplateResponse(**template)


@router.put(
    "/prompt-template/report-context",
    response_model=ReportPromptTemplateResponse,
)
async def update_report_prompt_template(
    request: ReportPromptTemplateUpdateRequest,
) -> ReportPromptTemplateResponse:
    """Update the report context prompt template."""
    try:
        template = await report_service.update_report_prompt_template(
            "report_context", request.content
        )
        return ReportPromptTemplateResponse(**template)
    except ReportServiceError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
