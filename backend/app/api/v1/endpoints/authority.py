"""Authority Case Management REST Endpoints (T3-4 Phase 4)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import (
    get_authority_case_service,
    get_establishment_service,
)
from backend.app.api.errors import ErrorCode
from backend.app.services.authority.case_service import AuthorityCaseService
from backend.app.services.authority.dependencies import require_authority_user
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    CaseNotFoundError,
    InvalidAssignmentError,
    InvalidCaseNoteError,
    InvalidJurisdictionScopeError,
    InvalidStatusTransitionError,
)
from backend.app.services.authority.models import AuthorityPrincipal
from backend.app.services.consumer_issues.models import ConsumerIssue
from backend.app.services.authority.schemas import (
    AuditEventResponse,
    CaseAssignRequest,
    CaseAssignResponse,
    CaseAuditTimelineResponse,
    CaseDetailResponse,
    CaseListResponse,
    CaseNoteResponse,
    CaseNotesListResponse,
    CaseStatusTransitionRequest,
    CaseStatusTransitionResponse,
    CaseSummaryResponse,
    CreateCaseNoteRequest,
    VerifyCaseJurisdictionRequest,
    VerifyCaseJurisdictionResponse,
)
from backend.app.services.establishment.errors import (
    DuplicateEstablishmentError,
    EstablishmentConcurrencyError,
    EstablishmentInactiveError,
    EstablishmentNotFoundError,
    EstablishmentUnverifiedError,
    InvalidEstablishmentDataError,
)
from backend.app.services.establishment.models import RetailEstablishment
from backend.app.services.establishment.schemas import (
    CreateEstablishmentRequest,
    EstablishmentAuditEventResponse,
    EstablishmentAuditTimelineResponse,
    EstablishmentResponse,
    PaginatedEstablishmentsResponse,
    ReviewEstablishmentRequest,
)
from backend.app.services.establishment.service import EstablishmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/authority", tags=["Authority Workflow"])


@router.get("/cases", response_model=CaseListResponse)
def list_authority_cases(
    status_filter: str | None = Query(None, alias="status", description="Filter by complaint status"),
    issue_type_filter: str | None = Query(None, alias="issue_type", description="Filter by complaint category"),
    assigned: bool | None = Query(None, description="Filter by assignment status (true=assigned, false=unassigned)"),
    my_cases: bool = Query(False, description="Filter strictly to cases assigned to the current officer"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseListResponse:
    """List complaints within the authenticated officer's authorized department and jurisdiction."""
    try:
        cases, total = case_service.list_cases(
            authority=principal,
            status=status_filter,
            issue_type=issue_type_filter,
            assigned=assigned,
            my_cases=my_cases,
            limit=limit,
            offset=offset,
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to list authority cases: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while querying authority case queue.",
                "details": {},
            },
        )

    items = [
        CaseSummaryResponse(
            id=c.id,
            user_id=c.user_id,
            inspection_id=c.inspection_id,
            saved_product_id=c.saved_product_id,
            issue_type=c.issue_type,
            title=c.title,
            status=c.status,
            department=c.department,
            state_code=c.state_code,
            district_code=c.district_code,
            jurisdiction_verified=c.jurisdiction_verified,
            establishment_id=c.establishment_id,
            jurisdiction_provenance=c.jurisdiction_provenance or "UNVERIFIED",
            jurisdiction_verified_at=c.jurisdiction_verified_at,
            jurisdiction_verified_by=c.jurisdiction_verified_by,
            assigned_officer_id=c.assigned_officer_id,
            assigned_at=c.assigned_at,
            assigned_by=c.assigned_by,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in cases
    ]
    return CaseListResponse(items=items, total=total, limit=limit, offset=offset)

def _map_case_detail_response(c: ConsumerIssue) -> CaseDetailResponse:
    """Helper to map ConsumerIssue domain model to CaseDetailResponse schema."""
    return CaseDetailResponse(
        id=c.id,
        user_id=c.user_id,
        inspection_id=c.inspection_id,
        saved_product_id=c.saved_product_id,
        issue_type=c.issue_type,
        title=c.title,
        description=c.description,
        status=c.status,
        resolution_notes=c.resolution_notes,
        evidence_images=c.evidence_images,
        department=c.department,
        state_code=c.state_code,
        district_code=c.district_code,
        jurisdiction_verified=c.jurisdiction_verified,
        establishment_id=c.establishment_id,
        jurisdiction_provenance=c.jurisdiction_provenance or "UNVERIFIED",
        jurisdiction_verified_at=c.jurisdiction_verified_at,
        jurisdiction_verified_by=c.jurisdiction_verified_by,
        assigned_officer_id=c.assigned_officer_id,
        assigned_at=c.assigned_at,
        assigned_by=c.assigned_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
def get_case_details(
    case_id: str,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseDetailResponse:
    """Retrieve full details of an investigation case, verifying authority jurisdiction access."""
    try:
        c = case_service.get_case_details(authority=principal, case_id=case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to get case details for '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while retrieving case details.",
                "details": {},
            },
        )

    return _map_case_detail_response(c)


@router.post("/cases/{case_id}/assign", response_model=CaseAssignResponse)
def assign_case_officer(
    case_id: str,
    payload: CaseAssignRequest,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseAssignResponse:
    """Assign or reassign the primary investigating officer to a complaint."""
    try:
        saved_case, audit_event = case_service.assign_officer(
            authority=principal,
            case_id=case_id,
            target_officer_id=payload.officer_user_id,
            expected_assigned_officer_id=payload.expected_assigned_officer_id,
            expect_unassigned=payload.expect_unassigned,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except InvalidAssignmentError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if "conflict" in exc.message.lower() or "concurrent" in exc.message.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value if status_code == 409 else ErrorCode.INVALID_REQUEST.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to assign officer to case '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while assigning case officer.",
                "details": {},
            },
        )

    return CaseAssignResponse(
        case_id=saved_case.id,
        assigned_officer_id=saved_case.assigned_officer_id or "",
        assigned_by=saved_case.assigned_by or principal.user_id,
        assigned_at=saved_case.assigned_at or audit_event.created_at,
        event_id=audit_event.id,
    )


@router.get("/cases/{case_id}/notes", response_model=CaseNotesListResponse)
def list_case_notes(
    case_id: str,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseNotesListResponse:
    """List confidential investigation notes for an authorized complaint."""
    try:
        notes = case_service.list_investigation_notes(authority=principal, case_id=case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to list notes for case '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while fetching case notes.",
                "details": {},
            },
        )

    items = [
        CaseNoteResponse(
            id=n.id,
            issue_id=n.issue_id,
            author_id=n.author_id,
            note_text=n.note_text,
            is_internal=n.is_internal,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in notes
    ]
    return CaseNotesListResponse(items=items, total=len(items))


@router.post("/cases/{case_id}/notes", response_model=CaseNoteResponse, status_code=status.HTTP_201_CREATED)
def add_case_note(
    case_id: str,
    payload: CreateCaseNoteRequest,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseNoteResponse:
    """Record a confidential internal investigation note on a case."""
    try:
        note, _ = case_service.add_investigation_note(
            authority=principal,
            case_id=case_id,
            note_text=payload.note_text,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except InvalidCaseNoteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to add note to case '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while recording investigation note.",
                "details": {},
            },
        )

    return CaseNoteResponse(
        id=note.id,
        issue_id=note.issue_id,
        author_id=note.author_id,
        note_text=note.note_text,
        is_internal=note.is_internal,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.patch("/cases/{case_id}/status", response_model=CaseStatusTransitionResponse)
def transition_case_status(
    case_id: str,
    payload: CaseStatusTransitionRequest,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseStatusTransitionResponse:
    """Perform a validated lifecycle status transition on an investigation case."""
    try:
        saved_case, audit_event = case_service.transition_status(
            authority=principal,
            case_id=case_id,
            new_status=payload.new_status,
            resolution_notes=payload.resolution_notes,
            expected_status=payload.expected_status,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except InvalidStatusTransitionError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if "conflict" in exc.message.lower() or "concurrent" in exc.message.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value if status_code == 409 else ErrorCode.INVALID_REQUEST.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to transition status on case '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while updating case status.",
                "details": {},
            },
        )

    return CaseStatusTransitionResponse(
        case_id=saved_case.id,
        previous_status=audit_event.previous_state or "",
        new_status=saved_case.status,
        resolution_notes=saved_case.resolution_notes,
        updated_at=saved_case.updated_at,
        event_id=audit_event.id,
    )


@router.get("/cases/{case_id}/audit-timeline", response_model=CaseAuditTimelineResponse)
def get_case_audit_timeline(
    case_id: str,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> CaseAuditTimelineResponse:
    """Retrieve audit timeline for an authorized case."""
    try:
        events = case_service.list_audit_events(authority=principal, case_id=case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError, InvalidJurisdictionScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except Exception as exc:
        logger.error("Failed to get audit timeline for case '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while retrieving case audit timeline.",
                "details": {},
            },
        )

    items = [
        AuditEventResponse(
            id=e.id,
            issue_id=e.issue_id,
            actor_id=e.actor_id,
            actor_role=e.actor_role,
            event_type=e.event_type,
            previous_state=e.previous_state,
            new_state=e.new_state,
            metadata=e.metadata,
            created_at=e.created_at,
        )
        for e in events
    ]
    return CaseAuditTimelineResponse(items=items, total=len(items))


@router.post("/cases/{case_id}/verify-jurisdiction", response_model=VerifyCaseJurisdictionResponse)
def verify_case_jurisdiction(
    case_id: str,
    payload: VerifyCaseJurisdictionRequest,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    case_service: AuthorityCaseService = Depends(get_authority_case_service),
) -> VerifyCaseJurisdictionResponse:
    """Verify complaint jurisdiction against an active, verified commercial establishment."""
    try:
        saved_case, audit_event = case_service.verify_case_jurisdiction(
            authority=principal,
            case_id=case_id,
            establishment_id=payload.establishment_id,
            provenance=payload.provenance,
            verification_notes=payload.verification_notes,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value,
                "message": exc.message,
                "details": exc.details,
            },
        )
    except EstablishmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ESTABLISHMENT_NOT_FOUND",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except (EstablishmentInactiveError, EstablishmentUnverifiedError, InvalidJurisdictionScopeError, InvalidStatusTransitionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except Exception as exc:
        logger.error("Failed to verify jurisdiction for case '%s': %s", case_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while verifying case jurisdiction.",
                "details": {},
            },
        )

    verified_time = saved_case.jurisdiction_verified_at or audit_event.created_at
    verifier_id = saved_case.jurisdiction_verified_by or principal.user_id

    return VerifyCaseJurisdictionResponse(
        case_id=saved_case.id,
        establishment_id=saved_case.establishment_id or payload.establishment_id,
        state_code=saved_case.state_code or "",
        district_code=saved_case.district_code or "",
        jurisdiction_verified=saved_case.jurisdiction_verified,
        jurisdiction_provenance=saved_case.jurisdiction_provenance or payload.provenance,
        verified_at=verified_time,
        verified_by=verifier_id,
        audit_event_id=audit_event.id,
        jurisdiction_verified_at=verified_time,
        jurisdiction_verified_by=verifier_id,
        event_id=audit_event.id,
    )


def _map_establishment_response(est: RetailEstablishment) -> EstablishmentResponse:
    return EstablishmentResponse(
        id=est.id,
        trade_name=est.trade_name,
        legal_name=est.legal_name,
        gstin=est.gstin,
        lm_license_number=est.lm_license_number,
        shop_establishment_number=est.shop_establishment_number,
        state_code=est.state_code,
        district_code=est.district_code,
        pincode=est.pincode,
        physical_address=est.physical_address,
        verification_status=est.verification_status,
        verification_provenance=est.verification_provenance,
        verification_authority_id=est.verification_authority_id,
        verification_date=est.verification_date,
        verification_notes=est.verification_notes,
        is_active=est.is_active,
        created_at=est.created_at,
        updated_at=est.updated_at,
        created_by=est.created_by,
        updated_by=est.updated_by,
    )


@router.post("/establishments", response_model=EstablishmentResponse, status_code=status.HTTP_201_CREATED)
def create_establishment(
    payload: CreateEstablishmentRequest,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    establishment_service: EstablishmentService = Depends(get_establishment_service),
) -> EstablishmentResponse:
    """Onboard a new commercial premises in PENDING status."""
    try:
        est = establishment_service.create_establishment(authority=principal, data=payload)
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except DuplicateEstablishmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_ESTABLISHMENT",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except InvalidEstablishmentDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except Exception as exc:
        logger.error("Failed to onboard establishment: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while creating establishment.",
                "details": {},
            },
        )

    return _map_establishment_response(est)


@router.post("/establishments/{establishment_id}/review", response_model=EstablishmentResponse)
def review_establishment(
    establishment_id: str,
    payload: ReviewEstablishmentRequest,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    establishment_service: EstablishmentService = Depends(get_establishment_service),
) -> EstablishmentResponse:
    """Administrative review to VERIFY, SUSPEND, or REVOKE an establishment with concurrency token protection."""
    try:
        est, _ = establishment_service.review_establishment(
            authority=principal,
            establishment_id=establishment_id,
            action=payload.action,
            expected_status=payload.expected_status,
            notes=payload.get_notes(),
            provenance=payload.provenance,
        )
    except EstablishmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ESTABLISHMENT_NOT_FOUND",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except EstablishmentConcurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENT_UPDATE_CONFLICT",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except DuplicateEstablishmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_ESTABLISHMENT",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except InvalidEstablishmentDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except Exception as exc:
        logger.error("Failed to review establishment '%s': %s", establishment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while reviewing establishment.",
                "details": {},
            },
        )

    return _map_establishment_response(est)


@router.get("/establishments/{establishment_id}/audit-timeline", response_model=EstablishmentAuditTimelineResponse)
def get_establishment_audit_timeline(
    establishment_id: str,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    establishment_service: EstablishmentService = Depends(get_establishment_service),
) -> EstablishmentAuditTimelineResponse:
    """Retrieve chronological audit timeline for an establishment bounded by authority jurisdiction."""
    try:
        est = establishment_service.get_establishment(principal, establishment_id)
        if principal.jurisdiction.state_code != est.state_code or est.district_code not in principal.jurisdiction.authorized_district_codes:
            raise AuthorityJurisdictionDeniedError(
                f"Officer is not authorized to view audit events for establishment in {est.state_code}/{est.district_code}.",
                details={"establishment_id": establishment_id},
            )
        raw_events = establishment_service.repo.get_audit_events(establishment_id)
    except EstablishmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ESTABLISHMENT_NOT_FOUND",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except Exception as exc:
        logger.error("Failed to fetch audit timeline for establishment '%s': %s", establishment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while retrieving audit timeline.",
                "details": {},
            },
        )

    items = []
    for e in raw_events:
        ts = e.get("created_at")
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif isinstance(ts, datetime):
            dt = ts
        else:
            dt = datetime.now(timezone.utc)
        items.append(
            EstablishmentAuditEventResponse(
                id=str(e["id"]),
                establishment_id=str(e["establishment_id"]),
                actor_id=str(e["actor_id"]),
                actor_role=e.get("actor_role", "authority"),
                action=e["action"],
                event_type=e.get("event_type", f"ESTABLISHMENT_{e['action']}"),
                previous_status=e["previous_status"],
                new_status=e["new_status"],
                previous_is_active=bool(e["previous_is_active"]),
                new_is_active=bool(e["new_is_active"]),
                notes=e.get("notes"),
                provenance=e.get("provenance", "MANUAL"),
                metadata=e.get("metadata", {}),
                created_at=dt,
            )
        )
    return EstablishmentAuditTimelineResponse(
        establishment_id=establishment_id,
        items=items,
        total=len(items),
    )


