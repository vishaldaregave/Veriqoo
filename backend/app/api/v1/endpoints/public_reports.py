"""Public endpoint for resolving shareable QR inspection reports."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.api.dependencies import get_report_sharing_service
from backend.app.api.errors import ErrorCode
from backend.app.api.schemas import PublicInspectionReportResponse
from backend.app.services.report_sharing import (
    ReportShareError,
    ReportShareExpiredError,
    ReportShareNotFoundError,
    ReportShareRevokedError,
    ReportShareStateError,
    ReportSharingService,
)

router = APIRouter(tags=["Public Reports"])


@router.get(
    "/r/{share_token}",
    response_model=PublicInspectionReportResponse,
    summary="Resolve Shareable QR Inspection Report",
    description="Public endpoint resolving a valid QR share token into a sanitized, localized inspection report representation.",
)
@router.get(
    "/public/reports/{share_token}",
    response_model=PublicInspectionReportResponse,
    summary="Resolve Shareable QR Inspection Report (API v1 Alias)",
    description="Public endpoint alias resolving a valid QR share token into a sanitized, localized inspection report representation.",
)
def get_public_report(
    share_token: str,
    lang: str | None = None,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    sharing_service: ReportSharingService = Depends(get_report_sharing_service),
) -> PublicInspectionReportResponse:
    """Public resolution of shared inspection report without authentication."""
    try:
        report_projection = sharing_service.resolve_share(
            raw_token=share_token,
            lang=lang,
            accept_language=accept_language,
        )
    except ReportShareExpiredError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SHARE_EXPIRED",
                "message": "This shared inspection report reference has expired.",
                "details": {},
            },
        )
    except ReportShareRevokedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SHARE_REVOKED",
                "message": "This shared inspection report reference has been revoked.",
                "details": {},
            },
        )
    except (ReportShareNotFoundError, ReportShareStateError, ReportShareError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SHARE_NOT_FOUND",
                "message": "The requested inspection report share reference was not found or is no longer available.",
                "details": {},
            },
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SHARE_NOT_FOUND",
                "message": "Unable to resolve shared inspection report.",
                "details": {},
            },
        )

    return PublicInspectionReportResponse(
        report_id=report_projection.report_id,
        inspection_id=report_projection.inspection_id,
        overall_status=report_projection.overall_status,
        language=report_projection.language,
        summary=report_projection.summary,
        counts=report_projection.counts,
        verification_results=report_projection.verification_results,
        evidence_annotations=report_projection.evidence_annotations,
        created_at=report_projection.created_at,
        share_metadata=report_projection.share_metadata,
    )
