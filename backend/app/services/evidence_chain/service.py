"""Orchestration service for Evidence Identity, Provenance Tracking, and Custody Chain (Phase U25).

Coordinates:
1. Cryptographic evidence registration & immutable hash binding
2. Append-oriented event chain logging (CAPTURED, RECEIVED, HASHED, STORED, OCR, NORMALIZATION, VERIFICATION, REPORT, REVALIDATION)
3. Storage integrity verification
4. OCR provenance & re-run versioning
5. Evidence -> Fact -> Requirement -> Report traceability
6. Comprehensive inspection-level integrity audits
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import threading
from typing import Any, Sequence
import uuid

from backend.app.services.evidence_chain.models import (
    ChainEventType,
    EvidenceChainEvent,
    EvidenceIntegrityStatus,
    EvidenceIntegrityVerification,
    EvidenceRecord,
)
from backend.app.services.evidence_chain.repository import (
    EvidenceChainRepository,
    InMemoryEvidenceChainRepository,
)
from backend.app.services.evidence_chain.verifier import EvidenceChainVerifier


class EvidenceChainService:
    """Provides high-level evidence identity registration and tamper-evident custody chain management."""

    def __init__(
        self,
        repository: EvidenceChainRepository | None = None,
        storage: Any | None = None,
        verifier: type[EvidenceChainVerifier] = EvidenceChainVerifier,
    ) -> None:
        self.repository = repository or InMemoryEvidenceChainRepository()
        self.storage = storage
        self.verifier = verifier
        self._lock = threading.RLock()

    @property
    def _repo(self) -> EvidenceChainRepository:
        """Convenience alias for internal repository access."""
        return self.repository

    def register_evidence(
        self,
        inspection_id: str,
        data: bytes | None = None,
        raw_bytes: bytes | None = None,
        image_id: str | None = None,
        source_id: str | None = None,
        original_filename: str | None = None,
        filename: str | None = None,
        media_type: str = "image/jpeg",
        storage_reference: str | None = None,
        storage_path: str | None = None,
        captured_at: str | None = None,
        received_at: str | None = None,
        submitted_by: str | None = None,
        source_type: str = "UPLOAD",
        metadata: dict[str, Any] | None = None,
        evidence_id: str | None = None,
        operation_id: str | None = None,
    ) -> EvidenceRecord:
        """Register a new evidence artifact with immutable cryptographic SHA-256 hash."""
        payload_bytes = data if data is not None else (raw_bytes or b"")
        fname = original_filename or filename
        storage_ref = storage_reference or storage_path

        with self._lock:
            now_iso = received_at or datetime.now(timezone.utc).isoformat()
            content_hash = self.verifier.compute_sha256(payload_bytes)
            ev_id = evidence_id or f"ev-{uuid.uuid4()}"

            insp_id_clean = str(inspection_id).strip()

            # Check operation_id idempotency
            if operation_id:
                for existing in self.repository.list_evidence_records_for_inspection(insp_id_clean):
                    if existing.metadata.get("operation_id") == operation_id:
                        return existing

            # If storage is present and storage_ref given, store bytes if not already present
            if self.storage and storage_ref and payload_bytes:
                try:
                    if hasattr(self.storage, "upload"):
                        self.storage.upload(storage_ref, payload_bytes)
                    elif hasattr(self.storage, "store"):
                        self.storage.store(storage_ref, payload_bytes)
                except Exception:
                    pass

            meta = dict(metadata or {})
            if operation_id:
                meta["operation_id"] = operation_id

            record = EvidenceRecord(
                evidence_id=ev_id,
                inspection_id=insp_id_clean,
                image_id=str(image_id).strip() if image_id else None,
                source_id=str(source_id).strip() if source_id else None,
                content_hash=content_hash,
                hash_algorithm="SHA-256",
                byte_size=len(payload_bytes),
                media_type=media_type,
                original_filename=fname,
                storage_reference=storage_ref,
                captured_at=captured_at,
                received_at=now_iso,
                created_at=now_iso,
                submitted_by=str(submitted_by).strip() if submitted_by else None,
                source_type=source_type,
                integrity_status=EvidenceIntegrityStatus.VERIFIED,
                metadata=meta,
            )

            # Idempotent persistence
            persisted_record = self.repository.save_evidence_record(record)

            # Check if root event already exists
            existing_events = self.repository.list_chain_events_for_evidence(persisted_record.evidence_id)
            if existing_events:
                return persisted_record

            # 1. Genesis event (RECEIVED, previous_event_hash = None)
            recv_event = EvidenceChainEvent(
                event_id=f"evt-{uuid.uuid4()}",
                evidence_id=persisted_record.evidence_id,
                inspection_id=persisted_record.inspection_id,
                event_type=ChainEventType.RECEIVED,
                actor_type="USER" if submitted_by else "SYSTEM",
                actor_id=submitted_by,
                timestamp=now_iso,
                previous_event_hash=None,
                operation_id=operation_id,
                metadata={
                    "byte_size": len(payload_bytes),
                    "media_type": media_type,
                    "filename": fname,
                    "source_type": source_type,
                    "content_hash": content_hash,
                },
            )
            self.repository.append_chain_event(recv_event)

            return persisted_record

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        """Retrieve evidence record by ID."""
        with self._lock:
            return self.repository.get_evidence_record(evidence_id)

    def list_evidence_for_inspection(self, inspection_id: str) -> list[EvidenceRecord]:
        """List all evidence records bound to an inspection."""
        with self._lock:
            return self.repository.list_evidence_records_for_inspection(inspection_id)

    def get_evidence_chain(self, evidence_id: str) -> list[EvidenceChainEvent]:
        """Retrieve complete chronological event chain for an evidence record."""
        with self._lock:
            return self.repository.list_chain_events_for_evidence(evidence_id)

    def log_event(
        self,
        evidence_id: str,
        inspection_id: str | None = None,
        event_type: ChainEventType | str = ChainEventType.RECEIVED,
        actor_type: str = "SYSTEM",
        actor_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        operation_id: str | None = None,
        timestamp: str | None = None,
    ) -> EvidenceChainEvent:
        """Append an append-oriented tamper-evident lifecycle event to the chain."""
        with self._lock:
            ev_id = str(evidence_id).strip()
            rec = self.repository.get_evidence_record(ev_id)
            if rec is None:
                raise ValueError(f"Cannot log event for non-existent evidence '{ev_id}'.")

            insp_id = str(inspection_id).strip() if inspection_id else rec.inspection_id
            if insp_id != rec.inspection_id:
                raise ValueError(
                    f"Evidence '{ev_id}' belongs to inspection '{rec.inspection_id}', does not belong to inspection '{insp_id}'."
                )

            now_iso = timestamp or datetime.now(timezone.utc).isoformat()
            existing_events = self.repository.list_chain_events_for_evidence(ev_id)

            # Idempotency check on operation_id
            if operation_id:
                for existing in existing_events:
                    if existing.operation_id == operation_id:
                        return existing

            prev_hash = existing_events[-1].event_hash if existing_events else None

            event = EvidenceChainEvent(
                event_id=f"evt-{uuid.uuid4()}",
                evidence_id=ev_id,
                inspection_id=insp_id,
                event_type=ChainEventType(event_type) if isinstance(event_type, str) else event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                timestamp=now_iso,
                previous_event_hash=prev_hash,
                metadata=metadata or {},
                operation_id=operation_id,
            )
            return self.repository.append_chain_event(event)

    def log_ocr_started(
        self,
        evidence_id: str,
        ocr_engine: str = "tesseract",
        language: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceChainEvent:
        """Log OCR extraction start event."""
        meta = dict(metadata or {})
        meta.update({
            "ocr_engine": ocr_engine,
            "language": language or "en",
        })
        return self.log_event(
            evidence_id=evidence_id,
            event_type=ChainEventType.OCR_STARTED,
            actor_type="OCR_ENGINE",
            actor_id=ocr_engine,
            metadata=meta,
        )

    def log_ocr_completed(
        self,
        evidence_id: str,
        ocr_engine: str = "tesseract",
        detected_text: str = "",
        confidence: float = 1.0,
        language: str | None = None,
        version: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceChainEvent:
        """Log OCR extraction completion with engine provenance and snippet metadata."""
        rec = self.get_evidence_record(evidence_id)
        source_hash = rec.content_hash if rec else ""

        meta = dict(metadata or {})
        meta.update({
            "ocr_engine": ocr_engine,
            "confidence": confidence,
            "detected_text_preview": detected_text[:200],
            "language": language or "en",
            "version": version,
            "source_content_hash": source_hash,
        })
        return self.log_event(
            evidence_id=evidence_id,
            event_type=ChainEventType.OCR_COMPLETED,
            actor_type="OCR_ENGINE",
            actor_id=ocr_engine,
            metadata=meta,
        )

    def log_fact_derived(
        self,
        evidence_id: str,
        fact_id: str,
        field_type: str,
        fact_value: Any,
        candidate_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceChainEvent:
        """Log fact derivation linking evidence observation to parsed inspection fact."""
        meta = dict(metadata or {})
        meta.update({
            "fact_id": fact_id,
            "field_type": field_type,
            "fact_value": str(fact_value),
            "candidate_ids": candidate_ids or [],
        })
        return self.log_event(
            evidence_id=evidence_id,
            event_type=ChainEventType.FACT_DERIVED,
            actor_type="SYSTEM",
            actor_id="fact_extractor",
            metadata=meta,
        )

    def log_requirement_evaluated(
        self,
        evidence_id: str,
        requirement_id: str,
        status: Any,
        fact_ids: list[str] | None = None,
        rule_citation: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceChainEvent:
        """Log statutory requirement evaluation linking evidence to legal compliance rule."""
        meta = dict(metadata or {})
        status_val = status.value if hasattr(status, "value") else str(status)
        meta.update({
            "requirement_id": requirement_id,
            "status": status_val,
            "fact_ids": fact_ids or [],
            "rule_citation": rule_citation,
        })
        return self.log_event(
            evidence_id=evidence_id,
            event_type=ChainEventType.REQUIREMENT_EVALUATED,
            actor_type="SYSTEM",
            actor_id="statutory_verifier",
            metadata=meta,
        )

    def log_report_generated(
        self,
        evidence_id: str,
        report_id: str,
        requirement_ids: list[str],
        overall_verdict: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceChainEvent:
        """Log final inspection report generation incorporating evidence."""
        meta = dict(metadata or {})
        meta.update({
            "report_id": report_id,
            "requirement_ids": requirement_ids,
            "overall_verdict": overall_verdict,
        })
        return self.log_event(
            evidence_id=evidence_id,
            event_type=ChainEventType.REPORT_GENERATED,
            actor_type="SYSTEM",
            actor_id="report_generator",
            metadata=meta,
        )

    def log_revalidated(
        self,
        evidence_id: str,
        revalidation_id: str,
        overall_verdict: str,
        server_snapshot_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceChainEvent:
        """Log authoritative server revalidation event."""
        meta = dict(metadata or {})
        meta.update({
            "revalidation_id": revalidation_id,
            "overall_verdict": overall_verdict,
            "server_snapshot_id": server_snapshot_id,
        })
        return self.log_event(
            evidence_id=evidence_id,
            event_type=ChainEventType.REVALIDATED,
            actor_type="SYSTEM",
            actor_id="server_revalidation_engine",
            metadata=meta,
        )

    def verify_evidence_integrity(
        self,
        evidence_id: str,
        actual_bytes: bytes | None = None,
    ) -> EvidenceIntegrityVerification:
        """Perform on-demand cryptographic verification of evidence record and event chain."""
        with self._lock:
            rec = self.repository.get_evidence_record(evidence_id)
            if rec is None:
                return EvidenceIntegrityVerification(
                    evidence_id=evidence_id,
                    inspection_id="",
                    integrity_status=EvidenceIntegrityStatus.MISSING,
                    content_hash_valid=False,
                    chain_valid=False,
                    event_count=0,
                    error_codes=["EVIDENCE_RECORD_NOT_FOUND"],
                )

            # Retrieve bytes from storage if available and not explicitly passed
            bytes_to_verify = actual_bytes
            if bytes_to_verify is None and self.storage and rec.storage_reference:
                try:
                    if hasattr(self.storage, "download"):
                        bytes_to_verify = self.storage.download(rec.storage_reference)
                    elif hasattr(self.storage, "retrieve"):
                        bytes_to_verify = self.storage.retrieve(rec.storage_reference)
                except Exception:
                    return EvidenceIntegrityVerification(
                        evidence_id=evidence_id,
                        inspection_id=rec.inspection_id,
                        integrity_status=EvidenceIntegrityStatus.MISSING,
                        content_hash_valid=False,
                        chain_valid=False,
                        event_count=0,
                        error_codes=["EVIDENCE_OBJECT_NOT_FOUND"],
                    )

            events = self.repository.list_chain_events_for_evidence(evidence_id)
            audit = self.verifier.verify_evidence(
                record=rec,
                events=events,
                actual_bytes=bytes_to_verify,
            )

            # Update repository integrity status if changed
            if audit.integrity_status != rec.integrity_status:
                self.repository.update_integrity_status(evidence_id, audit.integrity_status)

            return audit

    def audit_evidence_integrity(
        self,
        evidence_id: str,
        actual_bytes: bytes | None = None,
    ) -> EvidenceIntegrityVerification:
        """Alias for verify_evidence_integrity."""
        return self.verify_evidence_integrity(evidence_id=evidence_id, actual_bytes=actual_bytes)

    def get_inspection_evidence_summary(
        self,
        inspection_id: str,
    ) -> dict[str, Any]:
        """Aggregate evidence records and chain verification status for an inspection."""
        with self._lock:
            records = self.repository.list_evidence_records_for_inspection(inspection_id)
            total = len(records)
            if total == 0:
                return {
                    "inspection_id": inspection_id,
                    "evidence_count": 0,
                    "verified_evidence_count": 0,
                    "unverified_evidence_count": 0,
                    "integrity_warning_count": 0,
                    "chain_verification_status": "EMPTY",
                    "items": [],
                }

            verifications = [self.verify_evidence_integrity(r.evidence_id) for r in records]
            verified_c = sum(1 for v in verifications if v.integrity_status == EvidenceIntegrityStatus.VERIFIED)
            unverified_c = sum(1 for v in verifications if v.integrity_status in (EvidenceIntegrityStatus.UNVERIFIED, EvidenceIntegrityStatus.REVIEW_REQUIRED))
            warning_c = sum(1 for v in verifications if v.integrity_status in (EvidenceIntegrityStatus.HASH_MISMATCH, EvidenceIntegrityStatus.CORRUPTED, EvidenceIntegrityStatus.MISSING))

            if warning_c > 0:
                overall_status = "WARNING" if any(v.integrity_status == EvidenceIntegrityStatus.HASH_MISMATCH for v in verifications) else "BROKEN"
            elif verified_c == total:
                overall_status = "VERIFIED"
            else:
                overall_status = "UNVERIFIED"

            return {
                "inspection_id": inspection_id,
                "evidence_count": total,
                "verified_evidence_count": verified_c,
                "unverified_evidence_count": unverified_c,
                "integrity_warning_count": warning_c,
                "chain_verification_status": overall_status,
                "items": records,
            }

    def audit_inspection_chain(
        self,
        inspection_id: str,
    ) -> dict[str, Any]:
        """Alias for inspection chain audit metrics."""
        summary = self.get_inspection_evidence_summary(inspection_id)
        return {
            "inspection_id": inspection_id,
            "total_evidence_count": summary["evidence_count"],
            "verified_count": summary["verified_evidence_count"],
            "unverified_count": summary["unverified_evidence_count"],
            "hash_mismatch_count": summary["integrity_warning_count"],
            "all_chains_valid": summary["chain_verification_status"] == "VERIFIED",
            "audited_at": datetime.now(timezone.utc).isoformat(),
        }
