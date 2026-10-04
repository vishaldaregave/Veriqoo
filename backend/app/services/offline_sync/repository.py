"""Durable repository implementations for Phase U24-B Sync Operations.

Provides:
1. Abstract SyncOperationRepository contract
2. Thread-safe InMemorySyncOperationRepository for unit/integration testing
3. SupabaseSyncOperationRepository for PostgreSQL/Supabase database persistence
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import json
import threading
from typing import Any, Sequence
import uuid

import requests

from backend.app.config import Settings, get_settings
from backend.app.services.offline_sync.models import (
    DurableSyncOperationRecord,
    OperationStatus,
    SyncEntityType,
    SyncOperation,
    SyncOperationType,
)


class SyncOperationRepository(abc.ABC):
    """Abstract repository contract for durable sync operation persistence."""

    @abc.abstractmethod
    def save_operation(self, record: DurableSyncOperationRecord) -> DurableSyncOperationRecord:
        """Persist a new sync operation record.
        
        Must raise a duplicate/conflict error if operation_id already exists.
        """
        pass

    @abc.abstractmethod
    def get_operation(self, operation_id: str) -> DurableSyncOperationRecord | None:
        """Retrieve a sync operation record by its operation_id."""
        pass

    @abc.abstractmethod
    def update_operation_status(
        self,
        operation_id: str,
        status: OperationStatus,
        acknowledged_at: datetime | str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        attempt_count: int | None = None,
    ) -> DurableSyncOperationRecord:
        """Update the processing status and diagnostic result of an operation."""
        pass

    @abc.abstractmethod
    def list_operations_for_inspection(self, inspection_id: str) -> list[DurableSyncOperationRecord]:
        """List all sync operation records for a given inspection, ordered by creation/sequence."""
        pass


class DuplicateOperationIdError(Exception):
    """Raised when an operation with the same operation_id already exists in the repository."""

    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id
        super().__init__(f"Operation with id '{operation_id}' already exists.")


class OperationNotFoundError(Exception):
    """Raised when an operation cannot be found."""

    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id
        super().__init__(f"Operation with id '{operation_id}' was not found.")


class InMemorySyncOperationRepository(SyncOperationRepository):
    """Thread-safe in-memory store for sync operations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: dict[str, DurableSyncOperationRecord] = {}

    def save_operation(self, record: DurableSyncOperationRecord) -> DurableSyncOperationRecord:
        with self._lock:
            op_id = record.operation_id
            if op_id in self._operations:
                raise DuplicateOperationIdError(op_id)

            # Store defensive copy
            stored = DurableSyncOperationRecord.from_dict(record.to_dict())
            self._operations[op_id] = stored
            return DurableSyncOperationRecord.from_dict(stored.to_dict())

    def get_operation(self, operation_id: str) -> DurableSyncOperationRecord | None:
        with self._lock:
            record = self._operations.get(operation_id)
            if record is None:
                return None
            return DurableSyncOperationRecord.from_dict(record.to_dict())

    def update_operation_status(
        self,
        operation_id: str,
        status: OperationStatus,
        acknowledged_at: datetime | str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        attempt_count: int | None = None,
    ) -> DurableSyncOperationRecord:
        with self._lock:
            record = self._operations.get(operation_id)
            if record is None:
                raise OperationNotFoundError(operation_id)

            record.status = status
            if acknowledged_at is not None:
                if isinstance(acknowledged_at, datetime):
                    record.acknowledged_at = acknowledged_at.isoformat()
                else:
                    record.acknowledged_at = str(acknowledged_at)
            if error_code is not None:
                record.error_code = error_code
            if error_message is not None:
                record.error_message = error_message
            if attempt_count is not None:
                record.attempt_count = attempt_count

            return DurableSyncOperationRecord.from_dict(record.to_dict())

    def list_operations_for_inspection(self, inspection_id: str) -> list[DurableSyncOperationRecord]:
        with self._lock:
            records = [
                DurableSyncOperationRecord.from_dict(r.to_dict())
                for r in self._operations.values()
                if r.inspection_id == str(inspection_id)
            ]
            records.sort(key=lambda r: (r.sequence, r.created_at))
            return records


class SupabaseSyncOperationRepository(SyncOperationRepository):
    """Supabase REST/PostgREST implementation of SyncOperationRepository."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.supabase_url.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def save_operation(self, record: DurableSyncOperationRecord) -> DurableSyncOperationRecord:
        payload = {
            "operation_id": record.operation_id,
            "inspection_id": record.inspection_id,
            "entity_type": record.entity_type.value,
            "entity_id": record.entity_id,
            "operation_type": record.operation_type.value,
            "content_hash": record.content_hash,
            "dependency_ids": record.dependency_ids,
            "status": record.status.value,
            "attempt_count": record.attempt_count,
            "payload": record.payload,
            "error_code": record.error_code,
            "error_message": record.error_message,
            "metadata": record.metadata,
            "created_at": record.created_at,
            "received_at": record.received_at,
            "acknowledged_at": record.acknowledged_at,
        }

        resp = requests.post(
            f"{self.base_url}/inspection_sync_operations",
            headers=self.headers,
            json=payload,
            timeout=10,
        )

        if resp.status_code in (409, 400) and "duplicate key" in resp.text.lower():
            raise DuplicateOperationIdError(record.operation_id)
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"Failed to persist sync operation: {resp.status_code} {resp.text}")

        data = resp.json()
        item = data[0] if isinstance(data, list) and data else data
        return DurableSyncOperationRecord.from_dict(item)

    def get_operation(self, operation_id: str) -> DurableSyncOperationRecord | None:
        resp = requests.get(
            f"{self.base_url}/inspection_sync_operations?operation_id=eq.{operation_id}&select=*",
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return DurableSyncOperationRecord.from_dict(data[0])
        return None

    def update_operation_status(
        self,
        operation_id: str,
        status: OperationStatus,
        acknowledged_at: datetime | str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        attempt_count: int | None = None,
    ) -> DurableSyncOperationRecord:
        patch_payload: dict[str, Any] = {"status": status.value}
        if acknowledged_at is not None:
            patch_payload["acknowledged_at"] = (
                acknowledged_at.isoformat() if isinstance(acknowledged_at, datetime) else str(acknowledged_at)
            )
        if error_code is not None:
            patch_payload["error_code"] = error_code
        if error_message is not None:
            patch_payload["error_message"] = error_message
        if attempt_count is not None:
            patch_payload["attempt_count"] = attempt_count

        resp = requests.patch(
            f"{self.base_url}/inspection_sync_operations?operation_id=eq.{operation_id}",
            headers=self.headers,
            json=patch_payload,
            timeout=10,
        )
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"Failed to update sync operation status: {resp.status_code} {resp.text}")

        data = resp.json()
        item = data[0] if isinstance(data, list) and data else data
        return DurableSyncOperationRecord.from_dict(item)

    def list_operations_for_inspection(self, inspection_id: str) -> list[DurableSyncOperationRecord]:
        resp = requests.get(
            f"{self.base_url}/inspection_sync_operations?inspection_id=eq.{inspection_id}&order=sequence.asc,created_at.asc&select=*",
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return [DurableSyncOperationRecord.from_dict(d) for d in data]
        return []
