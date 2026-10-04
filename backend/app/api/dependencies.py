"""Dependency injection providers for FastAPI API endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Generator

from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.config import Settings, get_settings
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import IngestionConfig
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator


# Singleton in-memory store for API sessions
_GLOBAL_SESSION_STORE = InMemoryInspectionStore()


def get_session_store() -> InMemoryInspectionStore:
    """Provide the in-memory inspection session store (singleton / injectable)."""
    return _GLOBAL_SESSION_STORE


def get_ingestion_service() -> ImageIngestionService:
    """Provide the Phase 5A image ingestion service."""
    return ImageIngestionService(config=IngestionConfig())


def get_pipeline_orchestrator() -> InspectionPipelineOrchestrator:
    """Provide the Phase 7 unified end-to-end inspection orchestrator."""
    return InspectionPipelineOrchestrator()


def get_app_settings() -> Settings:
    """Provide application configuration settings."""
    return get_settings()


def get_image_storage():
    """Provide ImageStorage backend (SupabaseImageStorage when configured, InMemoryImageStorage otherwise)."""
    from backend.app.services.storage import InMemoryImageStorage, SupabaseImageStorage

    settings = get_settings()
    if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
        return SupabaseImageStorage(settings=settings)
    return InMemoryImageStorage()


def get_inspection_service(
    ingestion_service: ImageIngestionService | None = None,
    orchestrator: InspectionPipelineOrchestrator | None = None,
):
    """Provide InspectionService coordinator."""
    from backend.app.services.inspection.repository import InMemoryInspectionRepository
    from backend.app.services.inspection.service import InspectionService

    storage = get_image_storage()
    repo = InMemoryInspectionRepository()
    return InspectionService(
        repository=repo,
        ingestion_service=ingestion_service or get_ingestion_service(),
        orchestrator=orchestrator or get_pipeline_orchestrator(),
        storage=storage,
    )


# Singleton execution service for process-local background task management
_GLOBAL_EXECUTION_SERVICE: Any = None


def get_inspection_execution_service(
    session_store: InMemoryInspectionStore | None = None,
    orchestrator: InspectionPipelineOrchestrator | None = None,
):
    """Provide process-local InspectionExecutionService."""
    global _GLOBAL_EXECUTION_SERVICE
    from backend.app.services.inspection.execution import InspectionExecutionService
    from backend.app.services.inspection.service import InspectionService

    if _GLOBAL_EXECUTION_SERVICE is None:
        service = get_inspection_service(orchestrator=orchestrator)
        _GLOBAL_EXECUTION_SERVICE = InspectionExecutionService(inspection_service=service)
    return _GLOBAL_EXECUTION_SERVICE


_GLOBAL_ACCOUNT_LINK_REPO: Any = None


def get_account_link_repository():
    """Provide AccountLinkRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_ACCOUNT_LINK_REPO
    from backend.app.telegram.account_linking import (
        InMemoryAccountLinkRepository,
        SupabaseAccountLinkRepository,
    )

    if _GLOBAL_ACCOUNT_LINK_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_ACCOUNT_LINK_REPO = SupabaseAccountLinkRepository(settings=settings)
        else:
            _GLOBAL_ACCOUNT_LINK_REPO = InMemoryAccountLinkRepository()
    return _GLOBAL_ACCOUNT_LINK_REPO


def get_account_linking_service():
    """Provide AccountLinkingService coordinator."""
    from backend.app.telegram.account_linking import AccountLinkingService

    repo = get_account_link_repository()
    return AccountLinkingService(repository=repo)



