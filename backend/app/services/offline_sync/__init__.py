"""Offline Inspection & Sync package for Phase U24 (U24-A & U24-B).

Exports core domain contracts, models, enums, legal snapshot builder,
validators, durable repositories, and sync ingestion engine.
"""

from backend.app.services.offline_sync.bundle import (
    LegalSnapshotContext,
    OfflineInspectionBundle,
)
from backend.app.services.offline_sync.executor import (
    OfflineEvaluationResult,
    OfflineInspectionExecutor,
)
from backend.app.services.offline_sync.ingestion import (
    SyncIngestionService,
)
from backend.app.services.offline_sync.models import (
    DurableSyncOperationRecord,
    EvaluationMetadata,
    EvaluationMode,
    LegalSnapshotManifest,
    LegalSnapshotValidationResult,
    LegalSnapshotValidationStatus,
    OfflineInspectionMetadata,
    OperationStatus,
    SyncAckStatus,
    SyncAcknowledgement,
    SyncConflict,
    SyncConflictClassification,
    SyncEntityType,
    SyncErrorCode,
    SyncManifest,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)
from backend.app.services.offline_sync.repository import (
    DuplicateOperationIdError,
    InMemorySyncOperationRepository,
    OperationNotFoundError,
    SupabaseSyncOperationRepository,
    SyncOperationRepository,
)
from backend.app.services.offline_sync.snapshot import (
    LegalSnapshotBuilder,
    LegalSnapshotValidator,
)
from backend.app.services.offline_sync.validator import (
    SyncEntityValidator,
    SyncLifecycleValidator,
)
from backend.app.services.offline_sync.revalidation import (
    RevalidationComparison,
    ServerRevalidationResult,
    ServerRevalidationService,
)

__all__ = [
    "EvaluationMode",
    "EvaluationMetadata",
    "LegalSnapshotManifest",
    "LegalSnapshotValidationStatus",
    "LegalSnapshotValidationResult",
    "OfflineInspectionMetadata",
    "OperationStatus",
    "SyncErrorCode",
    "DurableSyncOperationRecord",
    "SyncEntityType",
    "SyncOperationType",
    "SyncOperation",
    "SyncAckStatus",
    "SyncAcknowledgement",
    "SyncConflictClassification",
    "SyncConflict",
    "SyncStatus",
    "SyncManifest",
    "LegalSnapshotBuilder",
    "LegalSnapshotValidator",
    "SyncOperationRepository",
    "InMemorySyncOperationRepository",
    "SupabaseSyncOperationRepository",
    "DuplicateOperationIdError",
    "OperationNotFoundError",
    "SyncEntityValidator",
    "SyncLifecycleValidator",
    "SyncIngestionService",
    "OfflineInspectionBundle",
    "LegalSnapshotContext",
    "OfflineEvaluationResult",
    "OfflineInspectionExecutor",
    "RevalidationComparison",
    "ServerRevalidationResult",
    "ServerRevalidationService",
]

