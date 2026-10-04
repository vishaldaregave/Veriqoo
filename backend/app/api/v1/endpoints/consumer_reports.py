"""FastAPI router for Consumer Authority Reports and Case Integration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import (
    get_consumer_report_service,
    get_session_store,
)
from backend.app.api.errors import ErrorCode
from backend.app.api.schemas import (
    AuthorityCaseInputResponse,
    ConsumerReportListResponse,
    ConsumerReportResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.consumer_report import ConsumerReportService
from backend.app.services.inspection.errors import InspectionNotFoundError



router = APIRouter(prefix="/consumer-reports", tags=["Consumer Reports"])


def _is_authority_user(user: AuthenticatedUser) -> bool:
    """Check if the caller has an authority role in claims/metadata."""
    if user.role in ("authority", "admin", "inspector", "officer"):
        return True
    claims_role = user.claims.get("role") or user.claims.get("user_role")
    if claims_role in ("authority", "admin", "inspector", "officer"):
        return True
    app_meta = user.claims.get("app_metadata", {})
    if isinstance(app_meta, dict) and app_meta.get("role") in ("authority", "admin", "inspector", "officer"):
        return True
    return False


@router.get(
    "/{report_id}",
    response_model=ConsumerReportResponse,
    summary="Get Consumer Authority Report",
    description="Retrieve a submitted consumer authority report. Owner or authority role required.",
)
def get_consumer_report(
    report_id: str,
    lang: str | None = Query(default=None, description="Preferred language for localized explanations (en, hi, mr)"),
    report_service: ConsumerReportService = Depends(get_consumer_report_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve consumer authority report by report_id with safe 404 masking."""
    try:
        report = report_service.get_consumer_report(report_id)
    except InspectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND.value if hasattr(ErrorCode, "RESOURCE_NOT_FOUND") else "REPORT_NOT_FOUND",
                "message": f"Consumer report '{report_id}' was not found.",
                "details": {"report_id": report_id},
            },
        )

    # Ownership check: Owner or Authority can view
    is_owner = report.submitted_by == current_user.user_id
    is_auth = _is_authority_user(current_user)

    if not is_owner and not is_auth:
        # Cross-user access MUST return safe 404 to obscure existence
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND.value if hasattr(ErrorCode, "RESOURCE_NOT_FOUND") else "REPORT_NOT_FOUND",
                "message": f"Consumer report '{report_id}' was not found.",
                "details": {"report_id": report_id},
            },
        )

    return report.to_dict(lang=lang)


@router.get(
    "",
    response_model=ConsumerReportListResponse,
    summary="List Consumer Authority Reports",
    description="List consumer reports submitted by caller (or all reports if authority).",
)
def list_consumer_reports(
    report_service: ConsumerReportService = Depends(get_consumer_report_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """List reports for the current user, or all reports if authority."""
    if _is_authority_user(current_user):
        reports = report_service.list_all_consumer_reports()
    else:
        reports = report_service.list_user_consumer_reports(current_user)

    return {
        "total": len(reports),
        "reports": [r.to_dict() for r in reports],
    }


@router.get(
    "/{report_id}/case-input",
    response_model=AuthorityCaseInputResponse,
    summary="Get Typed Authority Case Input Contract",
    description="Retrieve a structured AuthorityCaseInput snapshot package for T3 case management integration.",
)
def get_authority_case_input(
    report_id: str,
    report_service: ConsumerReportService = Depends(get_consumer_report_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve typed AuthorityCaseInput contract for T3 case workflow."""
    try:
        report = report_service.get_consumer_report(report_id)
    except InspectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND.value if hasattr(ErrorCode, "RESOURCE_NOT_FOUND") else "REPORT_NOT_FOUND",
                "message": f"Consumer report '{report_id}' was not found.",
                "details": {"report_id": report_id},
            },
        )

    is_owner = report.submitted_by == current_user.user_id
    is_auth = _is_authority_user(current_user)

    if not is_owner and not is_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.RESOURCE_NOT_FOUND.value if hasattr(ErrorCode, "RESOURCE_NOT_FOUND") else "REPORT_NOT_FOUND",
                "message": f"Consumer report '{report_id}' was not found.",
                "details": {"report_id": report_id},
            },
        )

    case_input = report_service.to_authority_case_input(report)
    return case_input.to_dict()
