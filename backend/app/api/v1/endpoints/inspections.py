"""FastAPI router for Multi-Image Inspections and Verification Execution."""

from datetime import datetime, timezone
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, status

from backend.app.api.dependencies import (
    get_consumer_intelligence_service,
    get_consumer_report_service,
    get_consumer_result_service,
    get_evidence_chain_service,
    get_ingestion_service,
    get_inspection_repository,
    get_pipeline_orchestrator,
    get_report_sharing_service,
    get_server_revalidation_service,
    get_session_store,
    get_sync_ingestion_service,
)
from backend.app.api.errors import ErrorCode, create_error_response
from backend.app.api.schemas import (
    ConsumerComplianceResultResponse,
    ConsumerReportResponse,
    ConsumerScanIntelligenceResponse,
    CreateConsumerReportRequest,
    CreateInspectionRequest,
    CreateShareRequest,
    CreateShareResponse,
    EvidenceChainEventResponse,
    EvidenceIntegrityResponse,
    EvidenceRecordResponse,
    ImageUploadResponse,
    InspectionEvidenceSummaryResponse,
    InspectionImageResponse,
    InspectionListResponse,
    InspectionReportResponse,
    InspectionResponse,
    QRPayloadResponse,
    RevokeShareResponse,
    RunInspectionRequest,
    RunInspectionResponse,
    ServerRevalidationResponse,
    SyncAcknowledgementResponse,
    SyncBatchRequest,
    SyncBatchResponse,
    SyncManifestResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.offline_sync import (
    ServerRevalidationResult,
    ServerRevalidationService,
    SyncIngestionService,
    SyncOperation,
    SyncStatus,
)
from backend.app.services.applicability.models import InspectionFact
from backend.app.services.consumer_intelligence import ConsumerIntelligenceService
from backend.app.services.consumer_report import (
    ConsumerReportEligibility,
    ConsumerReportService,
)
from backend.app.services.consumer_result import ConsumerResultService
from backend.app.services.evidence.errors import InvalidImageError
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.inspection.errors import InspectionNotFoundError, InvalidInspectionError
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection.repository import InspectionRepository
from backend.app.services.inspection_pipeline.errors import (
    InvalidPipelineInputError,
    PipelineError,
)
from backend.app.services.report_sharing import (
    ReportShareError,
    ReportSharePermissionError,
    ReportShareStateError,
    ReportSharingService,
)
from backend.app.services.inspection_pipeline.models import InspectionPipelineRequest
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator


router = APIRouter(prefix="/inspections", tags=["Inspections"])


def _serialize_session(session: InspectionSession) -> InspectionResponse:
    """Helper to serialize an InspectionSession into standard InspectionResponse schema."""
    insp = session.inspection
    image_responses = [
        InspectionImageResponse(
            image_id=img.image_id,
            sequence=img.sequence,
            added_at=img.added_at.isoformat(),
            source_hash=img.source_hash,
            normalized_hash=img.normalized_hash,
            storage_path=img.storage_path,
        )
        for img in insp.images
    ]
    return InspectionResponse(
        inspection_id=insp.inspection_id,
        created_at=insp.created_at.isoformat(),
        status=insp.status.value,
        image_count=insp.image_count,
        images=image_responses,
        metadata=dict(insp.metadata),
        has_report=session.report is not None,
        owner_id=insp.owner_id,
    )


def _verify_inspection_ownership(
    session: InspectionSession,
    current_user: AuthenticatedUser,
    inspection_id: str,
) -> None:
    """Assert authenticated user owns the inspection. Raises safe 404 to avoid IDOR or enumeration."""
    insp = session.inspection
    if insp.owner_id and insp.owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )


def _verify_inspection_access(
    inspection_id: str,
    current_user: AuthenticatedUser,
    store: InMemoryInspectionStore,
    inspection_repo: InspectionRepository,
) -> None:
    """Assert authenticated user owns the inspection across session store and persistent repo."""
    session = store.get_session_optional(inspection_id)
    if session is not None:
        _verify_inspection_ownership(session, current_user, inspection_id)
        return

    try:
        insp = inspection_repo.get_inspection(inspection_id)
        if insp.owner_id and insp.owner_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                    "message": f"Inspection with ID '{inspection_id}' not found.",
                    "details": {"inspection_id": inspection_id},
                },
            )
    except InspectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )


@router.post(
    "",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Inspection Session",
    description="Initialize a new in-memory inspection container in COLLECTING state owned by the authenticated user.",
)
def create_inspection(
    request: CreateInspectionRequest | None = None,
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> InspectionResponse:
    """Create a new in-memory inspection session bound to authenticated owner."""
    meta = dict(request.metadata if request and request.metadata else {})
    # Strip any client-supplied spoofed ownership attributes
    meta.pop("user_id", None)
    meta.pop("owner_id", None)
    if request and request.inspection_date:
        meta["inspection_date"] = request.inspection_date

    session = store.create_session(metadata=meta, owner_id=current_user.user_id)
    return _serialize_session(session)


@router.get(
    "",
    response_model=InspectionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Consumer Scan History",
    description="Retrieve paginated list of previous inspection sessions owned by the authenticated caller in reverse-chronological order.",
)
def list_my_inspections(
    limit: int = Query(20, ge=1, le=100, description="Number of inspections to return (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> InspectionListResponse:
    """Retrieve caller's scan history with reverse-chronological ordering and pagination."""
    sessions, total = store.list_sessions_by_owner(
        owner_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )
    items = [_serialize_session(s) for s in sessions]
    return InspectionListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Get Inspection Session",
    description="Retrieve inspection session metadata and ordered image references.",
)
def get_inspection(
    inspection_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    inspection_repo: InspectionRepository = Depends(get_inspection_repository),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> InspectionResponse:
    """Retrieve inspection session state if owned by caller."""
    session = store.get_session_optional(inspection_id)
    if session is None:
        try:
            insp = inspection_repo.get_inspection(inspection_id)
            report = inspection_repo.get_report(inspection_id)
            session = store.create_session(
                inspection_id=insp.inspection_id,
                metadata=dict(insp.metadata),
                owner_id=insp.owner_id,
            )
            session.inspection.status = insp.status
            session.report = report
        except Exception:
            session = store.get_session(inspection_id)

    _verify_inspection_ownership(session, current_user, inspection_id)
    return _serialize_session(session)


@router.post(
    "/{inspection_id}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Inspection Image",
    description="Upload, validate, and normalize a package photograph into the inspection session.",
)
async def upload_image(
    inspection_id: str,
    file: UploadFile = File(..., description="Package photograph (JPEG, PNG, or WEBP)"),
    store: InMemoryInspectionStore = Depends(get_session_store),
    ingestion_service: ImageIngestionService = Depends(get_ingestion_service),
    evidence_service: Any = Depends(get_evidence_chain_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ImageUploadResponse:
    """Upload and ingest package photograph evidence into an inspection owned by caller."""
    # Ensure inspection session exists and verify ownership before consuming bytes
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    # Read uploaded bytes
    contents = await file.read()
    if not contents or len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.IMAGE_EMPTY.value,
                "message": "Uploaded image file is empty (0 bytes).",
                "details": {"filename": file.filename},
            },
        )

    # Ingest and normalize image
    artifact = ingestion_service.ingest_bytes(
        data=contents,
        source_name=file.filename or "upload.jpg",
        metadata={"content_type": file.content_type},
    )

    # Add reference and artifact to session store
    image_ref = store.add_artifact(inspection_id, artifact)

    # Register in cryptographic evidence chain
    try:
        evidence_service.register_evidence(
            inspection_id=inspection_id,
            data=contents,
            image_id=artifact.image_id,
            original_filename=file.filename or "upload.jpg",
            media_type=file.content_type or "image/jpeg",
            submitted_by=current_user.user_id,
            source_type="UPLOAD",
            storage_reference=image_ref.storage_path,
        )
    except Exception:
        pass  # Non-fatal if evidence chain service is optional or fails

    return ImageUploadResponse(
        image_id=artifact.image_id,
        sequence=image_ref.sequence,
        source_hash=artifact.source_hash,
        normalized_hash=artifact.normalized_hash,
        source_format=artifact.source_format,
        normalized_format=artifact.normalized_format,
        original_width=artifact.original_width,
        original_height=artifact.original_height,
        normalized_width=artifact.normalized_width,
        normalized_height=artifact.normalized_height,
        file_size_bytes=artifact.file_size_bytes,
        source_file_size_bytes=artifact.source_file_size_bytes,
        color_mode=artifact.color_mode,
        was_resized=artifact.was_resized,
        was_orientation_corrected=artifact.was_orientation_corrected,
        storage_path=image_ref.storage_path,
    )


@router.post(
    "/{inspection_id}/run",
    response_model=RunInspectionResponse,
    summary="Execute Inspection Pipeline (Background / Manual Retry)",
    description=(
        "Trigger asynchronous background execution of the Phase 7 inspection pipeline. "
        "Returns immediately with status RUNNING. "
        "If status is FAILED, calling this endpoint initiates an explicit manual retry. "
        "If status is RUNNING or COMPLETED, returns the current status idempotently without duplicate execution."
    ),
)
def run_inspection(
    inspection_id: str,
    background_tasks: BackgroundTasks,
    request: RunInspectionRequest | None = None,
    store: InMemoryInspectionStore = Depends(get_session_store),
    orchestrator: InspectionPipelineOrchestrator = Depends(get_pipeline_orchestrator),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RunInspectionResponse:
    """Execute end-to-end verification orchestrator for an inspection owned by caller."""
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    if session.report is not None or session.inspection.is_completed:
        return RunInspectionResponse(
            inspection_id=inspection_id,
            status=InspectionStatus.COMPLETED.value,
            message="Inspection execution is already completed.",
        )

    if session.inspection.is_running:
        return RunInspectionResponse(
            inspection_id=inspection_id,
            status=InspectionStatus.RUNNING.value,
            message="Inspection execution is currently running.",
        )

    # Convert request facts if present
    req_facts: list[InspectionFact] = []
    if request and request.inspection_facts:
        for idx, fact_dict in enumerate(request.inspection_facts):
            fact_id = fact_dict.get("id", str(uuid.uuid4()))
            run_id = fact_dict.get("run_id", inspection_id)
            fact_key = fact_dict.get("fact_key", f"fact_{idx}")
            value = fact_dict.get("value")
            unit = fact_dict.get("unit")
            req_facts.append(
                InspectionFact(
                    id=fact_id,
                    run_id=run_id,
                    fact_key=fact_key,
                    value=value,
                    unit=unit,
                )
            )

    req_context = request.applicability_context if request else {}
    req_targets = request.target_requirements if request else []
    req_meta = request.metadata if request else {}

    # Transition state to RUNNING immediately
    session.inspection.status = InspectionStatus.RUNNING
    session.updated_at = datetime.now(timezone.utc)

    def _execute_pipeline_task() -> None:
        try:
            artifacts = store.get_artifacts(inspection_id)
            pipeline_req = InspectionPipelineRequest(
                inspection_id=inspection_id,
                image_artifacts=artifacts,
                inspection_facts=req_facts,
                applicability_context=req_context,
                target_requirements=req_targets,
                metadata=req_meta,
            )
            report = orchestrator.run(pipeline_req)
            store.store_report(inspection_id, report)
        except Exception as exc:
            from backend.app.services.inspection.execution import sanitize_error_message
            sess = store.get_session(inspection_id)
            sess.inspection.status = InspectionStatus.FAILED
            sess.inspection.metadata["execution_error"] = sanitize_error_message(str(exc))
            sess.updated_at = datetime.now(timezone.utc)

    if background_tasks is not None:
        background_tasks.add_task(_execute_pipeline_task)
    else:
        _execute_pipeline_task()

    return RunInspectionResponse(
        inspection_id=inspection_id,
        status=InspectionStatus.RUNNING.value,
        message="Inspection execution started.",
    )


@router.get(
    "/{inspection_id}/report",
    response_model=InspectionReportResponse,
    summary="Get Inspection Report",
    description="Retrieve the latest inspection verification report in the requested or negotiated language.",
)
def get_report(
    inspection_id: str,
    lang: str | None = None,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    store: InMemoryInspectionStore = Depends(get_session_store),
    inspection_repo: InspectionRepository = Depends(get_inspection_repository),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve inspection report for completed run owned by caller."""
    session = store.get_session_optional(inspection_id)
    if session is None:
        try:
            insp = inspection_repo.get_inspection(inspection_id)
            report = inspection_repo.get_report(inspection_id)
            session = store.create_session(
                inspection_id=insp.inspection_id,
                metadata=dict(insp.metadata),
                owner_id=insp.owner_id,
            )
            session.inspection.status = insp.status
            session.report = report
        except Exception:
            session = store.get_session(inspection_id)

    _verify_inspection_ownership(session, current_user, inspection_id)

    if session.inspection.is_failed:
        error_msg = session.inspection.metadata.get("execution_error", "Inspection pipeline execution failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.PIPELINE_ERROR.value,
                "message": f"Inspection pipeline execution failed: {error_msg}",
                "details": {"error": error_msg},
            },
        )

    report = store.get_report(inspection_id)
    if report is None:
        status_str = session.inspection.status.value
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.REPORT_NOT_AVAILABLE.value,
                "message": f"Inspection report has not been generated for inspection '{inspection_id}' (status: {status_str}).",
                "details": {"inspection_id": inspection_id, "status": status_str},
            },
        )

    # Negotiate language according to cascading precedence
    from backend.app.localization.service import get_localization_service
    loc = get_localization_service()
    user_claims = current_user.claims if hasattr(current_user, "claims") else None
    target_lang = loc.resolve_language(
        explicit_lang=lang,
        inspection_meta=session.inspection.metadata,
        user_claims=user_claims,
        accept_language_header=accept_language,
    )

    return report.to_dict(lang=target_lang.value)


@router.post(
    "/{inspection_id}/share",
    response_model=CreateShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Shareable Inspection Report QR Reference",
    description="Generate a secure, high-entropy, opaque report share token and QR URL for a completed inspection.",
)
def create_share(
    inspection_id: str,
    request: CreateShareRequest | None = None,
    store: InMemoryInspectionStore = Depends(get_session_store),
    sharing_service: ReportSharingService = Depends(get_report_sharing_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CreateShareResponse:
    """Create a share reference and QR payload for an inspection owned by the caller."""
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    if session.inspection.is_failed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": f"Cannot share failed inspection '{inspection_id}'.",
                "details": {"inspection_id": inspection_id},
            },
        )

    if session.inspection.status != InspectionStatus.COMPLETED or session.report is None:
        status_str = session.inspection.status.value
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": f"Cannot share inspection in state '{status_str}'. Inspection must be COMPLETED with an existing report.",
                "details": {"inspection_id": inspection_id, "status": status_str},
            },
        )

    expires_in = request.expires_in_seconds if request else None
    meta = request.metadata if request else {}

    try:
        share, raw_token, qr_payload = sharing_service.create_share(
            inspection_id=inspection_id,
            created_by=current_user.user_id,
            expires_in_seconds=expires_in,
            metadata=meta,
        )
    except ReportSharePermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )
    except ReportShareStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": e.message,
                "details": e.details,
            },
        )

    return CreateShareResponse(
        share_id=share.id,
        inspection_id=share.inspection_id,
        qr=QRPayloadResponse(
            url=qr_payload.url,
            token_id=qr_payload.token_id,
            format=qr_payload.format,
            version=qr_payload.version,
        ),
        created_at=share.created_at.isoformat(),
        expires_at=share.expires_at.isoformat() if share.expires_at else None,
        status=share.status().value,
    )


@router.post(
    "/{inspection_id}/share/{share_id}/revoke",
    response_model=RevokeShareResponse,
    summary="Revoke Report Share",
    description="Immediately revoke an active share reference and its associated QR access.",
)
def revoke_share(
    inspection_id: str,
    share_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    sharing_service: ReportSharingService = Depends(get_report_sharing_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RevokeShareResponse:
    """Revoke an active report share owned by the caller."""
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    try:
        share = sharing_service.revoke_share(
            inspection_id=inspection_id,
            share_id=share_id,
            current_user_id=current_user.user_id,
        )
    except ReportSharePermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )
    except ReportShareError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SHARE_NOT_FOUND",
                "message": e.message,
                "details": e.details,
            },
        )

    revoked_at_str = share.revoked_at.isoformat() if share.revoked_at else datetime.now(timezone.utc).isoformat()
    return RevokeShareResponse(
        share_id=share.id,
        inspection_id=share.inspection_id,
        status="REVOKED",
        revoked_at=revoked_at_str,
    )


@router.get(
    "/{inspection_id}/consumer-intelligence",
    response_model=ConsumerScanIntelligenceResponse,
    summary="Get Consumer Scan Intelligence",
    description="Retrieve structured product identity, scan quality diagnostics, consumer risk classification, and guidance actions for a completed inspection.",
)
def get_consumer_intelligence(
    inspection_id: str,
    lang: str | None = None,
    selling_price: float | None = None,
    store: InMemoryInspectionStore = Depends(get_session_store),
    intelligence_service: ConsumerIntelligenceService = Depends(get_consumer_intelligence_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve consumer scan intelligence for an inspection session owned by the caller."""
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    if session.inspection.is_failed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": f"Cannot generate consumer intelligence for failed inspection '{inspection_id}'.",
                "details": {"inspection_id": inspection_id},
            },
        )

    if session.inspection.status != InspectionStatus.COMPLETED or session.report is None:
        status_str = session.inspection.status.value
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": f"Cannot generate consumer intelligence for inspection in state '{status_str}'. Inspection must be COMPLETED with an existing report.",
                "details": {"inspection_id": inspection_id, "status": status_str},
            },
        )

    intelligence = intelligence_service.generate_intelligence(
        inspection_id=inspection_id,
        lang=lang,
        user_selling_price=selling_price,
    )
    return intelligence.to_dict()


@router.get(
    "/{inspection_id}/consumer-result",
    response_model=ConsumerComplianceResultResponse,
    summary="Get Consumer Compliance Result & Explanation",
    description="Retrieve consumer-oriented compliance result, plain-language explanations, findings, score, limitations, and actions.",
)
def get_consumer_result(
    inspection_id: str,
    lang: str | None = None,
    store: InMemoryInspectionStore = Depends(get_session_store),
    result_service: ConsumerResultService = Depends(get_consumer_result_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve consumer compliance result and explanation for an inspection session owned by the caller."""
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    if session.inspection.is_failed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": f"Cannot generate consumer result for failed inspection '{inspection_id}'.",
                "details": {"inspection_id": inspection_id},
            },
        )

    if session.inspection.status != InspectionStatus.COMPLETED or session.report is None:
        status_str = session.inspection.status.value
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": f"Cannot generate consumer result for inspection in state '{status_str}'. Inspection must be COMPLETED with an existing report.",
                "details": {"inspection_id": inspection_id, "status": status_str},
            },
        )

    result = result_service.generate_consumer_result(
        inspection_id=inspection_id,
        lang=lang,
    )
    return result.to_dict()


@router.post(
    "/{inspection_id}/consumer-reports",
    response_model=ConsumerReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Consumer Authority Report",
    description="Package completed inspection with compliance issues into an authority-ready, evidence-backed report.",
)
def create_consumer_report(
    inspection_id: str,
    request: CreateConsumerReportRequest | None = None,
    store: InMemoryInspectionStore = Depends(get_session_store),
    report_service: ConsumerReportService = Depends(get_consumer_report_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit an authority report package for an inspection owned by the caller."""
    session = store.get_session(inspection_id)
    _verify_inspection_ownership(session, current_user, inspection_id)

    description = request.consumer_description if request else None
    preferred_language = request.preferred_language if request else "en"

    # Eligibility validation
    is_eligible, reason, eligibility = report_service.check_eligibility(session)
    if not is_eligible or eligibility != ConsumerReportEligibility.ELIGIBLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_INSPECTION_STATE.value,
                "message": reason,
                "details": {
                    "inspection_id": inspection_id,
                    "eligibility": eligibility.value,
                },
            },
        )

    report = report_service.create_consumer_report(
        inspection_id=inspection_id,
        user=current_user,
        consumer_description=description,
        lang=preferred_language,
    )
    return report.to_dict(lang=preferred_language)


# =====================================================================
# Phase U24-C Offline Sync Endpoints
# =====================================================================

MAX_SYNC_OPERATIONS_PER_BATCH = 100
MAX_SYNC_DEPENDENCIES_PER_OP = 50


@router.post(
    "/sync/batch",
    response_model=SyncBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Synchronization Ingestion",
    description="Idempotently ingest a batch of ordered offline sync operations with dependency resolution.",
)
def sync_batch(
    request: SyncBatchRequest,
    sync_service: SyncIngestionService = Depends(get_sync_ingestion_service),
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SyncBatchResponse:
    """Ingest a batch of offline sync operations for an inspection owned by the authenticated caller."""
    if not request.operations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.INVALID_REQUEST.value,
                "message": "Sync batch must contain at least one operation.",
                "details": {"inspection_id": request.inspection_id},
            },
        )

    if len(request.operations) > MAX_SYNC_OPERATIONS_PER_BATCH:
        raise HTTPException(
            status_code=413,
            detail={
                "code": ErrorCode.SYNC_BATCH_TOO_LARGE.value,
                "message": f"Sync batch exceeds maximum limit of {MAX_SYNC_OPERATIONS_PER_BATCH} operations.",
                "details": {
                    "inspection_id": request.inspection_id,
                    "operation_count": len(request.operations),
                    "max_limit": MAX_SYNC_OPERATIONS_PER_BATCH,
                },
            },
        )

    # Check inspection ownership if inspection exists in session store
    session = store.get_session_optional(request.inspection_id)
    if session is not None and session.inspection.owner_id and session.inspection.owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{request.inspection_id}' not found.",
                "details": {"inspection_id": request.inspection_id},
            },
        )

    domain_ops: list[SyncOperation] = []
    for op_req in request.operations:
        if len(op_req.dependency_ids) > MAX_SYNC_DEPENDENCIES_PER_OP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": ErrorCode.INVALID_REQUEST.value,
                    "message": f"Operation '{op_req.operation_id}' exceeds maximum dependency limit of {MAX_SYNC_DEPENDENCIES_PER_OP}.",
                    "details": {"operation_id": op_req.operation_id},
                },
            )

        domain_ops.append(
            SyncOperation(
                operation_id=op_req.operation_id,
                inspection_id=op_req.inspection_id,
                entity_type=op_req.entity_type,
                entity_id=op_req.entity_id,
                operation_type=op_req.operation_type,
                content_hash=op_req.content_hash,
                created_at=op_req.created_at,
                sequence=op_req.sequence,
                dependency_ids=op_req.dependency_ids,
                payload=op_req.payload,
            )
        )

    acks = sync_service.ingest_batch(domain_ops, authenticated_user_id=current_user.user_id)

    # Synchronize in-memory session store container if root inspection was acknowledged
    if session is None:
        for op in domain_ops:
            if op.entity_type == "INSPECTION" or op.entity_type == SyncOperation:
                meta = dict(op.payload.get("metadata", {}))
                meta["owner_id"] = current_user.user_id
                store.create_session(
                    inspection_id=request.inspection_id,
                    metadata=meta,
                    owner_id=current_user.user_id,
                )
                break

    results = [
        SyncAcknowledgementResponse(
            operation_id=ack.operation_id,
            entity_id=ack.entity_id,
            status=ack.status.value if hasattr(ack.status, "value") else str(ack.status),
            server_timestamp=ack.server_timestamp,
            server_version=ack.server_version,
            error_code=ack.error_code,
            error_message=ack.error_message,
        )
        for ack in acks
    ]

    return SyncBatchResponse(
        inspection_id=request.inspection_id,
        batch_id=request.batch_id,
        results=results,
    )


