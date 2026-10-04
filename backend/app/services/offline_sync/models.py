"""Core domain contracts, models, and enums for Phase U24-A Offline Inspection & Sync.

Establishes formal typed boundaries for:
1. Evaluation metadata and offline evaluation modes
2. Legal snapshot manifest and validation contracts
3. Offline inspection metadata contracts (without trusting client authentication)
4. Sync operations, acknowledgements, conflicts, and manifests
5. Orthogonal sync status lifecycle (distinct from inspection processing lifecycle)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any


# =====================================================================
# 1. Evaluation Metadata Contract
# =====================================================================

class EvaluationMode(str, Enum):
    """Execution mode of the legal metrology evaluation."""

    ONLINE = "ONLINE"
    OFFLINE_DETERMINISTIC = "OFFLINE_DETERMINISTIC"
    SERVER_REVALIDATED = "SERVER_REVALIDATED"


class EvaluationMetadata:
    """Strongly typed metadata tracking how and when an inspection result was evaluated."""

    def __init__(
        self,
        evaluation_mode: EvaluationMode | str = EvaluationMode.ONLINE,
        revalidation_required: bool = False,
        evaluated_at: datetime | str | None = None,
        engine_version: str = "1.0.0",
        model_version: str | None = None,
        prompt_version: str | None = None,
        legal_snapshot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(evaluation_mode, str):
            try:
                self.evaluation_mode = EvaluationMode(evaluation_mode)
            except ValueError:
                self.evaluation_mode = EvaluationMode.ONLINE
        else:
            self.evaluation_mode = evaluation_mode

        self.revalidation_required = bool(revalidation_required)

        if evaluated_at is None:
            self.evaluated_at = datetime.now(timezone.utc)
        elif isinstance(evaluated_at, str):
            try:
                self.evaluated_at = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
            except Exception:
                self.evaluated_at = datetime.now(timezone.utc)
        else:
            self.evaluated_at = evaluated_at

        if self.evaluated_at.tzinfo is None:
            self.evaluated_at = self.evaluated_at.replace(tzinfo=timezone.utc)

        self.engine_version = str(engine_version)
        self.model_version = str(model_version) if model_version else None
        self.prompt_version = str(prompt_version) if prompt_version else None
        self.legal_snapshot_id = str(legal_snapshot_id) if legal_snapshot_id else None
        self.metadata = dict(metadata or {})

    def to_dict(self) -> dict[str, Any]:
        """Deterministic dictionary serialization."""
        return {
            "evaluation_mode": self.evaluation_mode.value,
            "revalidation_required": self.revalidation_required,
            "evaluated_at": self.evaluated_at.isoformat(),
            "engine_version": self.engine_version,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "legal_snapshot_id": self.legal_snapshot_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationMetadata:
        """Construct instance from dictionary payload."""
        return cls(
            evaluation_mode=data.get("evaluation_mode", EvaluationMode.ONLINE),
            revalidation_required=data.get("revalidation_required", False),
            evaluated_at=data.get("evaluated_at"),
            engine_version=data.get("engine_version", "1.0.0"),
            model_version=data.get("model_version"),
            prompt_version=data.get("prompt_version"),
            legal_snapshot_id=data.get("legal_snapshot_id"),
            metadata=data.get("metadata", {}),
        )


# =====================================================================
# 2. Legal Snapshot Identity & Manifest
# =====================================================================

class LegalSnapshotManifest:
    """Informational manifest describing the composition of a deterministic legal snapshot."""

    def __init__(
        self,
        legal_snapshot_id: str,
        document_count: int = 0,
        provision_count: int = 0,
        requirement_count: int = 0,
        schedule_count: int = 0,
        schedule_entry_count: int = 0,
        table_count: int = 0,
        amendment_count: int = 0,
        approved_applicability_rule_version_count: int = 0,
        approved_condition_group_count: int = 0,
        approved_condition_count: int = 0,
        serialization_version: str = "1.0.0",
        generated_at: str | None = None,
    ) -> None:
        self.legal_snapshot_id = str(legal_snapshot_id)
        self.document_count = int(document_count)
        self.provision_count = int(provision_count)
        self.requirement_count = int(requirement_count)
        self.schedule_count = int(schedule_count)
        self.schedule_entry_count = int(schedule_entry_count)
        self.table_count = int(table_count)
        self.amendment_count = int(amendment_count)
        self.approved_applicability_rule_version_count = int(approved_applicability_rule_version_count)
        self.approved_condition_group_count = int(approved_condition_group_count)
        self.approved_condition_count = int(approved_condition_count)
        self.serialization_version = str(serialization_version)
        self.generated_at = str(generated_at) if generated_at else datetime.now(timezone.utc).isoformat()

    @property
    def total_entity_count(self) -> int:
        """Total number of authoritative legal entities incorporated in the snapshot."""
        return (
            self.document_count
            + self.provision_count
            + self.requirement_count
            + self.schedule_count
            + self.schedule_entry_count
            + self.table_count
            + self.amendment_count
            + self.approved_applicability_rule_version_count
            + self.approved_condition_group_count
            + self.approved_condition_count
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot manifest."""
        return {
            "legal_snapshot_id": self.legal_snapshot_id,
            "document_count": self.document_count,
            "provision_count": self.provision_count,
            "requirement_count": self.requirement_count,
            "schedule_count": self.schedule_count,
            "schedule_entry_count": self.schedule_entry_count,
            "table_count": self.table_count,
            "amendment_count": self.amendment_count,
            "approved_applicability_rule_version_count": self.approved_applicability_rule_version_count,
            "approved_condition_group_count": self.approved_condition_group_count,
            "approved_condition_count": self.approved_condition_count,
            "total_entity_count": self.total_entity_count,
            "serialization_version": self.serialization_version,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LegalSnapshotManifest:
        """Reconstruct LegalSnapshotManifest from dictionary."""
        return cls(
            legal_snapshot_id=data.get("legal_snapshot_id", ""),
            document_count=data.get("document_count", 0),
            provision_count=data.get("provision_count", 0),
            requirement_count=data.get("requirement_count", 0),
            schedule_count=data.get("schedule_count", 0),
            schedule_entry_count=data.get("schedule_entry_count", 0),
            table_count=data.get("table_count", 0),
            amendment_count=data.get("amendment_count", 0),
            approved_applicability_rule_version_count=data.get("approved_applicability_rule_version_count", 0),
            approved_condition_group_count=data.get("approved_condition_group_count", 0),
            approved_condition_count=data.get("approved_condition_count", 0),
            serialization_version=data.get("serialization_version", "1.0.0"),
            generated_at=data.get("generated_at"),
        )


class LegalSnapshotValidationStatus(str, Enum):
    """Comparison status between client legal snapshot and current authoritative server snapshot."""

    MATCHED = "MATCHED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class LegalSnapshotValidationResult:
    """Outcome of validating a client-provided legal snapshot identity against server authority."""

    def __init__(
        self,
        status: LegalSnapshotValidationStatus | str,
        client_snapshot_id: str,
        server_snapshot_id: str | None = None,
        is_valid_for_evaluation: bool = False,
        requires_server_revalidation: bool = False,
        reason: str = "",
    ) -> None:
        if isinstance(status, str):
            try:
                self.status = LegalSnapshotValidationStatus(status)
            except ValueError:
                self.status = LegalSnapshotValidationStatus.UNKNOWN
        else:
            self.status = status

        self.client_snapshot_id = str(client_snapshot_id)
        self.server_snapshot_id = str(server_snapshot_id) if server_snapshot_id else None
        self.is_valid_for_evaluation = bool(is_valid_for_evaluation)
        self.requires_server_revalidation = bool(requires_server_revalidation)
        self.reason = str(reason)

    def to_dict(self) -> dict[str, Any]:
        """Serialize validation result."""
        return {
            "status": self.status.value,
            "client_snapshot_id": self.client_snapshot_id,
            "server_snapshot_id": self.server_snapshot_id,
            "is_valid_for_evaluation": self.is_valid_for_evaluation,
            "requires_server_revalidation": self.requires_server_revalidation,
            "reason": self.reason,
        }


# =====================================================================
# 3. Offline Inspection Metadata
# =====================================================================

class OfflineInspectionMetadata:
    """Inspection-level offline provenance and device telemetry metadata.
    
    SECURITY CONTRACT:
    Client-provided owner/user identifiers or role claims MUST NEVER be accepted in this model.
    Server ownership is strictly established via cryptographically verified Supabase JWTs.
    """

    def __init__(
        self,
        inspection_id: str,
        client_created_at: str,
        device_id: str,
        legal_snapshot_id: str,
        evaluation_mode: EvaluationMode | str = EvaluationMode.OFFLINE_DETERMINISTIC,
        revalidation_required: bool = True,
        client_engine_version: str = "1.0.0",
        metadata_schema_version: str = "1.0.0",
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        self.inspection_id = str(inspection_id)
        self.client_created_at = str(client_created_at)
        self.device_id = str(device_id)
        self.legal_snapshot_id = str(legal_snapshot_id)

        if isinstance(evaluation_mode, str):
            try:
                self.evaluation_mode = EvaluationMode(evaluation_mode)
            except ValueError:
                self.evaluation_mode = EvaluationMode.OFFLINE_DETERMINISTIC
        else:
            self.evaluation_mode = evaluation_mode

        self.revalidation_required = bool(revalidation_required)
        self.client_engine_version = str(client_engine_version)
        self.metadata_schema_version = str(metadata_schema_version)
        self.extra_context = dict(extra_context or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize offline inspection metadata."""
        return {
            "inspection_id": self.inspection_id,
            "client_created_at": self.client_created_at,
            "device_id": self.device_id,
            "legal_snapshot_id": self.legal_snapshot_id,
            "evaluation_mode": self.evaluation_mode.value,
            "revalidation_required": self.revalidation_required,
            "client_engine_version": self.client_engine_version,
            "metadata_schema_version": self.metadata_schema_version,
            "extra_context": dict(self.extra_context),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OfflineInspectionMetadata:
        """Construct instance from dictionary payload."""
        return cls(
            inspection_id=data.get("inspection_id", ""),
            client_created_at=data.get("client_created_at", ""),
            device_id=data.get("device_id", ""),
            legal_snapshot_id=data.get("legal_snapshot_id", ""),
            evaluation_mode=data.get("evaluation_mode", EvaluationMode.OFFLINE_DETERMINISTIC),
            revalidation_required=data.get("revalidation_required", True),
            client_engine_version=data.get("client_engine_version", "1.0.0"),
            metadata_schema_version=data.get("metadata_schema_version", "1.0.0"),
            extra_context=data.get("extra_context", {}),
        )


# =====================================================================
# 4. Sync Operation & Lifecycle Contracts
# =====================================================================

class SyncEntityType(str, Enum):
    """Categorical types of inspection domain entities in the sync pipeline."""

    INSPECTION = "INSPECTION"
    IMAGE = "IMAGE"
    OCR_OBSERVATION = "OCR_OBSERVATION"
    EVIDENCE = "EVIDENCE"
    FACT = "FACT"
    APPLICABILITY = "APPLICABILITY"
    REQUIREMENT_RESULT = "REQUIREMENT_RESULT"
    REPORT = "REPORT"


class OperationStatus(str, Enum):
    """Lifecycle states for individual sync operations."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    REJECTED = "REJECTED"


class SyncErrorCode(str, Enum):
    """Stable, machine-readable sync error codes."""

    SYNC_DUPLICATE = "SYNC_DUPLICATE"
    SYNC_DUPLICATE_PAYLOAD_MISMATCH = "SYNC_DUPLICATE_PAYLOAD_MISMATCH"
    SYNC_CONTENT_HASH_MISMATCH = "SYNC_CONTENT_HASH_MISMATCH"
    SYNC_DEPENDENCY_PENDING = "SYNC_DEPENDENCY_PENDING"
    SYNC_DEPENDENCY_REJECTED = "SYNC_DEPENDENCY_REJECTED"
    SYNC_CROSS_INSPECTION_DEPENDENCY = "SYNC_CROSS_INSPECTION_DEPENDENCY"
    SYNC_INVALID_DEPENDENCY = "SYNC_INVALID_DEPENDENCY"
    SYNC_CIRCULAR_DEPENDENCY = "SYNC_CIRCULAR_DEPENDENCY"
    SYNC_INSPECTION_NOT_FOUND = "SYNC_INSPECTION_NOT_FOUND"
    SYNC_NOT_OWNER = "SYNC_NOT_OWNER"
    SYNC_INVALID_ENTITY = "SYNC_INVALID_ENTITY"
    SYNC_INVALID_STATE = "SYNC_INVALID_STATE"
    SYNC_DATABASE_ERROR = "SYNC_DATABASE_ERROR"
    SYNC_VALIDATION_ERROR = "SYNC_VALIDATION_ERROR"


class SyncOperationType(str, Enum):
    """Allowed idempotent mutation verbs in synchronization operations."""

    CREATE = "CREATE"
    UPSERT = "UPSERT"


class DurableSyncOperationRecord:
    """Server-side durable representation of a synchronization operation."""

    def __init__(
        self,
        operation_id: str,
        inspection_id: str,
        entity_type: SyncEntityType | str,
        entity_id: str,
        operation_type: SyncOperationType | str,
        content_hash: str,
        created_at: str,
        received_at: str | None = None,
        acknowledged_at: str | None = None,
        sequence: int = 1,
        dependency_ids: list[str] | None = None,
        status: OperationStatus | str = OperationStatus.PENDING,
        attempt_count: int = 0,
        error_code: str | None = None,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.operation_id = str(operation_id)
        self.inspection_id = str(inspection_id)

        if isinstance(entity_type, str):
            self.entity_type = SyncEntityType(entity_type)
        else:
            self.entity_type = entity_type

        self.entity_id = str(entity_id)

        if isinstance(operation_type, str):
            self.operation_type = SyncOperationType(operation_type)
        else:
            self.operation_type = operation_type

        self.content_hash = str(content_hash)
        self.created_at = str(created_at)
        self.received_at = str(received_at) if received_at else datetime.now(timezone.utc).isoformat()
        self.acknowledged_at = str(acknowledged_at) if acknowledged_at else None
        self.sequence = int(sequence)
        self.dependency_ids = [str(d) for d in (dependency_ids or [])]

        if isinstance(status, str):
            self.status = OperationStatus(status)
        else:
            self.status = status

        self.attempt_count = int(attempt_count)
        self.error_code = str(error_code) if error_code else None
        self.error_message = str(error_message) if error_message else None
        self.payload = dict(payload or {})
        self.metadata = dict(metadata or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize durable record."""
        return {
            "operation_id": self.operation_id,
            "inspection_id": self.inspection_id,
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "operation_type": self.operation_type.value,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "received_at": self.received_at,
            "acknowledged_at": self.acknowledged_at,
            "sequence": self.sequence,
            "dependency_ids": list(self.dependency_ids),
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DurableSyncOperationRecord:
        """Construct instance from dictionary."""
        return cls(
            operation_id=data.get("operation_id", ""),
            inspection_id=data.get("inspection_id", ""),
            entity_type=data.get("entity_type", SyncEntityType.INSPECTION),
            entity_id=data.get("entity_id", ""),
            operation_type=data.get("operation_type", SyncOperationType.CREATE),
            content_hash=data.get("content_hash", ""),
            created_at=data.get("created_at", ""),
            received_at=data.get("received_at"),
            acknowledged_at=data.get("acknowledged_at"),
            sequence=data.get("sequence", 1),
            dependency_ids=data.get("dependency_ids", []),
            status=data.get("status", OperationStatus.PENDING),
            attempt_count=data.get("attempt_count", 0),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )


class SyncOperation:
    """Strongly typed, atomic synchronization operation record representing a pending mutation."""

    def __init__(
        self,
        operation_id: str,
        inspection_id: str,
        entity_type: SyncEntityType | str,
        entity_id: str,
        operation_type: SyncOperationType | str,
        content_hash: str,
        created_at: str,
        sequence: int = 1,
        dependency_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.operation_id = str(operation_id)
        self.inspection_id = str(inspection_id)

        if isinstance(entity_type, str):
            self.entity_type = SyncEntityType(entity_type)
        else:
            self.entity_type = entity_type

        self.entity_id = str(entity_id)

        if isinstance(operation_type, str):
            self.operation_type = SyncOperationType(operation_type)
        else:
            self.operation_type = operation_type

        self.content_hash = str(content_hash)
        self.created_at = str(created_at)
        self.sequence = int(sequence)
        self.dependency_ids = [str(d) for d in (dependency_ids or [])]
        self.payload = dict(payload or {})

    def to_dict(self) -> dict[str, Any]:
        """Deterministic serialization."""
        return {
            "operation_id": self.operation_id,
            "inspection_id": self.inspection_id,
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "operation_type": self.operation_type.value,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "sequence": self.sequence,
            "dependency_ids": list(self.dependency_ids),
            "payload": dict(self.payload),
        }

    @staticmethod
    def compute_content_hash(payload: Any) -> str:
        """Deterministic SHA-256 computation over payload content."""
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncOperation:
        """Construct instance from dictionary."""
        return cls(
            operation_id=data.get("operation_id", ""),
            inspection_id=data.get("inspection_id", ""),
            entity_type=data.get("entity_type", SyncEntityType.INSPECTION),
            entity_id=data.get("entity_id", ""),
            operation_type=data.get("operation_type", SyncOperationType.CREATE),
            content_hash=data.get("content_hash", ""),
            created_at=data.get("created_at", ""),
            sequence=data.get("sequence", 1),
            dependency_ids=data.get("dependency_ids", []),
            payload=data.get("payload", {}),
        )


# =====================================================================
# 5. Sync Acknowledgement Contract
# =====================================================================

class SyncAckStatus(str, Enum):
    """Server acknowledgement status returned for a sync operation."""

    ACKNOWLEDGED = "ACKNOWLEDGED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    REJECTED = "REJECTED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"


class SyncAcknowledgement:
    """Strongly typed server receipt confirming or rejecting synchronization of an entity."""

    def __init__(
        self,
        operation_id: str,
        entity_id: str,
        status: SyncAckStatus | str,
        server_timestamp: str | None = None,
        server_version: str | None = "1.0.0",
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.operation_id = str(operation_id)
        self.entity_id = str(entity_id)

        if isinstance(status, str):
            self.status = SyncAckStatus(status)
        else:
            self.status = status

        self.server_timestamp = str(server_timestamp) if server_timestamp else datetime.now(timezone.utc).isoformat()
        self.server_version = str(server_version) if server_version else "1.0.0"
        self.error_code = str(error_code) if error_code else None
        self.error_message = str(error_message) if error_message else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize acknowledgement."""
        return {
            "operation_id": self.operation_id,
            "entity_id": self.entity_id,
            "status": self.status.value,
            "server_timestamp": self.server_timestamp,
            "server_version": self.server_version,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncAcknowledgement:
        """Construct instance from dictionary."""
        return cls(
            operation_id=data.get("operation_id", ""),
            entity_id=data.get("entity_id", ""),
            status=data.get("status", SyncAckStatus.ACKNOWLEDGED),
            server_timestamp=data.get("server_timestamp"),
            server_version=data.get("server_version", "1.0.0"),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
        )


# =====================================================================
# 6. Sync Conflict Contract
# =====================================================================

class SyncConflictClassification(str, Enum):
    """Categorization of a synchronization conflict."""

    SAFE_TO_REPLAY = "SAFE_TO_REPLAY"
    MUST_REJECT = "MUST_REJECT"
    MUST_REVALIDATE = "MUST_REVALIDATE"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class SyncConflict:
    """Structured record of a detected discrepancy between offline client state and authoritative server state."""

    def __init__(
        self,
        conflict_id: str,
        inspection_id: str,
        entity_type: SyncEntityType | str,
        entity_id: str,
        classification: SyncConflictClassification | str,
        code: str,
        message: str,
        server_state_reference: dict[str, Any] | None = None,
        client_state_reference: dict[str, Any] | None = None,
        detected_at: str | None = None,
    ) -> None:
        self.conflict_id = str(conflict_id)
        self.inspection_id = str(inspection_id)

        if isinstance(entity_type, str):
            self.entity_type = SyncEntityType(entity_type)
        else:
            self.entity_type = entity_type

        self.entity_id = str(entity_id)

        if isinstance(classification, str):
            self.classification = SyncConflictClassification(classification)
        else:
            self.classification = classification

        self.code = str(code)
        self.message = str(message)
        self.server_state_reference = dict(server_state_reference or {})
        self.client_state_reference = dict(client_state_reference or {})
        self.detected_at = str(detected_at) if detected_at else datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize conflict model."""
        return {
            "conflict_id": self.conflict_id,
            "inspection_id": self.inspection_id,
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "classification": self.classification.value,
            "code": self.code,
            "message": self.message,
            "server_state_reference": dict(self.server_state_reference),
            "client_state_reference": dict(self.client_state_reference),
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncConflict:
        """Construct instance from dictionary."""
        return cls(
            conflict_id=data.get("conflict_id", ""),
            inspection_id=data.get("inspection_id", ""),
            entity_type=data.get("entity_type", SyncEntityType.INSPECTION),
            entity_id=data.get("entity_id", ""),
            classification=data.get("classification", SyncConflictClassification.MUST_REJECT),
            code=data.get("code", "CONFLICT"),
            message=data.get("message", ""),
            server_state_reference=data.get("server_state_reference", {}),
            client_state_reference=data.get("client_state_reference", {}),
            detected_at=data.get("detected_at"),
        )


# =====================================================================
# 7. Sync Status & Sync Manifest Contracts
# =====================================================================

class SyncStatus(str, Enum):
    """Synchronization state machine status (strictly orthogonal to InspectionStatus)."""

    DRAFT_LOCAL = "DRAFT_LOCAL"
    SYNC_PENDING = "SYNC_PENDING"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    SYNC_FAILED = "SYNC_FAILED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    REVALIDATED = "REVALIDATED"


class SyncManifest:
    """Authoritative snapshot answering 'What has been synchronized for this inspection?'"""

    def __init__(
        self,
        inspection_id: str,
        lifecycle_status: str,
        sync_status: SyncStatus | str = SyncStatus.SYNC_PENDING,
        entity_acknowledgements: list[SyncAcknowledgement] | None = None,
        image_hashes: dict[str, str] | None = None,
        legal_snapshot_id: str | None = None,
        evaluation_metadata: EvaluationMetadata | None = None,
        last_synced_at: str | None = None,
    ) -> None:
        self.inspection_id = str(inspection_id)
        self.lifecycle_status = str(lifecycle_status)

        if isinstance(sync_status, str):
            self.sync_status = SyncStatus(sync_status)
        else:
            self.sync_status = sync_status

        self.entity_acknowledgements = list(entity_acknowledgements or [])
        self.image_hashes = dict(image_hashes or {})
        self.legal_snapshot_id = str(legal_snapshot_id) if legal_snapshot_id else None
        self.evaluation_metadata = evaluation_metadata
        self.last_synced_at = str(last_synced_at) if last_synced_at else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize sync manifest."""
        return {
            "inspection_id": self.inspection_id,
            "lifecycle_status": self.lifecycle_status,
            "sync_status": self.sync_status.value,
            "entity_acknowledgements": [ack.to_dict() for ack in self.entity_acknowledgements],
            "image_hashes": dict(self.image_hashes),
            "legal_snapshot_id": self.legal_snapshot_id,
            "evaluation_metadata": self.evaluation_metadata.to_dict() if self.evaluation_metadata else None,
            "last_synced_at": self.last_synced_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncManifest:
        """Construct instance from dictionary payload."""
        eval_meta = None
        if data.get("evaluation_metadata"):
            eval_meta = EvaluationMetadata.from_dict(data["evaluation_metadata"])

        acks = [SyncAcknowledgement.from_dict(a) for a in data.get("entity_acknowledgements", [])]

        return cls(
            inspection_id=data.get("inspection_id", ""),
            lifecycle_status=data.get("lifecycle_status", "COMPLETED"),
            sync_status=data.get("sync_status", SyncStatus.SYNC_PENDING),
            entity_acknowledgements=acks,
            image_hashes=data.get("image_hashes", {}),
            legal_snapshot_id=data.get("legal_snapshot_id"),
            evaluation_metadata=eval_meta,
            last_synced_at=data.get("last_synced_at"),
        )
