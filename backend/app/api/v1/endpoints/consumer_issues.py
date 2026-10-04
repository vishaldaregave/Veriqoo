"""FastAPI endpoints for Consumer Issue Reporting (T3-3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.dependencies import get_consumer_issue_service
from backend.app.api.errors import ErrorCode
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.consumer_issues.errors import (
    ConsumerIssueNotFoundError,
    DuplicateConsumerIssueError,
    InvalidConsumerIssueError,
    InvalidImageReferenceError,
    InvalidIssueStateError,
)
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus
from backend.app.services.consumer_issues.schemas import (
    ConsumerIssueResponse,
    CreateConsumerIssueRequest,
    PaginatedConsumerIssuesResponse,
)
from backend.app.services.consumer_issues.service import ConsumerIssueService
from backend.app.services.inspection.errors import InspectionNotFoundError
from backend.app.services.saved_products.errors import SavedProductNotFoundError

router = APIRouter(prefix="/consumer-issues", tags=["Consumer Issues"])


def _serialize_issue(issue: ConsumerIssue) -> ConsumerIssueResponse:
    """Helper to convert ConsumerIssue domain model to ConsumerIssueResponse schema."""
    return ConsumerIssueResponse(
        id=issue.id,
        user_id=issue.user_id,
        inspection_id=issue.inspection_id,
        saved_product_id=issue.saved_product_id,
        issue_type=issue.issue_type,
        title=issue.title,
        description=issue.description,
        status=issue.status,
        resolution_notes=issue.resolution_notes,
        evidence_images=issue.evidence_images,
        department=issue.department,
        state_code=issue.state_code,
        district_code=issue.district_code,
        jurisdiction_verified=issue.jurisdiction_verified,
        establishment_id=issue.establishment_id,
        jurisdiction_provenance=issue.jurisdiction_provenance or "UNVERIFIED",
        jurisdiction_verified_at=issue.jurisdiction_verified_at,
        jurisdiction_verified_by=issue.jurisdiction_verified_by,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


@router.post(
    "",
    response_model=ConsumerIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Consumer Issue Report",
    description="Submit a verified consumer complaint or allegation linked to an owned inspection scan session.",
)
def submit_consumer_issue(
    request: CreateConsumerIssueRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ConsumerIssueService = Depends(get_consumer_issue_service),
) -> ConsumerIssueResponse:
    """Submit a new consumer issue report after ownership and evidence validation."""
    try:
        issue = service.create_issue(
            user_id=current_user.user_id,
            request=request,
        )
        return _serialize_issue(issue)
    except SavedProductNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.SAVED_PRODUCT_NOT_FOUND.value,
                "message": err.message if hasattr(err, "message") else str(err),
                "details": getattr(err, "details", {}),
            },
        )
    except InvalidConsumerIssueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": err.message if hasattr(err, "message") else str(err),
                "details": getattr(err, "details", {}),
            },
        )
    except InspectionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": err.message if hasattr(err, "message") else str(err),
                "details": getattr(err, "details", {}),
            },
        )
    except InvalidImageReferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_IMAGE_REFERENCE.value,
                "message": err.message,
                "details": err.details,
            },
        )
    except DuplicateConsumerIssueError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.DUPLICATE_CONSUMER_ISSUE.value,
                "message": err.message,
                "details": err.details,
            },
        )


@router.get(
    "",
    response_model=PaginatedConsumerIssuesResponse,
    status_code=status.HTTP_200_OK,
    summary="List Consumer Issues",
    description="Retrieve paginated list of consumer complaints reported by current authenticated user.",
)
def list_consumer_issues(
    limit: int = Query(20, ge=1, le=100, description="Number of items to return (1-100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status_filter: IssueStatus | None = Query(None, alias="status", description="Filter by issue status"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ConsumerIssueService = Depends(get_consumer_issue_service),
) -> PaginatedConsumerIssuesResponse:
    """List caller's reported issues with reverse-chronological ordering and optional status filter."""
    issues, total = service.list_issues(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
        status_filter=status_filter.value if status_filter else None,
    )
    items = [_serialize_issue(item) for item in issues]
    return PaginatedConsumerIssuesResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{issue_id}",
    response_model=ConsumerIssueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Consumer Issue Details",
    description="Retrieve detailed consumer issue report if owned by authenticated user.",
)
def get_consumer_issue(
    issue_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ConsumerIssueService = Depends(get_consumer_issue_service),
) -> ConsumerIssueResponse:
    """Retrieve consumer issue report details if owned by caller."""
    try:
        issue = service.get_issue(user_id=current_user.user_id, issue_id=issue_id)
        return _serialize_issue(issue)
    except ConsumerIssueNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": err.message,
                "details": err.details,
            },
        )


@router.delete(
    "/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw Consumer Issue Report",
    description="Withdraw/delete a consumer issue report if owned by caller and still in SUBMITTED status.",
)
def withdraw_consumer_issue(
    issue_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ConsumerIssueService = Depends(get_consumer_issue_service),
) -> Response:
    """Withdraw a submitted consumer issue report."""
    try:
        service.delete_issue(user_id=current_user.user_id, issue_id=issue_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConsumerIssueNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": err.message,
                "details": err.details,
            },
        )
    except InvalidIssueStateError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": err.message,
                "details": err.details,
            },
        )