@router.get(
    "/{inspection_id}/sync-status",
    response_model=SyncManifestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Inspection Synchronization Status",
    description="Retrieve the authoritative synchronization manifest and acknowledgement receipt state.",
)
def get_inspection_sync_status(
    inspection_id: str,
    sync_service: SyncIngestionService = Depends(get_sync_ingestion_service),
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SyncManifestResponse:
    """Return synchronization manifest for an inspection owned by the caller."""
    # Check ownership in session store if present
    session = store.get_session_optional(inspection_id)
    if session is not None and session.inspection.owner_id and session.inspection.owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )

    try:
        manifest = sync_service.get_sync_manifest(inspection_id, authenticated_user_id=current_user.user_id)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )

    if session is None and not manifest.entity_acknowledgements and manifest.sync_status == SyncStatus.DRAFT_LOCAL:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )

    acks = [
        SyncAcknowledgementResponse(
            operation_id=a.operation_id,
            entity_id=a.entity_id,
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
            server_timestamp=a.server_timestamp,
            server_version=a.server_version,
            error_code=a.error_code,
            error_message=a.error_message,
        )
        for a in manifest.entity_acknowledgements
    ]

    return SyncManifestResponse(
        inspection_id=manifest.inspection_id,
        lifecycle_status=manifest.lifecycle_status,
        sync_status=manifest.sync_status.value,
        entity_acknowledgements=acks,
        image_hashes=manifest.image_hashes,
        legal_snapshot_id=manifest.legal_snapshot_id,
        evaluation_metadata=manifest.evaluation_metadata.to_dict() if manifest.evaluation_metadata else None,
        last_synced_at=manifest.last_synced_at,
    )


@router.post(
    "/{inspection_id}/revalidate",
    response_model=ServerRevalidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revalidate Offline Inspection on Server",
    description="Execute authoritative server-side compliance revalidation of an offline inspection against the active approved legal snapshot.",
)
def revalidate_offline_inspection(
    inspection_id: str,
    revalidation_service: ServerRevalidationService = Depends(get_server_revalidation_service),
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ServerRevalidationResponse:
    """Execute authoritative server-side compliance revalidation of an offline inspection."""
    # Check ownership in session store if present
    session = store.get_session_optional(inspection_id)
    if session is not None and session.inspection.owner_id and session.inspection.owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )

    try:
        result = revalidation_service.revalidate(
            inspection_id=inspection_id,
            authenticated_user_id=current_user.user_id,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )
    except InspectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{inspection_id}' not found.",
                "details": {"inspection_id": inspection_id},
            },
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": str(exc),
                "details": {"inspection_id": inspection_id},
            },
        )

    return ServerRevalidationResponse(
        inspection_id=result.inspection_id,
        overall_status=result.overall_status.value,
        verification_results=result.verification_results,
        summary=result.summary,
        counts=result.counts,
        applicable_requirements=result.applicable_requirements,
        server_legal_snapshot_id=result.server_legal_snapshot_id,
        offline_legal_snapshot_id=result.offline_legal_snapshot_id,
        evaluation_metadata=result.evaluation_metadata.to_dict(),
        comparison=result.comparison.to_dict(),
        evidence_annotations=result.evidence_annotations,
        revalidated_at=result.revalidated_at,
        content_hash=result.content_hash,
    )