@router.get("/establishments/{establishment_id}", response_model=EstablishmentResponse)
def get_establishment(
    establishment_id: str,
    principal: AuthorityPrincipal = Depends(require_authority_user),
    establishment_service: EstablishmentService = Depends(get_establishment_service),
) -> EstablishmentResponse:
    """Retrieve establishment details bounded by authority jurisdiction."""
    try:
        est = establishment_service.get_establishment(authority=principal, establishment_id=establishment_id)
    except EstablishmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ESTABLISHMENT_NOT_FOUND",
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except Exception as exc:
        logger.error("Failed to retrieve establishment '%s': %s", establishment_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while retrieving establishment.",
                "details": {},
            },
        )

    return _map_establishment_response(est)


@router.get("/establishments", response_model=PaginatedEstablishmentsResponse)
def list_establishments(
    district_code: str | None = Query(None, description="Optional district filter"),
    verification_status: str | None = Query(None, description="Optional verification status filter"),
    is_active: bool | None = Query(None, description="Optional active status filter"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    principal: AuthorityPrincipal = Depends(require_authority_user),
    establishment_service: EstablishmentService = Depends(get_establishment_service),
) -> PaginatedEstablishmentsResponse:
    """List establishments within the officer's jurisdiction."""
    try:
        items, total = establishment_service.list_establishments(
            authority=principal,
            district_code=district_code,
            verification_status=verification_status,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
    except (AuthorityInactiveError, AuthorityJurisdictionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": exc.message,
                "details": getattr(exc, "details", {}),
            },
        )
    except Exception as exc:
        logger.error("Failed to list establishments: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal error occurred while listing establishments.",
                "details": {},
            },
        )

    return PaginatedEstablishmentsResponse(
        items=[_map_establishment_response(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )

