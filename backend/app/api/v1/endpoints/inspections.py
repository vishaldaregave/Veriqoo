"""FastAPI router for Multi-Image Inspections and Verification Execution."""

from datetime import datetime, timezone
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status

from backend.app.api.dependencies import (
    get_ingestion_service,
    get_pipeline_orchestrator,
    get_session_store,
)
from backend.app.api.errors import ErrorCode, create_error_response
from backend.app.api.schemas import (
    CreateInspectionRequest,
    ImageUploadResponse,
    InspectionImageResponse,
    InspectionListResponse,
    InspectionReportResponse,
    InspectionResponse,
    RunInspectionRequest,
    RunInspectionResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.applicability.models import InspectionFact
from backend.app.services.evidence.errors import InvalidImageError
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.inspection.errors import InvalidInspectionError
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.errors import (
    InvalidPipelineInputError,
    PipelineError,
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
    description="Retrieve the latest inspection verification report.",
)
def get_report(
    inspection_id: str,
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

    return report.to_dict()