# =====================================================================
# Phase U25: Evidence Chain of Custody & Trust Endpoints
# =====================================================================

@router.get(
    "/{inspection_id}/evidence",
    response_model=InspectionEvidenceSummaryResponse,
    summary="Get Inspection Evidence Records and Integrity Summary",
    description="Retrieve canonical cryptographic evidence records and integrity verification status for an inspection.",
)
def get_inspection_evidence(
    inspection_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    inspection_repo: InspectionRepository = Depends(get_inspection_repository),
    evidence_service: Any = Depends(get_evidence_chain_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> InspectionEvidenceSummaryResponse:
    """List canonical evidence records and chain verification status for an inspection."""
    _verify_inspection_access(inspection_id, current_user, store, inspection_repo)
    summary = evidence_service.get_inspection_evidence_summary(inspection_id=inspection_id)
    return InspectionEvidenceSummaryResponse(
        inspection_id=summary["inspection_id"],
        evidence_count=summary["evidence_count"],
        verified_evidence_count=summary["verified_evidence_count"],
        unverified_evidence_count=summary["unverified_evidence_count"],
        integrity_warning_count=summary["integrity_warning_count"],
        chain_verification_status=summary["chain_verification_status"],
        items=[
            EvidenceRecordResponse(
                evidence_id=r.evidence_id,
                inspection_id=r.inspection_id,
                image_id=r.image_id,
                source_id=r.source_id,
                content_hash=r.content_hash,
                hash_algorithm=r.hash_algorithm,
                byte_size=r.byte_size,
                media_type=r.media_type,
                original_filename=r.original_filename,
                storage_reference=r.storage_reference,
                captured_at=r.captured_at,
                received_at=r.received_at,
                created_at=r.created_at,
                submitted_by=r.submitted_by,
                source_type=r.source_type,
                integrity_status=r.integrity_status.value if hasattr(r.integrity_status, "value") else str(r.integrity_status),
                metadata=r.metadata,
            )
            for r in summary["items"]
        ],
    )


@router.get(
    "/{inspection_id}/evidence/{evidence_id}",
    response_model=EvidenceRecordResponse,
    summary="Get Canonical Evidence Record",
    description="Retrieve a single canonical evidence record by ID with cryptographic hash identity.",
)
def get_evidence_record(
    inspection_id: str,
    evidence_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    inspection_repo: InspectionRepository = Depends(get_inspection_repository),
    evidence_service: Any = Depends(get_evidence_chain_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EvidenceRecordResponse:
    """Retrieve canonical evidence record ensuring inspection ownership and scope isolation."""
    _verify_inspection_access(inspection_id, current_user, store, inspection_repo)
    record = evidence_service.get_evidence_record(evidence_id=evidence_id)
    if record is None or record.inspection_id != inspection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Evidence record '{evidence_id}' not found for inspection '{inspection_id}'.",
                "details": {"inspection_id": inspection_id, "evidence_id": evidence_id},
            },
        )
    return EvidenceRecordResponse(
        evidence_id=record.evidence_id,
        inspection_id=record.inspection_id,
        image_id=record.image_id,
        source_id=record.source_id,
        content_hash=record.content_hash,
        hash_algorithm=record.hash_algorithm,
        byte_size=record.byte_size,
        media_type=record.media_type,
        original_filename=record.original_filename,
        storage_reference=record.storage_reference,
        captured_at=record.captured_at,
        received_at=record.received_at,
        created_at=record.created_at,
        submitted_by=record.submitted_by,
        source_type=record.source_type,
        integrity_status=record.integrity_status.value if hasattr(record.integrity_status, "value") else str(record.integrity_status),
        metadata=record.metadata,
    )


@router.get(
    "/{inspection_id}/evidence/{evidence_id}/chain",
    response_model=list[EvidenceChainEventResponse],
    summary="Get Evidence Provenance Chain",
    description="Retrieve the complete append-oriented cryptographic provenance event chain for an evidence record.",
)
def get_evidence_chain(
    inspection_id: str,
    evidence_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    inspection_repo: InspectionRepository = Depends(get_inspection_repository),
    evidence_service: Any = Depends(get_evidence_chain_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[EvidenceChainEventResponse]:
    """Retrieve tamper-evident provenance event chain for an evidence item."""
    _verify_inspection_access(inspection_id, current_user, store, inspection_repo)
    record = evidence_service.get_evidence_record(evidence_id=evidence_id)
    if record is None or record.inspection_id != inspection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Evidence record '{evidence_id}' not found for inspection '{inspection_id}'.",
                "details": {"inspection_id": inspection_id, "evidence_id": evidence_id},
            },
        )
    events = evidence_service.get_evidence_chain(evidence_id=evidence_id)
    return [
        EvidenceChainEventResponse(
            event_id=e.event_id,
            evidence_id=e.evidence_id,
            inspection_id=e.inspection_id,
            event_type=e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
            actor_type=e.actor_type,
            actor_id=e.actor_id,
            timestamp=e.timestamp,
            previous_event_hash=e.previous_event_hash,
            event_hash=e.event_hash,
            metadata=e.metadata,
            operation_id=e.operation_id,
        )
        for e in events
    ]


@router.get(
    "/{inspection_id}/evidence/{evidence_id}/integrity",
    response_model=EvidenceIntegrityResponse,
    summary="Verify Evidence Integrity and Chain",
    description="Perform cryptographic verification of content hash and event chain sequence.",
)
def verify_evidence_integrity(
    inspection_id: str,
    evidence_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    inspection_repo: InspectionRepository = Depends(get_inspection_repository),
    evidence_service: Any = Depends(get_evidence_chain_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EvidenceIntegrityResponse:
    """Perform on-demand cryptographic verification of evidence record and event chain."""
    _verify_inspection_access(inspection_id, current_user, store, inspection_repo)
    record = evidence_service.get_evidence_record(evidence_id=evidence_id)
    if record is None or record.inspection_id != inspection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Evidence record '{evidence_id}' not found for inspection '{inspection_id}'.",
                "details": {"inspection_id": inspection_id, "evidence_id": evidence_id},
            },
        )
    result = evidence_service.verify_evidence_integrity(evidence_id=evidence_id)
    return EvidenceIntegrityResponse(
        evidence_id=result.evidence_id,
        inspection_id=result.inspection_id,
        integrity_status=result.integrity_status.value if hasattr(result.integrity_status, "value") else str(result.integrity_status),
        content_hash=result.content_hash,
        content_hash_valid=result.content_hash_valid,
        chain_valid=result.chain_valid,
        event_count=result.event_count,
        first_event_at=result.first_event_at,
        last_event_at=result.last_event_at,
        broken_event_id=result.broken_event_id,
        error_codes=result.error_codes,
        verified_at=result.verified_at,
        details=result.details,
    )



