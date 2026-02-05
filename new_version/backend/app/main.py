"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import get_logger
from app.api.v1 import router as api_v1_router
from app.infrastructure.database.connection import init_db, close_db
from app.infrastructure.scheduler import (
    get_scheduler_status,
    schedule_sync_jobs,
    start_scheduler,
    stop_scheduler,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Startup
    logger.info("Starting application", version=settings.app_version)
    await init_db()

    # Start scheduler and load jobs from database
    start_scheduler()
    try:
        await schedule_sync_jobs()
        logger.info("Sync jobs scheduled from database configuration")
    except Exception as e:
        logger.warning("Could not load sync jobs from database", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down application")
    stop_scheduler()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        scheduler_status = get_scheduler_status()
        return {
            "status": "healthy",
            "version": settings.app_version,
            "scheduler": {
                "running": scheduler_status["running"],
                "jobs_count": scheduler_status["job_count"],
            },
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
