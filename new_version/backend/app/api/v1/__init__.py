"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import charts, schema_description, sync, webhooks, status

router = APIRouter()

router.include_router(sync.router, prefix="/sync", tags=["sync"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(status.router, prefix="/status", tags=["status"])
router.include_router(charts.router, prefix="/charts", tags=["charts"])
router.include_router(schema_description.router, prefix="/schema", tags=["schema"])
