"""Structural and Integrity Validation for Phase U24-B Sync Ingestion.

Enforces:
1. Content-hash integrity verification (SHA-256 of canonical JSON payload)
2. Structural entity validation across all SyncEntityType categories
3. Dependency state verification (pending vs rejected vs satisfied)
4. Circular dependency cycle detection
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.app.services.offline_sync.models import (
    OperationStatus,
    SyncEntityType,
    SyncErrorCode,
    SyncOperation,
    SyncStatus,
)
from backend.app.services.offline_sync.repository import SyncOperationRepository


class SyncEntityValidator:
    """Validates payload integrity, structural correctness, and dependency graphs."""

    @staticmethod
    def verify_content_hash(payload: Any, declared_hash: str) -> tuple[bool, str]:
        """Verify that the declared SHA-256 matches the canonical JSON serialization of the payload.
        
        Returns:
            (is_valid, computed_hash)
        """
        canonical_json = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        computed_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        is_valid = computed_hash == declared_hash
        return is_valid, computed_hash

    @staticmethod
    def validate_entity_structure(operation: SyncOperation) -> tuple[bool, str | None, str | None]:
        """Perform structural validation on an operation according to its entity_type.
        
        Returns:
            (is_valid, error_code, error_message)
        """
        if not operation.operation_id or not operation.operation_id.strip():
            return False, SyncErrorCode.SYNC_VALIDATION_ERROR.value, "operation_id cannot be empty."

        if not operation.inspection_id or not operation.inspection_id.strip():
            return False, SyncErrorCode.SYNC_VALIDATION_ERROR.value, "inspection_id cannot be empty."

        if not operation.entity_id or not operation.entity_id.strip():
            return False, SyncErrorCode.SYNC_VALIDATION_ERROR.value, "entity_id cannot be empty."

        payload = operation.payload or {}
        etype = operation.entity_type

        if etype == SyncEntityType.INSPECTION:
            # Inspection session container: payload may contain client metadata
            return True, None, None

        elif etype == SyncEntityType.IMAGE:
            image_id = payload.get("image_id") or operation.entity_id
            if not image_id:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "IMAGE operation missing image_id."
            if "source_hash" not in payload and "normalized_hash" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "IMAGE operation missing hash metadata."
            return True, None, None

        elif etype == SyncEntityType.OCR_OBSERVATION:
            if "image_id" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "OCR_OBSERVATION requires referenced image_id."
            if "raw_text" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "OCR_OBSERVATION requires raw_text."
            return True, None, None

        elif etype == SyncEntityType.EVIDENCE:
            if "field" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "EVIDENCE candidate requires target field."
            if "raw_text" not in payload and "normalized_text" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "EVIDENCE requires raw_text or normalized_text."
            return True, None, None

        elif etype == SyncEntityType.FACT:
            if "fact_key" not in payload and "key" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "FACT requires fact_key."
            return True, None, None

        elif etype == SyncEntityType.APPLICABILITY:
            if "rule_id" not in payload and "rule_version_id" not in payload and "decision" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "APPLICABILITY requires rule or decision reference."
            return True, None, None

        elif etype == SyncEntityType.REQUIREMENT_RESULT:
            if "requirement_id" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "REQUIREMENT_RESULT requires requirement_id."
            if "status" not in payload:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "REQUIREMENT_RESULT requires compliance status."
            return True, None, None

        elif etype == SyncEntityType.REPORT:
            # Report structural payload validation
            if not payload and not operation.entity_id:
                return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, "REPORT requires report payload or identifier."
            return True, None, None

        return False, SyncErrorCode.SYNC_INVALID_ENTITY.value, f"Unsupported entity type: {etype}"

    @staticmethod
    def check_dependencies(
        dependency_ids: list[str],
        repository: SyncOperationRepository,
        current_inspection_id: str | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Verify that all prerequisite operations exist and are acknowledged.
        
        Returns:
            (can_proceed, error_code, error_message)
        """
        for dep_id in dependency_ids:
            dep_rec = repository.get_operation(dep_id)
            if dep_rec is None:
                return False, SyncErrorCode.SYNC_DEPENDENCY_PENDING.value, f"Prerequisite operation '{dep_id}' is missing/pending."

            if current_inspection_id and dep_rec.inspection_id != current_inspection_id:
                return False, SyncErrorCode.SYNC_CROSS_INSPECTION_DEPENDENCY.value, (
                    f"Prerequisite operation '{dep_id}' belongs to a different inspection ('{dep_rec.inspection_id}' != '{current_inspection_id}')."
                )

            if dep_rec.status == OperationStatus.REJECTED:
                return False, SyncErrorCode.SYNC_DEPENDENCY_REJECTED.value, f"Prerequisite operation '{dep_id}' was permanently rejected."

            if dep_rec.status in (OperationStatus.PENDING, OperationStatus.PROCESSING, OperationStatus.RETRYABLE_FAILURE):
                return False, SyncErrorCode.SYNC_DEPENDENCY_PENDING.value, f"Prerequisite operation '{dep_id}' is not yet acknowledged (status: {dep_rec.status.value})."

        return True, None, None

    @staticmethod
    def detect_circular_dependencies(operations: list[SyncOperation]) -> list[str] | None:
        """Detect if an operation graph contains circular dependency cycles.
        
        Returns:
            List of operation IDs forming the cycle if detected, or None.
        """
        graph: dict[str, list[str]] = {}
        for op in operations:
            graph[op.operation_id] = list(op.dependency_ids)

        visited: dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            visited[node] = 1
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in graph:
                    continue
                if visited.get(neighbor, 0) == 1:
                    cycle_start_idx = path.index(neighbor)
                    return path[cycle_start_idx:] + [neighbor]
                if visited.get(neighbor, 0) == 0:
                    cycle = dfs(neighbor)
                    if cycle:
                        return cycle

            path.pop()
            visited[node] = 2
            return None

        for op_id in graph:
            if visited.get(op_id, 0) == 0:
                cycle = dfs(op_id)
                if cycle:
                    return cycle

        return None


