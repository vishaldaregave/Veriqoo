"""Dependency injection providers for FastAPI API endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Generator
from fastapi import Depends

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


_GLOBAL_USER_PROFILE_REPO: Any = None


def get_user_profile_repository():
    """Provide UserProfileRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_USER_PROFILE_REPO
    from backend.app.services.user_profile.repository import (
        InMemoryUserProfileRepository,
        SupabaseUserProfileRepository,
    )

    if _GLOBAL_USER_PROFILE_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_USER_PROFILE_REPO = SupabaseUserProfileRepository(settings=settings)
        else:
            _GLOBAL_USER_PROFILE_REPO = InMemoryUserProfileRepository()
    return _GLOBAL_USER_PROFILE_REPO


def get_user_profile_service(
    repository: Any = Depends(get_user_profile_repository),
):
    """Provide UserProfileService coordinator."""
    from backend.app.services.user_profile.service import UserProfileService

    return UserProfileService(repository=repository)


_GLOBAL_SAVED_PRODUCT_REPO: Any = None


def get_saved_product_repository():
    """Provide SavedProductRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_SAVED_PRODUCT_REPO
    from backend.app.services.saved_products.repository import (
        InMemorySavedProductRepository,
        SupabaseSavedProductRepository,
    )

    if _GLOBAL_SAVED_PRODUCT_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_SAVED_PRODUCT_REPO = SupabaseSavedProductRepository(settings=settings)
        else:
            _GLOBAL_SAVED_PRODUCT_REPO = InMemorySavedProductRepository()
    return _GLOBAL_SAVED_PRODUCT_REPO


def get_saved_product_service(
    repository: Any = Depends(get_saved_product_repository),
    session_store: Any = Depends(get_session_store),
):
    """Provide SavedProductService coordinator."""
    from backend.app.services.saved_products.service import SavedProductService

    return SavedProductService(repository=repository, session_store=session_store)


_GLOBAL_CONSUMER_ISSUE_REPO: Any = None


def get_consumer_issue_repository():
    """Provide ConsumerIssueRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_CONSUMER_ISSUE_REPO
    from backend.app.services.consumer_issues.repository import (
        InMemoryConsumerIssueRepository,
        SupabaseConsumerIssueRepository,
    )

    if _GLOBAL_CONSUMER_ISSUE_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_CONSUMER_ISSUE_REPO = SupabaseConsumerIssueRepository(settings=settings)
        else:
            _GLOBAL_CONSUMER_ISSUE_REPO = InMemoryConsumerIssueRepository()
    return _GLOBAL_CONSUMER_ISSUE_REPO


_GLOBAL_LOCATION_REGISTRY: Any = None


def get_verified_location_registry():
    """Provide authoritative ServerVerifiedLocationRegistry."""
    global _GLOBAL_LOCATION_REGISTRY
    from backend.app.services.consumer_issues.jurisdiction import ServerVerifiedLocationRegistry

    if _GLOBAL_LOCATION_REGISTRY is None:
        _GLOBAL_LOCATION_REGISTRY = ServerVerifiedLocationRegistry()
    return _GLOBAL_LOCATION_REGISTRY


def get_trusted_jurisdiction_resolver(
    registry: Any = Depends(get_verified_location_registry),
):
    """Provide DefaultTrustedJurisdictionResolver coordinator."""
    from backend.app.services.consumer_issues.jurisdiction import DefaultTrustedJurisdictionResolver

    return DefaultTrustedJurisdictionResolver(registry=registry)


def get_consumer_issue_service(
    repository: Any = Depends(get_consumer_issue_repository),
    session_store: Any = Depends(get_session_store),
    saved_product_repository: Any = Depends(get_saved_product_repository),
    jurisdiction_resolver: Any = Depends(get_trusted_jurisdiction_resolver),
):
    """Provide ConsumerIssueService coordinator."""
    from backend.app.services.consumer_issues.service import ConsumerIssueService

    return ConsumerIssueService(
        repository=repository,
        session_store=session_store,
        saved_product_repository=saved_product_repository,
        jurisdiction_resolver=jurisdiction_resolver,
    )


_GLOBAL_AUTHORITY_REPO: Any = None


def get_authority_repository():
    """Provide AuthorityRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_AUTHORITY_REPO
    from backend.app.services.authority.repository import (
        InMemoryAuthorityRepository,
        SupabaseAuthorityRepository,
    )

    if _GLOBAL_AUTHORITY_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_AUTHORITY_REPO = SupabaseAuthorityRepository(settings=settings)
        else:
            _GLOBAL_AUTHORITY_REPO = InMemoryAuthorityRepository()
    return _GLOBAL_AUTHORITY_REPO


def get_authority_service(
    repository: Any = Depends(get_authority_repository),
):
    """Provide AuthorityService coordinator."""
    from backend.app.services.authority.service import AuthorityService

    return AuthorityService(repository=repository)


_GLOBAL_AUTHORITY_CASE_REPO: Any = None


def get_authority_case_repository():
    """Provide AuthorityCaseRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_AUTHORITY_CASE_REPO
    from backend.app.services.authority.case_repository import (
        InMemoryAuthorityCaseRepository,
        SupabaseAuthorityCaseRepository,
    )

    if _GLOBAL_AUTHORITY_CASE_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_AUTHORITY_CASE_REPO = SupabaseAuthorityCaseRepository(settings=settings)
        else:
            _GLOBAL_AUTHORITY_CASE_REPO = InMemoryAuthorityCaseRepository()
    return _GLOBAL_AUTHORITY_CASE_REPO


_GLOBAL_ESTABLISHMENT_REPO: Any = None


def get_establishment_repository():
    """Provide EstablishmentRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_ESTABLISHMENT_REPO
    from backend.app.services.establishment.repository import (
        InMemoryEstablishmentRepository,
        SupabaseEstablishmentRepository,
    )

    if _GLOBAL_ESTABLISHMENT_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_ESTABLISHMENT_REPO = SupabaseEstablishmentRepository(settings=settings)
        else:
            _GLOBAL_ESTABLISHMENT_REPO = InMemoryEstablishmentRepository()
    return _GLOBAL_ESTABLISHMENT_REPO


def get_establishment_service(
    repository: Any = Depends(get_establishment_repository),
):
    """Provide EstablishmentService coordinator."""
    from backend.app.services.establishment.service import EstablishmentService

    return EstablishmentService(repository=repository)


def get_authority_case_service(
    case_repository: Any = Depends(get_authority_case_repository),
    authority_repository: Any = Depends(get_authority_repository),
    establishment_repository: Any = Depends(get_establishment_repository),
):
    """Provide AuthorityCaseService coordinator."""
    from backend.app.services.authority.case_service import AuthorityCaseService

    return AuthorityCaseService(
        case_repository=case_repository,
        authority_repository=authority_repository,
        establishment_repository=establishment_repository,
    )







