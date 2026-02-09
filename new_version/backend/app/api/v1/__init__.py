"""API v1 router."""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import auth, charts, dashboards, public, references, schema_description, selectors, sync, webhooks, status
from app.core.auth import get_current_user

router = APIRouter()

# Public routes (no auth)
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(public.router, prefix="/public", tags=["public"])

# Protected routes (require JWT)
_auth = [Depends(get_current_user)]
router.include_router(sync.router, prefix="/sync", tags=["sync"], dependencies=_auth)
router.include_router(status.router, prefix="/status", tags=["status"], dependencies=_auth)
router.include_router(charts.router, prefix="/charts", tags=["charts"], dependencies=_auth)
router.include_router(schema_description.router, prefix="/schema", tags=["schema"], dependencies=_auth)
router.include_router(references.router, prefix="/references", tags=["references"], dependencies=_auth)
router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"], dependencies=_auth)
router.include_router(selectors.router, prefix="/dashboards", tags=["selectors"], dependencies=_auth)
