"""Deterministic Cryptographic Verifier for Evidence Integrity and Custody Chains (Phase U25).

Executes rigorous verification of:
1. Raw evidence byte SHA-256 integrity against the recorded immutable content_hash.
2. Individual event cryptographic hash integrity.
3. Strict parent-hash linking across chronological custody events (previous_event_hash).
4. Evidence and inspection scope isolation (detecting cross-inspection or cross-evidence pollution).
5. Chain completeness and broken link localization.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Sequence

from backend.app.services.evidence_chain.models import (
    EvidenceChainEvent,
    EvidenceIntegrityStatus,
    EvidenceIntegrityVerification,
    EvidenceRecord,
)


class EvidenceChainVerifier:
    """Verifies evidence cryptographic identity and audit chain integrity."""

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute lowercase hex SHA-256 of byte payload."""
        return hashlib.sha256(data).hexdigest().lower()

    @classmethod
    def verify_bytes_hash(
        cls,
        data: bytes,
        expected_hash: str,
    ) -> tuple[bool, str]:
        """Verify that raw bytes match an expected SHA-256 digest."""
        computed = cls.compute_sha256(data)
        clean_expected = str(expected_hash).strip().lower()
        is_match = computed == clean_expected
        return is_match, computed

    @classmethod
    def verify_chain(
        cls,
        events: Sequence[EvidenceChainEvent],
        expected_evidence_id: str,
        expected_inspection_id: str,
    ) -> tuple[bool, str | None, list[str]]:
        """Verify append-oriented cryptographic chain continuity.

        Returns:
            (is_valid, broken_event_id, error_codes)
        """
        error_codes: list[str] = []
        if not events:
            return False, None, ["NO_CHAIN_EVENTS"]

        exp_ev_id = str(expected_evidence_id).strip()
        exp_insp_id = str(expected_inspection_id).strip()

        previous_hash: str | None = None

        for idx, evt in enumerate(events):
            # 1. Verify evidence_id scope
            if str(evt.evidence_id).strip() != exp_ev_id:
                error_codes.append(f"CROSS_EVIDENCE_POLLUTION: event '{evt.event_id}' has evidence_id '{evt.evidence_id}' (expected '{exp_ev_id}')")
                return False, evt.event_id, error_codes

            # 2. Verify inspection_id scope
            if str(evt.inspection_id).strip() != exp_insp_id:
                error_codes.append(f"CROSS_INSPECTION_POLLUTION: event '{evt.event_id}' has inspection_id '{evt.inspection_id}' (expected '{exp_insp_id}')")
                return False, evt.event_id, error_codes

            # 3. Verify event hash integrity
            computed_hash = evt.compute_event_hash()
            if evt.event_hash != computed_hash:
                error_codes.append(f"TAMPERED_EVENT_HASH: event '{evt.event_id}' declared '{evt.event_hash}' != computed '{computed_hash}'")
                return False, evt.event_id, error_codes

            # 4. Verify previous_event_hash linking
            if idx == 0:
                if evt.previous_event_hash is not None and evt.previous_event_hash != "":
                    error_codes.append(f"INVALID_ROOT_PREVIOUS_HASH: root event '{evt.event_id}' must have null previous_event_hash, got '{evt.previous_event_hash}'")
                    return False, evt.event_id, error_codes
            else:
                if evt.previous_event_hash != previous_hash:
                    error_codes.append(f"BROKEN_CHAIN_LINK: event '{evt.event_id}' previous_event_hash '{evt.previous_event_hash}' != expected '{previous_hash}'")
                    return False, evt.event_id, error_codes

            previous_hash = evt.event_hash

        return True, None, []

    @classmethod
    def verify_evidence(
        cls,
        record: EvidenceRecord,
        events: Sequence[EvidenceChainEvent],
        actual_bytes: bytes | None = None,
    ) -> EvidenceIntegrityVerification:
        """Perform comprehensive integrity and provenance audit for an evidence record."""
        now_iso = datetime.now(timezone.utc).isoformat()
        errors: list[str] = []
        details: dict[str, Any] = {}

        # 1. Verify byte content hash if bytes are available
        content_hash_valid = True
        if actual_bytes is not None:
            is_match, computed = cls.verify_bytes_hash(actual_bytes, record.content_hash)
            if not is_match:
                content_hash_valid = False
                errors.append(f"CONTENT_HASH_MISMATCH: expected '{record.content_hash}', got '{computed}'")
                details["computed_hash"] = computed
                details["expected_hash"] = record.content_hash
                details["byte_size_actual"] = len(actual_bytes)
                details["byte_size_expected"] = record.byte_size
            else:
                details["computed_hash"] = computed
                details["byte_size_verified"] = len(actual_bytes)

        # 2. Verify chain continuity
        chain_valid, broken_id, chain_errors = cls.verify_chain(
            events=events,
            expected_evidence_id=record.evidence_id,
            expected_inspection_id=record.inspection_id,
        )
        if not chain_valid:
            errors.extend(chain_errors)

        # 3. Determine overall EvidenceIntegrityStatus
        if not content_hash_valid:
            integrity_status = EvidenceIntegrityStatus.HASH_MISMATCH
        elif not chain_valid:
            integrity_status = EvidenceIntegrityStatus.CORRUPTED
        elif not events:
            integrity_status = EvidenceIntegrityStatus.UNVERIFIED
        else:
            integrity_status = EvidenceIntegrityStatus.VERIFIED

        first_ts = events[0].timestamp if events else None
        last_ts = events[-1].timestamp if events else None

        return EvidenceIntegrityVerification(
            evidence_id=record.evidence_id,
            inspection_id=record.inspection_id,
            integrity_status=integrity_status,
            content_hash_valid=content_hash_valid,
            chain_valid=chain_valid,
            event_count=len(events),
            first_event_at=first_ts,
            last_event_at=last_ts,
            broken_event_id=broken_id,
            error_codes=errors,
            details=details,
            verified_at=now_iso,
        )
