"""API v1 Router aggregating all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.endpoints.authority import router as authority_router
from backend.app.api.v1.endpoints.consumer_issues import router as consumer_issues_router
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.inspections import router as inspections_router
from backend.app.api.v1.endpoints.saved_products import router as saved_products_router
from backend.app.api.v1.endpoints.users import router as users_router


api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(inspections_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(saved_products_router)
api_v1_router.include_router(consumer_issues_router)
api_v1_router.include_router(authority_router)
