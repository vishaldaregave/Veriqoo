"""FastAPI router for Multi-Image Inspections and Verification Execution."""

from datetime import datetime, timezone
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, status

from backend.app.api.dependencies import (
    get_consumer_intelligence_service,
    get_consumer_report_service,
    get_consumer_result_service,
    get_ingestion_service,
    get_pipeline_orchestrator,
    get_report_sharing_service,
    get_session_store,
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
    ImageUploadResponse,
    InspectionImageResponse,
    InspectionReportResponse,
    InspectionResponse,
    QRPayloadResponse,
    RevokeShareResponse,
    RunInspectionRequest,
    RunInspectionResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.applicability.models import InspectionFact
from backend.app.services.consumer_intelligence import ConsumerIntelligenceService
from backend.app.services.consumer_report import (
    ConsumerReportEligibility,
    ConsumerReportService,
)
from backend.app.services.consumer_result import ConsumerResultService
from backend.app.services.evidence.errors import InvalidImageError
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.inspection.errors import InvalidInspectionError
from backend.app.services.inspection.models import InspectionStatus
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
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Get Inspection Session",
    description="Retrieve inspection session metadata and ordered image references.",
)
def get_inspection(
    inspection_id: str,
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> InspectionResponse:
    """Retrieve inspection session state if owned by caller."""
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
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve inspection report for completed run owned by caller."""
    # Ensure inspection session exists and verify ownership
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

