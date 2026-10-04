"""Durable repository abstractions and implementations for Evidence Records and Chain Events (Phase U25).

Provides:
1. Abstract EvidenceChainRepository contract
2. Thread-safe InMemoryEvidenceChainRepository for testing and standalone execution
3. SupabaseEvidenceChainRepository for PostgREST database persistence
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
from backend.app.services.evidence_chain.models import (
    ChainEventType,
    EvidenceChainEvent,
    EvidenceIntegrityStatus,
    EvidenceRecord,
)


class DuplicateEvidenceIdError(Exception):
    """Raised when an evidence record with the same ID already exists."""
    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        super().__init__(f"Evidence record with ID '{evidence_id}' already exists.")


class DuplicateEventIdError(Exception):
    """Raised when a chain event with the same ID already exists."""
    def __init__(self, event_id: str) -> None:
        self.event_id = event_id
        super().__init__(f"Chain event with ID '{event_id}' already exists.")


class EvidenceRecordNotFoundError(Exception):
    """Raised when an evidence record is not found."""
    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        super().__init__(f"Evidence record with ID '{evidence_id}' was not found.")


class EvidenceChainRepository(abc.ABC):
    """Abstract repository contract for evidence custody records and chain events."""

    @abc.abstractmethod
    def save_evidence_record(self, record: EvidenceRecord) -> EvidenceRecord:
        """Persist or idempotently record an evidence record."""
        pass

    @abc.abstractmethod
    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        """Retrieve an evidence record by ID."""
        pass

    @abc.abstractmethod
    def list_evidence_records_for_inspection(self, inspection_id: str) -> list[EvidenceRecord]:
        """List all evidence records bound to an inspection."""
        pass

    @abc.abstractmethod
    def append_chain_event(self, event: EvidenceChainEvent) -> EvidenceChainEvent:
        """Append a new cryptographic provenance event."""
        pass

    @abc.abstractmethod
    def list_chain_events_for_evidence(self, evidence_id: str) -> list[EvidenceChainEvent]:
        """List all provenance events for an evidence artifact in chronological order."""
        pass

    @abc.abstractmethod
    def list_chain_events_for_inspection(self, inspection_id: str) -> list[EvidenceChainEvent]:
        """List all provenance events for an inspection."""
        pass

    @abc.abstractmethod
    def update_integrity_status(
        self,
        evidence_id: str,
        status: EvidenceIntegrityStatus,
    ) -> EvidenceRecord:
        """Update the verified integrity status of an evidence record."""
        pass


class InMemoryEvidenceChainRepository(EvidenceChainRepository):
    """Thread-safe in-memory store for evidence records and chain events."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, EvidenceRecord] = {}  # evidence_id -> EvidenceRecord
        self._events: dict[str, list[EvidenceChainEvent]] = {}  # evidence_id -> list of events
        self._events_by_id: dict[str, EvidenceChainEvent] = {}  # event_id -> EvidenceChainEvent

    def save_evidence_record(self, record: EvidenceRecord) -> EvidenceRecord:
        with self._lock:
            ev_id = record.evidence_id
            if ev_id in self._records:
                existing = self._records[ev_id]
                if existing.inspection_id != record.inspection_id:
                    raise ValueError(f"Cannot mutate inspection_id of evidence '{ev_id}'.")
                if existing.content_hash != record.content_hash:
                    raise ValueError(f"Cannot mutate content_hash of evidence '{ev_id}'.")
                return EvidenceRecord.from_dict(existing.to_dict())

            stored = EvidenceRecord.from_dict(record.to_dict())
            self._records[ev_id] = stored
            if ev_id not in self._events:
                self._events[ev_id] = []
            return EvidenceRecord.from_dict(stored.to_dict())

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        with self._lock:
            rec = self._records.get(evidence_id)
            if rec is None:
                return None
            return EvidenceRecord.from_dict(rec.to_dict())

    def list_evidence_records_for_inspection(self, inspection_id: str) -> list[EvidenceRecord]:
        with self._lock:
            insp_id = str(inspection_id).strip()
            records = [
                EvidenceRecord.from_dict(r.to_dict())
                for r in self._records.values()
                if r.inspection_id == insp_id
            ]
            records.sort(key=lambda r: (r.received_at, r.created_at))
            return records

    def append_chain_event(self, event: EvidenceChainEvent) -> EvidenceChainEvent:
        with self._lock:
            if event.event_id in self._events_by_id:
                existing = self._events_by_id[event.event_id]
                if existing.event_hash == event.event_hash:
                    return EvidenceChainEvent.from_dict(existing.to_dict())
                raise DuplicateEventIdError(event.event_id)

            # Defensive copy
            stored = EvidenceChainEvent.from_dict(event.to_dict())
            self._events_by_id[stored.event_id] = stored

            ev_id = stored.evidence_id
            if ev_id not in self._events:
                self._events[ev_id] = []
            self._events[ev_id].append(stored)

            return EvidenceChainEvent.from_dict(stored.to_dict())

    def list_chain_events_for_evidence(self, evidence_id: str) -> list[EvidenceChainEvent]:
        with self._lock:
            events = self._events.get(evidence_id, [])
            return [EvidenceChainEvent.from_dict(e.to_dict()) for e in events]

    def list_chain_events_for_inspection(self, inspection_id: str) -> list[EvidenceChainEvent]:
        with self._lock:
            insp_id = str(inspection_id).strip()
            all_events = [
                EvidenceChainEvent.from_dict(e.to_dict())
                for e in self._events_by_id.values()
                if e.inspection_id == insp_id
            ]
            all_events.sort(key=lambda e: (e.timestamp, e.event_id))
            return all_events

    def update_integrity_status(
        self,
        evidence_id: str,
        status: EvidenceIntegrityStatus,
    ) -> EvidenceRecord:
        with self._lock:
            rec = self._records.get(evidence_id)
            if rec is None:
                raise EvidenceRecordNotFoundError(evidence_id)
            rec.integrity_status = status
            return EvidenceRecord.from_dict(rec.to_dict())


