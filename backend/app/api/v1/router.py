"""API v1 Router aggregating all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.inspections import router as inspections_router


api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(inspections_router)

