"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import sync, webhooks, status

router = APIRouter()

router.include_router(sync.router, prefix="/sync", tags=["sync"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(status.router, prefix="/status", tags=["status"])