class SupabaseEvidenceChainRepository(EvidenceChainRepository):
    """PostgREST implementation of EvidenceChainRepository for PostgreSQL/Supabase."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.supabase_url.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def save_evidence_record(self, record: EvidenceRecord) -> EvidenceRecord:
        payload = record.to_dict()
        resp = requests.post(
            f"{self.base_url}/inspection_evidence_records",
            headers=self.headers,
            json=payload,
            timeout=10,
        )
        if resp.status_code in (409, 400) and "duplicate key" in resp.text.lower():
            existing = self.get_evidence_record(record.evidence_id)
            if existing and existing.content_hash == record.content_hash:
                return existing
            raise DuplicateEvidenceIdError(record.evidence_id)

        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"Failed to persist evidence record: {resp.status_code} {resp.text}")

        data = resp.json()
        item = data[0] if isinstance(data, list) and data else data
        return EvidenceRecord.from_dict(item)

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        resp = requests.get(
            f"{self.base_url}/inspection_evidence_records?evidence_id=eq.{evidence_id}&select=*",
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return EvidenceRecord.from_dict(data[0])
        return None

    def list_evidence_records_for_inspection(self, inspection_id: str) -> list[EvidenceRecord]:
        resp = requests.get(
            f"{self.base_url}/inspection_evidence_records?inspection_id=eq.{inspection_id}&order=received_at.asc,created_at.asc&select=*",
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return [EvidenceRecord.from_dict(d) for d in data]
        return []

    def append_chain_event(self, event: EvidenceChainEvent) -> EvidenceChainEvent:
        payload = event.to_dict()
        resp = requests.post(
            f"{self.base_url}/evidence_chain_events",
            headers=self.headers,
            json=payload,
            timeout=10,
        )
        if resp.status_code in (409, 400) and "duplicate key" in resp.text.lower():
            raise DuplicateEventIdError(event.event_id)

        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"Failed to persist chain event: {resp.status_code} {resp.text}")

        data = resp.json()
        item = data[0] if isinstance(data, list) and data else data
        return EvidenceChainEvent.from_dict(item)

    def list_chain_events_for_evidence(self, evidence_id: str) -> list[EvidenceChainEvent]:
        resp = requests.get(
            f"{self.base_url}/evidence_chain_events?evidence_id=eq.{evidence_id}&order=timestamp.asc,event_id.asc&select=*",
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return [EvidenceChainEvent.from_dict(d) for d in data]
        return []

    def list_chain_events_for_inspection(self, inspection_id: str) -> list[EvidenceChainEvent]:
        resp = requests.get(
            f"{self.base_url}/evidence_chain_events?inspection_id=eq.{inspection_id}&order=timestamp.asc,event_id.asc&select=*",
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return [EvidenceChainEvent.from_dict(d) for d in data]
        return []

    def update_integrity_status(
        self,
        evidence_id: str,
        status: EvidenceIntegrityStatus,
    ) -> EvidenceRecord:
        patch_payload = {"integrity_status": status.value}
        resp = requests.patch(
            f"{self.base_url}/inspection_evidence_records?evidence_id=eq.{evidence_id}",
            headers=self.headers,
            json=patch_payload,
            timeout=10,
        )
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(f"Failed to update evidence integrity status: {resp.status_code} {resp.text}")
        data = resp.json()
        item = data[0] if isinstance(data, list) and data else data
        return EvidenceRecord.from_dict(item)