class SyncLifecycleValidator:
    """Validates monotonic and legal state machine transitions for SyncStatus."""

    VALID_TRANSITIONS: dict[SyncStatus, set[SyncStatus]] = {
        SyncStatus.DRAFT_LOCAL: {SyncStatus.DRAFT_LOCAL, SyncStatus.SYNC_PENDING, SyncStatus.SYNCING},
        SyncStatus.SYNC_PENDING: {SyncStatus.SYNC_PENDING, SyncStatus.SYNCING, SyncStatus.SYNC_FAILED},
        SyncStatus.SYNCING: {SyncStatus.SYNCING, SyncStatus.SYNCED, SyncStatus.SYNC_FAILED, SyncStatus.REVALIDATION_REQUIRED},
        SyncStatus.SYNCED: {SyncStatus.SYNCED, SyncStatus.REVALIDATION_REQUIRED, SyncStatus.REVALIDATED, SyncStatus.SYNCING},
        SyncStatus.SYNC_FAILED: {SyncStatus.SYNC_FAILED, SyncStatus.SYNC_PENDING, SyncStatus.SYNCING},
        SyncStatus.REVALIDATION_REQUIRED: {SyncStatus.REVALIDATION_REQUIRED, SyncStatus.SYNCING, SyncStatus.REVALIDATED},
        SyncStatus.REVALIDATED: {SyncStatus.REVALIDATED, SyncStatus.REVALIDATION_REQUIRED},
    }

    @classmethod
    def can_transition(cls, from_status: SyncStatus | str, to_status: SyncStatus | str) -> bool:
        """Check if transition between statuses is legally permitted."""
        f_stat = SyncStatus(from_status) if isinstance(from_status, str) else from_status
        t_stat = SyncStatus(to_status) if isinstance(to_status, str) else to_status
        return t_stat in cls.VALID_TRANSITIONS.get(f_stat, set())

    @classmethod
    def assert_can_transition(cls, from_status: SyncStatus | str, to_status: SyncStatus | str) -> None:
        """Raise ValueError if transition is invalid."""
        if not cls.can_transition(from_status, to_status):
            f_val = from_status.value if hasattr(from_status, "value") else str(from_status)
            t_val = to_status.value if hasattr(to_status, "value") else str(to_status)
            raise ValueError(f"Invalid SyncStatus transition from '{f_val}' to '{t_val}'.")
