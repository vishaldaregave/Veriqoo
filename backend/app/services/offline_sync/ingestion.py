"""Server-side Sync Ingestion Engine for Phase U24-B.

Coordinates:
1. Idempotency and duplicate replay detection
2. Content hash integrity checking
3. Dependency graph resolution
4. Strict server-side ownership and authorization
5. Safe transaction boundaries and acknowledgement generation
6. Authoritative SyncManifest generation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection.repository import InspectionRepository
from backend.app.services.offline_sync.models import (
    DurableSyncOperationRecord,
    EvaluationMetadata,
    EvaluationMode,
    OperationStatus,
    SyncAckStatus,
    SyncAcknowledgement,
    SyncEntityType,
    SyncErrorCode,
    SyncManifest,
    SyncOperation,
    SyncStatus,
)
from backend.app.services.offline_sync.repository import (
    DuplicateOperationIdError,
    SyncOperationRepository,
)
from backend.app.services.offline_sync.validator import SyncEntityValidator


class SyncIngestionService:
    """Processes, validates, and synchronizes offline inspection operations."""

    def __init__(
        self,
        sync_repository: SyncOperationRepository,
        inspection_repository: InspectionRepository | None = None,
        server_version: str = "1.0.0",
    ) -> None:
        self.sync_repo = sync_repository
        self.inspection_repo = inspection_repository
        self.server_version = str(server_version)

    def ingest_operation(
        self,
        operation: SyncOperation,
        authenticated_user_id: str,
    ) -> SyncAcknowledgement:
        """Process a single sync operation with strict idempotency, integrity, and authorization."""
        auth_user = str(authenticated_user_id).strip()
        now_utc = datetime.now(timezone.utc).isoformat()

        # -------------------------------------------------------------
        # 1. Idempotency Check: Existing Operation Lookup
        # -------------------------------------------------------------
        existing_op = self.sync_repo.get_operation(operation.operation_id)
        if existing_op is not None:
            # Check for payload content hash match
            if existing_op.content_hash == operation.content_hash:
                # Identical replay: return existing status or ALREADY_APPLIED
                if existing_op.status in (OperationStatus.ACKNOWLEDGED, OperationStatus.ALREADY_APPLIED):
                    return SyncAcknowledgement(
                        operation_id=operation.operation_id,
                        entity_id=operation.entity_id,
                        status=SyncAckStatus.ALREADY_APPLIED,
                        server_timestamp=now_utc,
                        server_version=self.server_version,
                    )
                elif existing_op.status == OperationStatus.REJECTED:
                    return SyncAcknowledgement(
                        operation_id=operation.operation_id,
                        entity_id=operation.entity_id,
                        status=SyncAckStatus.REJECTED,
                        server_timestamp=now_utc,
                        server_version=self.server_version,
                        error_code=existing_op.error_code,
                        error_message=existing_op.error_message,
                    )
                elif existing_op.status == OperationStatus.RETRYABLE_FAILURE:
                    # Retry processing of a previously pending/retryable operation
                    pass
            else:
                # Conflicting replay under identical operation_id
                return SyncAcknowledgement(
                    operation_id=operation.operation_id,
                    entity_id=operation.entity_id,
                    status=SyncAckStatus.REJECTED,
                    server_timestamp=now_utc,
                    server_version=self.server_version,
                    error_code=SyncErrorCode.SYNC_DUPLICATE_PAYLOAD_MISMATCH.value,
                    error_message=f"Operation '{operation.operation_id}' already exists with a different content hash.",
                )

        # -------------------------------------------------------------
        # 2. Content Hash Verification
        # -------------------------------------------------------------
        is_hash_valid, computed_hash = SyncEntityValidator.verify_content_hash(
            operation.payload,
            operation.content_hash,
        )
        if not is_hash_valid:
            return self._record_and_acknowledge(
                operation=operation,
                status=OperationStatus.REJECTED,
                ack_status=SyncAckStatus.REJECTED,
                error_code=SyncErrorCode.SYNC_CONTENT_HASH_MISMATCH.value,
                error_message=f"Payload SHA-256 hash mismatch (expected {operation.content_hash}, calculated {computed_hash}).",
                existing_record=existing_op,
            )

        # -------------------------------------------------------------
        # 3. Structural Entity Validation
        # -------------------------------------------------------------
        is_struct_valid, struct_err_code, struct_err_msg = SyncEntityValidator.validate_entity_structure(operation)
        if not is_struct_valid:
            return self._record_and_acknowledge(
                operation=operation,
                status=OperationStatus.REJECTED,
                ack_status=SyncAckStatus.REJECTED,
                error_code=struct_err_code or SyncErrorCode.SYNC_INVALID_ENTITY.value,
                error_message=struct_err_msg or "Invalid entity structure.",
                existing_record=existing_op,
            )

        # -------------------------------------------------------------
        # 4. Dependency Graph Check
        # -------------------------------------------------------------
        if operation.dependency_ids:
            can_proceed, dep_err_code, dep_err_msg = SyncEntityValidator.check_dependencies(
                operation.dependency_ids,
                self.sync_repo,
                current_inspection_id=operation.inspection_id,
            )
            if not can_proceed:
                if dep_err_code in (
                    SyncErrorCode.SYNC_DEPENDENCY_REJECTED.value,
                    SyncErrorCode.SYNC_CROSS_INSPECTION_DEPENDENCY.value,
                ):
                    return self._record_and_acknowledge(
                        operation=operation,
                        status=OperationStatus.REJECTED,
                        ack_status=SyncAckStatus.REJECTED,
                        error_code=dep_err_code,
                        error_message=dep_err_msg or "Dependency permanently rejected.",
                        existing_record=existing_op,
                    )
                else:
                    return self._record_and_acknowledge(
                        operation=operation,
                        status=OperationStatus.RETRYABLE_FAILURE,
                        ack_status=SyncAckStatus.RETRYABLE_FAILURE,
                        error_code=dep_err_code or SyncErrorCode.SYNC_DEPENDENCY_PENDING.value,
                        error_message=dep_err_msg or "Dependency pending.",
                        existing_record=existing_op,
                    )

        # -------------------------------------------------------------
        # 5. Server-Side Ownership & Inspection Context Authorization
        # -------------------------------------------------------------
        if self.inspection_repo is not None:
            try:
                inspection = self.inspection_repo.get_inspection(operation.inspection_id)
                # Inspection exists: verify ownership
                owner_id = getattr(inspection, "owner_id", None) or (inspection.metadata.get("owner_id") if isinstance(inspection.metadata, dict) else None)
                if owner_id and str(owner_id).strip() != auth_user:
                    # Cross-user unauthorized access
                    return self._record_and_acknowledge(
                        operation=operation,
                        status=OperationStatus.REJECTED,
                        ack_status=SyncAckStatus.REJECTED,
                        error_code=SyncErrorCode.SYNC_NOT_OWNER.value,
                        error_message="User is not authorized to synchronize this inspection.",
                        existing_record=existing_op,
                    )
            except Exception:
                # Inspection does not exist in repository
                if operation.entity_type != SyncEntityType.INSPECTION:
                    return self._record_and_acknowledge(
                        operation=operation,
                        status=OperationStatus.RETRYABLE_FAILURE,
                        ack_status=SyncAckStatus.RETRYABLE_FAILURE,
                        error_code=SyncErrorCode.SYNC_INSPECTION_NOT_FOUND.value,
                        error_message=f"Target inspection '{operation.inspection_id}' does not exist on server.",
                        existing_record=existing_op,
                    )

        # -------------------------------------------------------------
        # 6. Apply Side Effects & Persist ACKNOWLEDGED
        # -------------------------------------------------------------
        if self.inspection_repo is not None and operation.entity_type == SyncEntityType.INSPECTION:
            try:
                self.inspection_repo.get_inspection(operation.inspection_id)
            except Exception:
                # Create root inspection container owned by authenticated user
                meta = operation.payload.get("metadata") or {}
                if isinstance(meta, dict):
                    meta = dict(meta)
                else:
                    meta = {}
                meta["owner_id"] = auth_user
                try:
                    self.inspection_repo.create_inspection(
                        inspection_id=operation.inspection_id,
                        metadata=meta,
                        owner_id=auth_user,
                    )
                except Exception as ex:
                    return self._record_and_acknowledge(
                        operation=operation,
                        status=OperationStatus.RETRYABLE_FAILURE,
                        ack_status=SyncAckStatus.RETRYABLE_FAILURE,
                        error_code=SyncErrorCode.SYNC_DATABASE_ERROR.value,
                        error_message=f"Failed to create inspection record: {str(ex)}",
                        existing_record=existing_op,
                    )

        return self._record_and_acknowledge(
            operation=operation,
            status=OperationStatus.ACKNOWLEDGED,
            ack_status=SyncAckStatus.ACKNOWLEDGED,
            existing_record=existing_op,
        )

    def ingest_batch(
        self,
        operations: list[SyncOperation],
        authenticated_user_id: str,
    ) -> list[SyncAcknowledgement]:
        """Process an ordered batch of sync operations, checking for circular dependencies first."""
        # 1. Detect circular dependencies
        cycle = SyncEntityValidator.detect_circular_dependencies(operations)
        if cycle:
            cycle_set = set(cycle)
            acks = []
            for op in operations:
                if op.operation_id in cycle_set:
                    acks.append(
                        SyncAcknowledgement(
                            operation_id=op.operation_id,
                            entity_id=op.entity_id,
                            status=SyncAckStatus.REJECTED,
                            server_timestamp=datetime.now(timezone.utc).isoformat(),
                            server_version=self.server_version,
                            error_code=SyncErrorCode.SYNC_CIRCULAR_DEPENDENCY.value,
                            error_message=f"Circular dependency detected involving operations: {cycle}",
                        )
                    )
                else:
                    acks.append(self.ingest_operation(op, authenticated_user_id))
            return acks

        # 2. Sort by sequence and ingest
        sorted_ops = sorted(operations, key=lambda x: x.sequence)
        return [self.ingest_operation(op, authenticated_user_id) for op in sorted_ops]

    def get_sync_manifest(
        self,
        inspection_id: str,
        authenticated_user_id: str,
    ) -> SyncManifest:
        """Construct the authoritative SyncManifest for a given inspection."""
        auth_user = str(authenticated_user_id).strip()

        # Authorization lookup
        lifecycle_status = "COLLECTING"
        image_hashes: dict[str, str] = {}
        evaluation_meta = None
        legal_snapshot_id = None

        if self.inspection_repo is not None:
            try:
                inspection = self.inspection_repo.get_inspection(inspection_id)
                owner_id = getattr(inspection, "owner_id", None) or (
                    inspection.metadata.get("owner_id") if isinstance(inspection.metadata, dict) else None
                )
                if owner_id and str(owner_id).strip() != auth_user:
                    raise PermissionError("Unauthorized inspection access.")
                lifecycle_status = inspection.status.value if hasattr(inspection.status, "value") else str(inspection.status)
            except Exception as e:
                if isinstance(e, PermissionError):
                    raise

        # Query all sync operations for inspection
        ops = self.sync_repo.list_operations_for_inspection(inspection_id)

        acks: list[SyncAcknowledgement] = []
        has_pending = False
        has_rejected = False

        for op in ops:
            if op.status == OperationStatus.ACKNOWLEDGED:
                status_val = SyncAckStatus.ACKNOWLEDGED
            elif op.status == OperationStatus.ALREADY_APPLIED:
                status_val = SyncAckStatus.ALREADY_APPLIED
            elif op.status == OperationStatus.REJECTED:
                status_val = SyncAckStatus.REJECTED
                has_rejected = True
            else:
                status_val = SyncAckStatus.RETRYABLE_FAILURE
                has_pending = True

            acks.append(
                SyncAcknowledgement(
                    operation_id=op.operation_id,
                    entity_id=op.entity_id,
                    status=status_val,
                    server_timestamp=op.acknowledged_at or op.received_at,
                    server_version=self.server_version,
                    error_code=op.error_code,
                    error_message=op.error_message,
                )
            )

            if op.entity_type == SyncEntityType.IMAGE:
                img_hash = op.payload.get("normalized_hash") or op.payload.get("source_hash")
                if img_hash:
                    image_hashes[op.entity_id] = str(img_hash)

            if op.payload.get("legal_snapshot_id"):
                legal_snapshot_id = str(op.payload["legal_snapshot_id"])

            if op.payload.get("evaluation_metadata"):
                evaluation_meta = EvaluationMetadata.from_dict(op.payload["evaluation_metadata"])

        # Determine overall sync status
        if not ops:
            overall_sync_status = SyncStatus.DRAFT_LOCAL
        elif has_rejected:
            overall_sync_status = SyncStatus.SYNC_FAILED
        elif has_pending:
            overall_sync_status = SyncStatus.SYNC_PENDING
        else:
            if evaluation_meta and evaluation_meta.revalidation_required:
                overall_sync_status = SyncStatus.REVALIDATION_REQUIRED
            else:
                overall_sync_status = SyncStatus.SYNCED

        latest_time = max([op.received_at for op in ops]) if ops else None

        return SyncManifest(
            inspection_id=inspection_id,
            lifecycle_status=lifecycle_status,
            sync_status=overall_sync_status,
            entity_acknowledgements=acks,
            image_hashes=image_hashes,
            legal_snapshot_id=legal_snapshot_id,
            evaluation_metadata=evaluation_meta,
            last_synced_at=latest_time,
        )

    def _record_and_acknowledge(
        self,
        operation: SyncOperation,
        status: OperationStatus,
        ack_status: SyncAckStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        existing_record: DurableSyncOperationRecord | None = None,
    ) -> SyncAcknowledgement:
        """Helper to update/save record and generate typed receipt."""
        now_utc = datetime.now(timezone.utc).isoformat()
        ack_time = now_utc if status in (OperationStatus.ACKNOWLEDGED, OperationStatus.ALREADY_APPLIED) else None

        if existing_record is not None:
            self.sync_repo.update_operation_status(
                operation_id=operation.operation_id,
                status=status,
                acknowledged_at=ack_time,
                error_code=error_code,
                error_message=error_message,
                attempt_count=existing_record.attempt_count + 1,
            )
        else:
            rec = DurableSyncOperationRecord(
                operation_id=operation.operation_id,
                inspection_id=operation.inspection_id,
                entity_type=operation.entity_type,
                entity_id=operation.entity_id,
                operation_type=operation.operation_type,
                content_hash=operation.content_hash,
                created_at=operation.created_at,
                received_at=now_utc,
                acknowledged_at=ack_time,
                sequence=operation.sequence,
                dependency_ids=operation.dependency_ids,
                status=status,
                attempt_count=1,
                error_code=error_code,
                error_message=error_message,
                payload=operation.payload,
            )
            try:
                self.sync_repo.save_operation(rec)
            except DuplicateOperationIdError:
                # In concurrent scenarios
                self.sync_repo.update_operation_status(
                    operation_id=operation.operation_id,
                    status=status,
                    acknowledged_at=ack_time,
                    error_code=error_code,
                    error_message=error_message,
                )
            except Exception as ex:
                return SyncAcknowledgement(
                    operation_id=operation.operation_id,
                    entity_id=operation.entity_id,
                    status=SyncAckStatus.RETRYABLE_FAILURE,
                    server_timestamp=now_utc,
                    server_version=self.server_version,
                    error_code=SyncErrorCode.SYNC_DATABASE_ERROR.value,
                    error_message=f"Storage failure: {str(ex)}",
                )

        return SyncAcknowledgement(
            operation_id=operation.operation_id,
            entity_id=operation.entity_id,
            status=ack_status,
            server_timestamp=now_utc,
            server_version=self.server_version,
            error_code=error_code,
            error_message=error_message,
        )
