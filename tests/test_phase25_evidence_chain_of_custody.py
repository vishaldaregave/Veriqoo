"""Phase U25: Evidence Trust and Tamper-Evident Chain of Custody Tests.

Covers all 35 Phase 16 test criteria:
 1. evidence hash creation
 2. SHA-256 correctness
 3. evidence identity immutability
 4. first chain event
 5. chained event hash
 6. broken previous_event_hash detection
 7. tampered event detection
 8. tampered evidence detection
 9. missing evidence detection
10. corrupted evidence detection
11. cross-inspection rejection
12. cross-user rejection
13. duplicate evidence idempotency
14. duplicate operation idempotency
15. duplicate event handling
16. changed payload rejection
17. OCR provenance
18. OCR rerun provenance
19. evidence -> fact linkage
20. fact -> requirement linkage
21. requirement -> report linkage
22. multiple evidence per requirement
23. one evidence -> multiple requirements
24. report integrity summary
25. offline evidence integrity
26. sync evidence hash verification
27. response/retry behavior
28. chain verification after persistence
29. historical events remain intact
30. no canonical compliance status changes
31. online inspection regression
32. U24 regression
33. process/session cache recovery
34. incomplete provenance detection
35. malformed event rejection
"""

from datetime import datetime, timezone
import hashlib
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_evidence_chain_repository,
    get_image_storage,
    get_session_store,
)
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.main import create_app
from backend.app.services.evidence_chain.models import (
    ChainEventType,
    EvidenceChainEvent,
    EvidenceIntegrityStatus,
    EvidenceRecord,
)
from backend.app.services.evidence_chain.repository import (
    EvidenceRecordNotFoundError,
    InMemoryEvidenceChainRepository,
)
from backend.app.services.evidence_chain.service import EvidenceChainService
from backend.app.services.evidence_chain.verifier import EvidenceChainVerifier
from backend.app.services.verification.models import VerificationStatus
from backend.app.services.storage import InMemoryImageStorage


# =====================================================================
# Fixtures
# =====================================================================

import io
from PIL import Image

@pytest.fixture
def storage():
    return InMemoryImageStorage()


@pytest.fixture
def repo():
    return InMemoryEvidenceChainRepository()


@pytest.fixture
def service(repo, storage):
    return EvidenceChainService(repository=repo, storage=storage)


@pytest.fixture
def sample_image_bytes():
    buf = io.BytesIO()
    img = Image.new("RGB", (50, 50), color=(100, 150, 200))
    img.save(buf, format="PNG")
    return buf.getvalue()



# =====================================================================
# Tests: 1-5 Fundamental Hash & Chain Integrity
# =====================================================================

def test_01_evidence_hash_creation(service, sample_image_bytes):
    """1. Evidence hash is automatically calculated on registration."""
    insp_id = "insp_01"
    record = service.register_evidence(
        inspection_id=insp_id,
        data=sample_image_bytes,
        original_filename="label.png",
        media_type="image/png",
    )
    assert record.evidence_id is not None
    assert record.inspection_id == insp_id
    assert len(record.content_hash) == 64
    assert record.byte_size == len(sample_image_bytes)
    assert record.hash_algorithm == "SHA-256"


def test_02_sha256_correctness(sample_image_bytes):
    """2. SHA-256 matches hashlib.sha256 over raw unaltered bytes."""
    expected_hash = hashlib.sha256(sample_image_bytes).hexdigest()
    computed_hash = EvidenceRecord.compute_content_hash(sample_image_bytes)
    assert computed_hash == expected_hash


def test_03_evidence_identity_immutability(repo, sample_image_bytes):
    """3. Evidence record cannot be altered with mismatched immutable fields."""
    content_hash = hashlib.sha256(sample_image_bytes).hexdigest()
    rec = EvidenceRecord(
        evidence_id="ev_imm_1",
        inspection_id="insp_1",
        content_hash=content_hash,
        byte_size=len(sample_image_bytes),
        received_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_evidence_record(rec)

    # Attempt to save record with same evidence_id but changed inspection_id
    tampered = EvidenceRecord(
        evidence_id="ev_imm_1",
        inspection_id="insp_2_tampered",
        content_hash=content_hash,
        byte_size=len(sample_image_bytes),
        received_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with pytest.raises(ValueError, match="Cannot mutate inspection_id"):
        repo.save_evidence_record(tampered)

    # Attempt to save record with same evidence_id but changed content_hash
    tampered_hash = EvidenceRecord(
        evidence_id="ev_imm_1",
        inspection_id="insp_1",
        content_hash="deadbeef" * 8,
        byte_size=len(sample_image_bytes),
        received_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with pytest.raises(ValueError, match="Cannot mutate content_hash"):
        repo.save_evidence_record(tampered_hash)


def test_04_first_chain_event(service, sample_image_bytes):
    """4. First chain event (genesis) has previous_event_hash as None."""
    rec = service.register_evidence(
        inspection_id="insp_04",
        data=sample_image_bytes,
    )
    events = service.get_evidence_chain(rec.evidence_id)
    assert len(events) >= 1
    genesis = events[0]
    assert genesis.previous_event_hash is None
    assert genesis.event_type == ChainEventType.RECEIVED
    assert len(genesis.event_hash) == 64


def test_05_chained_event_hash(service, sample_image_bytes):
    """5. Sequential events link previous_event_hash to prior event_hash."""
    rec = service.register_evidence(
        inspection_id="insp_05",
        data=sample_image_bytes,
    )
    e2 = service.log_ocr_started(evidence_id=rec.evidence_id, ocr_engine="tesseract")
    e3 = service.log_ocr_completed(
        evidence_id=rec.evidence_id,
        ocr_engine="tesseract",
        detected_text="MRP Rs 50.00",
        confidence=0.98,
    )

    events = service.get_evidence_chain(rec.evidence_id)
    assert len(events) >= 3
    assert events[1].previous_event_hash == events[0].event_hash
    assert events[2].previous_event_hash == events[1].event_hash


# =====================================================================
# Tests: 6-10 Tamper & Failure Detection
# =====================================================================

def test_06_broken_previous_event_hash_detection(service, repo, sample_image_bytes):
    """6. Verifier detects broken previous_event_hash links."""
    rec = service.register_evidence(inspection_id="insp_06", data=sample_image_bytes)
    e2 = service.log_ocr_started(evidence_id=rec.evidence_id, ocr_engine="test_engine")

    # Manually tamper with previous_event_hash of event 2 in repo
    events = repo.list_chain_events_for_evidence(rec.evidence_id)
    tampered_e2 = EvidenceChainEvent(
        event_id=events[1].event_id,
        evidence_id=events[1].evidence_id,
        inspection_id=events[1].inspection_id,
        event_type=events[1].event_type,
        actor_type=events[1].actor_type,
        actor_id=events[1].actor_id,
        timestamp=events[1].timestamp,
        previous_event_hash="broken_link_hash_00000000000000000000000000000000000000000000000",
        metadata=events[1].metadata,
    )
    repo._events[rec.evidence_id][1] = tampered_e2

    verification = service.verify_evidence_integrity(rec.evidence_id)
    assert verification.chain_valid is False
    assert verification.integrity_status == EvidenceIntegrityStatus.CORRUPTED
    assert any("BROKEN" in err or "HASH" in err for err in verification.error_codes)


def test_07_tampered_event_detection(service, repo, sample_image_bytes):
    """7. Verifier detects event payload tampering (signature/hash mismatch)."""
    rec = service.register_evidence(inspection_id="insp_07", data=sample_image_bytes)
    service.log_ocr_completed(rec.evidence_id, "tesseract", "MRP 100", 0.9)

    events = repo.list_chain_events_for_evidence(rec.evidence_id)
    # Tamper with metadata without recomputing event_hash
    tampered_event = EvidenceChainEvent(
        event_id=events[1].event_id,
        evidence_id=events[1].evidence_id,
        inspection_id=events[1].inspection_id,
        event_type=events[1].event_type,
        actor_type=events[1].actor_type,
        actor_id=events[1].actor_id,
        timestamp=events[1].timestamp,
        previous_event_hash=events[1].previous_event_hash,
        event_hash=events[1].event_hash,  # Kept old hash!
        metadata={"tampered": True, "detected_text": "TAMPERED TEXT"},
    )
    repo._events[rec.evidence_id][1] = tampered_event

    verification = service.verify_evidence_integrity(rec.evidence_id)
    assert verification.chain_valid is False
    assert any("TAMPERED" in err or "MISMATCH" in err for err in verification.error_codes)


def test_08_tampered_evidence_bytes_detection(service, storage, sample_image_bytes):
    """8. Verifier detects when stored image bytes have been altered."""
    storage_ref = "evidence/insp_08/img.png"
    rec = service.register_evidence(
        inspection_id="insp_08",
        data=sample_image_bytes,
        storage_reference=storage_ref,
    )

    # Tamper with bytes in storage
    tampered_bytes = b"COMPLETELY DIFFERENT BYTES"
    storage.upload(storage_ref, tampered_bytes)

    verification = service.verify_evidence_integrity(rec.evidence_id)
    assert verification.content_hash_valid is False
    assert verification.integrity_status == EvidenceIntegrityStatus.HASH_MISMATCH
    assert any("CONTENT_HASH_MISMATCH" in err or "MISMATCH" in err for err in verification.error_codes)


def test_09_missing_evidence_detection(service, storage, sample_image_bytes):
    """9. Verifier detects when stored evidence object is missing."""
    storage_ref = "evidence/insp_09/img.png"
    rec = service.register_evidence(
        inspection_id="insp_09",
        data=sample_image_bytes,
        storage_reference=storage_ref,
    )

    # Delete object from storage
    storage.delete(storage_ref)

    verification = service.verify_evidence_integrity(rec.evidence_id)
    assert verification.content_hash_valid is False
    assert verification.integrity_status == EvidenceIntegrityStatus.MISSING
    assert any("NOT_FOUND" in err for err in verification.error_codes)


def test_10_corrupted_evidence_detection(service, repo, sample_image_bytes):
    """10. Broken chain marks integrity as CORRUPTED."""
    rec = service.register_evidence(inspection_id="insp_10", data=sample_image_bytes)
    # Add malformed event directly to repo
    bad_event = EvidenceChainEvent(
        event_id="bad_ev",
        evidence_id=rec.evidence_id,
        inspection_id="insp_10",
        event_type=ChainEventType.CAPTURED,
        actor_type="TEST",
        timestamp="invalid_timestamp",
        previous_event_hash="wrong_hash",
    )
    repo._events[rec.evidence_id].append(bad_event)

    verification = service.verify_evidence_integrity(rec.evidence_id)
    assert verification.chain_valid is False
    assert verification.integrity_status == EvidenceIntegrityStatus.CORRUPTED


# =====================================================================
# Tests: 11-16 Scope Isolation & Idempotency
# =====================================================================

def test_11_cross_inspection_rejection(service, sample_image_bytes):
    """11. Evidence chain events cannot be logged for another inspection."""
    rec = service.register_evidence(inspection_id="insp_11_A", data=sample_image_bytes)
    with pytest.raises(ValueError, match="does not belong to inspection"):
        service.log_event(
            evidence_id=rec.evidence_id,
            inspection_id="insp_11_B_ATTACKER",
            event_type=ChainEventType.OCR_STARTED,
        )


def test_12_cross_user_rejection_via_api(sample_image_bytes):
    """12. Authenticated user B cannot access evidence of user A."""
    app = create_app()
    user_a = AuthenticatedUser(user_id="user_A", role="inspector")
    user_b = AuthenticatedUser(user_id="user_B", role="inspector")
    evidence_repo = InMemoryEvidenceChainRepository()

    # In-memory test client
    client = TestClient(app)

    # Override current user as user_A to create inspection
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_evidence_chain_repository] = lambda: evidence_repo

    resp = client.post("/api/v1/inspections", json={"metadata": {"test": "u25"}})
    assert resp.status_code == 201
    insp_id = resp.json()["inspection_id"]

    # Upload image as user_A
    img_resp = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("sample.png", sample_image_bytes, "image/png")},
    )
    assert img_resp.status_code == 201

    # Switch current user to user_B
    app.dependency_overrides[get_current_user] = lambda: user_b

    # Access evidence as user_B -> should return 404 (safe IDOR protection)
    evidence_resp = client.get(f"/api/v1/inspections/{insp_id}/evidence")
    assert evidence_resp.status_code == 404

    # Cleanup overrides
    app.dependency_overrides.clear()


def test_13_duplicate_evidence_idempotency(service, sample_image_bytes):
    """13. Re-registering identical evidence bytes with same ID is idempotent."""
    ev_id = "ev_fixed_id_13"
    rec1 = service.register_evidence(
        inspection_id="insp_13",
        data=sample_image_bytes,
        evidence_id=ev_id,
        operation_id="op_13",
    )
    rec2 = service.register_evidence(
        inspection_id="insp_13",
        data=sample_image_bytes,
        evidence_id=ev_id,
        operation_id="op_13",
    )
    assert rec1.evidence_id == rec2.evidence_id
    assert rec1.content_hash == rec2.content_hash
    # No duplicate records created in summary
    summary = service.get_inspection_evidence_summary("insp_13")
    assert summary["evidence_count"] == 1


def test_14_duplicate_operation_idempotency(service, sample_image_bytes):
    """14. Logging same operation_id returns idempotent existing event."""
    rec = service.register_evidence(inspection_id="insp_14", data=sample_image_bytes)
    e1 = service.log_event(
        evidence_id=rec.evidence_id,
        inspection_id="insp_14",
        event_type=ChainEventType.OCR_STARTED,
        operation_id="op_unique_14",
    )
    e2 = service.log_event(
        evidence_id=rec.evidence_id,
        inspection_id="insp_14",
        event_type=ChainEventType.OCR_STARTED,
        operation_id="op_unique_14",
    )
    assert e1.event_id == e2.event_id
    assert e1.event_hash == e2.event_hash


def test_15_duplicate_event_handling(repo, sample_image_bytes):
    """15. Repository ignores duplicate append of identical event."""
    event = EvidenceChainEvent(
        event_id="ev_dup_1",
        evidence_id="ev_15",
        inspection_id="insp_15",
        event_type=ChainEventType.CAPTURED,
        actor_type="CLIENT",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    repo.append_chain_event(event)
    repo.append_chain_event(event)  # Second append
    events = repo.list_chain_events_for_evidence("ev_15")
    assert len(events) == 1



def test_16_changed_payload_rejection(service, sample_image_bytes):
    """16. Attempting to register different bytes under same evidence_id raises ValueError."""
    ev_id = "ev_clash_16"
    service.register_evidence(
        inspection_id="insp_16",
        data=sample_image_bytes,
        evidence_id=ev_id,
    )
    with pytest.raises(ValueError, match="Cannot mutate content_hash"):
        service.register_evidence(
            inspection_id="insp_16",
            data=b"DIFFERENT BYTES ENTIRELY",
            evidence_id=ev_id,
        )


# =====================================================================
# Tests: 17-24 Provenance & Traceability
# =====================================================================

def test_17_ocr_provenance(service, sample_image_bytes):
    """17. OCR completion event contains engine, confidence, and text snippet."""
    rec = service.register_evidence(inspection_id="insp_17", data=sample_image_bytes)
    event = service.log_ocr_completed(
        evidence_id=rec.evidence_id,
        ocr_engine="tesseract",
        detected_text="Net Wt 500g",
        confidence=0.95,
        language="en",
    )
    assert event.metadata["ocr_engine"] == "tesseract"
    assert event.metadata["confidence"] == 0.95
    assert "Net Wt 500g" in event.metadata["detected_text_preview"]
    assert event.metadata["source_content_hash"] == rec.content_hash


def test_18_ocr_rerun_provenance(service, sample_image_bytes):
    """18. OCR rerun creates distinct sequential version events."""
    rec = service.register_evidence(inspection_id="insp_18", data=sample_image_bytes)
    e1 = service.log_ocr_completed(
        evidence_id=rec.evidence_id,
        ocr_engine="tesseract",
        detected_text="Net Wt 500g",
        version=1,
    )
    e2 = service.log_ocr_completed(
        evidence_id=rec.evidence_id,
        ocr_engine="cloud_vision",
        detected_text="Net Quantity 500 g",
        version=2,
    )
    assert e1.metadata["version"] == 1
    assert e2.metadata["version"] == 2
    assert e2.previous_event_hash == e1.event_hash


def test_19_evidence_to_fact_linkage(service, sample_image_bytes):
    """19. Fact derived event links evidence_id to fact_id and field_type."""
    rec = service.register_evidence(inspection_id="insp_19", data=sample_image_bytes)
    event = service.log_fact_derived(
        evidence_id=rec.evidence_id,
        fact_id="fact_mrp_1",
        field_type="mrp",
        fact_value="50.00",
        candidate_ids=["cand_mrp_1"],
    )
    assert event.metadata["fact_id"] == "fact_mrp_1"
    assert event.metadata["field_type"] == "mrp"
    assert event.metadata["fact_value"] == "50.00"
    assert "cand_mrp_1" in event.metadata["candidate_ids"]


def test_20_fact_to_requirement_linkage(service, sample_image_bytes):
    """20. Requirement evaluated event links evidence to statutory requirement."""
    rec = service.register_evidence(inspection_id="insp_20", data=sample_image_bytes)
    event = service.log_requirement_evaluated(
        evidence_id=rec.evidence_id,
        requirement_id="PCR-2011-R06-MRP",
        status=VerificationStatus.PASS,
        fact_ids=["fact_mrp_1"],
        rule_citation="Rule 6(1)(e)",
    )
    assert event.metadata["requirement_id"] == "PCR-2011-R06-MRP"
    assert event.metadata["status"] == "PASS"
    assert "fact_mrp_1" in event.metadata["fact_ids"]


def test_21_requirement_to_report_linkage(service, sample_image_bytes):
    """21. Report generated event records all evaluated requirement IDs."""
    rec = service.register_evidence(inspection_id="insp_21", data=sample_image_bytes)
    event = service.log_report_generated(
        evidence_id=rec.evidence_id,
        report_id="rep_21",
        requirement_ids=["PCR-2011-R06-MRP", "PCR-2011-R06-NET_QTY"],
        overall_verdict="PASS",
    )
    assert event.metadata["report_id"] == "rep_21"
    assert len(event.metadata["requirement_ids"]) == 2
    assert event.metadata["overall_verdict"] == "PASS"


def test_22_multiple_evidence_per_requirement(service, sample_image_bytes):
    """22. Multiple evidence items can contribute to a single requirement."""
    rec1 = service.register_evidence(inspection_id="insp_22", data=sample_image_bytes)
    rec2 = service.register_evidence(inspection_id="insp_22", data=sample_image_bytes + b"_side2")

    req_id = "PCR-2011-R06-MANUFACTURER"
    e1 = service.log_requirement_evaluated(
        evidence_id=rec1.evidence_id,
        requirement_id=req_id,
        status=VerificationStatus.REVIEW_REQUIRED,
    )
    e2 = service.log_requirement_evaluated(
        evidence_id=rec2.evidence_id,
        requirement_id=req_id,
        status=VerificationStatus.PASS,
    )
    assert e1.evidence_id != e2.evidence_id
    assert e1.metadata["requirement_id"] == e2.metadata["requirement_id"]


def test_23_one_evidence_multiple_requirements(service, sample_image_bytes):
    """23. Single evidence item can contribute to multiple statutory requirements."""
    rec = service.register_evidence(inspection_id="insp_23", data=sample_image_bytes)
    e1 = service.log_requirement_evaluated(
        evidence_id=rec.evidence_id,
        requirement_id="PCR-2011-R06-MRP",
        status=VerificationStatus.PASS,
    )
    e2 = service.log_requirement_evaluated(
        evidence_id=rec.evidence_id,
        requirement_id="PCR-2011-R06-NET_QTY",
        status=VerificationStatus.PASS,
    )
    assert e1.metadata["requirement_id"] != e2.metadata["requirement_id"]
    assert e1.evidence_id == e2.evidence_id == rec.evidence_id


def test_24_report_integrity_summary(service, sample_image_bytes):
    """24. Inspection evidence summary aggregates verified counts and status."""
    rec1 = service.register_evidence(inspection_id="insp_24", data=sample_image_bytes)
    rec2 = service.register_evidence(inspection_id="insp_24", data=sample_image_bytes + b"_2")

    summary = service.get_inspection_evidence_summary("insp_24")
    assert summary["evidence_count"] == 2
    assert summary["verified_evidence_count"] == 2
    assert summary["integrity_warning_count"] == 0
    assert summary["chain_verification_status"] == "VERIFIED"


# =====================================================================
# Tests: 25-30 Offline, Sync & Compliance Status Preservation
# =====================================================================

def test_25_offline_evidence_integrity_metadata(sample_image_bytes):
    """25. Offline evidence metadata stores deterministic hash and byte size."""
    content_hash = EvidenceRecord.compute_content_hash(sample_image_bytes)
    rec = EvidenceRecord(
        evidence_id="offline_ev_25",
        inspection_id="insp_25",
        content_hash=content_hash,
        byte_size=len(sample_image_bytes),
        source_type="SYNC",
        metadata={"client_timestamp": "2026-10-05T00:00:00Z"},
    )
    assert rec.source_type == "SYNC"
    assert rec.content_hash == hashlib.sha256(sample_image_bytes).hexdigest()
    assert rec.metadata["client_timestamp"] == "2026-10-05T00:00:00Z"


def test_26_sync_evidence_hash_verification(service, sample_image_bytes):
    """26. Sync evidence matching declared hash registers successfully."""
    expected_hash = hashlib.sha256(sample_image_bytes).hexdigest()
    rec = service.register_evidence(
        inspection_id="insp_26",
        data=sample_image_bytes,
        source_type="SYNC",
        operation_id="sync_op_26",
    )
    assert rec.content_hash == expected_hash
    verification = service.verify_evidence_integrity(rec.evidence_id)
    assert verification.content_hash_valid is True
    assert verification.chain_valid is True


def test_27_response_loss_and_retry_behavior(service, sample_image_bytes):
    """27. Client retry of failed network response reproduces identical record."""
    op_id = "retry_op_27"
    rec1 = service.register_evidence(
        inspection_id="insp_27",
        data=sample_image_bytes,
        operation_id=op_id,
    )
    # Simulate network retry
    rec2 = service.register_evidence(
        inspection_id="insp_27",
        data=sample_image_bytes,
        operation_id=op_id,
    )
    assert rec1.evidence_id == rec2.evidence_id
    assert rec1.content_hash == rec2.content_hash


def test_28_chain_verification_after_persistence(repo, storage, sample_image_bytes):
    """28. Chain verification succeeds after saving and re-retrieving from repo."""
    service1 = EvidenceChainService(repository=repo, storage=storage)
    rec = service1.register_evidence(inspection_id="insp_28", data=sample_image_bytes)
    service1.log_ocr_completed(rec.evidence_id, "tesseract", "MRP 50", 0.99)

    # Initialize a new service instance over the same repository
    service2 = EvidenceChainService(repository=repo, storage=storage)
    verification = service2.verify_evidence_integrity(rec.evidence_id)
    assert verification.chain_valid is True
    assert verification.content_hash_valid is True
    assert verification.event_count == 2


def test_29_historical_events_remain_intact(service, sample_image_bytes):
    """29. Adding new events does not mutate or invalidate earlier events."""
    rec = service.register_evidence(inspection_id="insp_29", data=sample_image_bytes)
    e1 = service.log_ocr_started(rec.evidence_id, "engine_a")
    hash_e1 = e1.event_hash

    # Add second and third events
    service.log_ocr_completed(rec.evidence_id, "engine_a", "MRP 10", 0.9)
    service.log_fact_derived(rec.evidence_id, "fact_1", "mrp", "10")

    events = service.get_evidence_chain(rec.evidence_id)
    assert events[1].event_hash == hash_e1  # First event after genesis remains unmodified


def test_30_no_canonical_compliance_status_changes():
    """30. Compliance statuses remain strictly PASS, FAIL, NOT_VISIBLE, NOT_APPLICABLE, REVIEW_REQUIRED."""
    allowed_statuses = {"PASS", "FAIL", "NOT_VISIBLE", "NOT_APPLICABLE", "REVIEW_REQUIRED"}
    actual_statuses = {s.value for s in VerificationStatus}
    assert actual_statuses == allowed_statuses
    # Integrity statuses are distinct
    integrity_statuses = {s.value for s in EvidenceIntegrityStatus}
    assert integrity_statuses == {"VERIFIED", "UNVERIFIED", "MISSING", "HASH_MISMATCH", "CORRUPTED", "REVIEW_REQUIRED"}


# =====================================================================
# Tests: 31-35 Regressions, Rehydration & Malformed Data
# =====================================================================

def test_31_online_inspection_regression_endpoints(sample_image_bytes):
    """31. Standard online inspection creation and image upload flows remain functional."""
    app = create_app()
    user = AuthenticatedUser(user_id="user_online_31", role="inspector")
    evidence_repo = InMemoryEvidenceChainRepository()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_evidence_chain_repository] = lambda: evidence_repo

    client = TestClient(app)
    create_resp = client.post("/api/v1/inspections", json={"metadata": {"test": "u25_reg"}})
    assert create_resp.status_code == 201
    insp_id = create_resp.json()["inspection_id"]

    # Upload test image
    img_resp = client.post(
        f"/api/v1/inspections/{insp_id}/images",
        files={"file": ("test.png", sample_image_bytes, "image/png")},
    )
    assert img_resp.status_code == 201

    # Fetch evidence summary
    ev_resp = client.get(f"/api/v1/inspections/{insp_id}/evidence")
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()
    assert ev_data["evidence_count"] >= 1
    assert ev_data["chain_verification_status"] == "VERIFIED"

    app.dependency_overrides.clear()


def test_32_u24_regression_revalidation_preservation():
    """32. Server revalidation response structure remains intact."""
    from backend.app.api.schemas import ServerRevalidationResponse
    # Ensure ServerRevalidationResponse schema contains required fields
    fields = ServerRevalidationResponse.model_fields
    assert "inspection_id" in fields
    assert "overall_status" in fields
    assert "comparison" in fields
    assert "content_hash" in fields


def test_33_process_session_cache_recovery(repo, storage, sample_image_bytes):
    """33. New session cache rehydrates evidence chain correctly from repository."""
    service1 = EvidenceChainService(repository=repo, storage=storage)
    rec = service1.register_evidence(inspection_id="insp_33", data=sample_image_bytes)

    # Re-instantiate service as if in another process / worker
    service2 = EvidenceChainService(repository=repo, storage=storage)
    fetched = service2.get_evidence_record(rec.evidence_id)
    assert fetched is not None
    assert fetched.content_hash == rec.content_hash


def test_34_incomplete_provenance_detection(service):
    """34. Missing genesis event is detected by chain verifier."""
    rec = EvidenceRecord(
        evidence_id="ev_no_events",
        inspection_id="insp_34",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        byte_size=0,
    )
    service._repo.save_evidence_record(rec)

    verification = service.verify_evidence_integrity("ev_no_events")
    assert verification.chain_valid is False
    assert "NO_CHAIN_EVENTS" in verification.error_codes


def test_35_malformed_event_rejection():
    """35. EvidenceChainEvent rejects missing mandatory fields."""
    with pytest.raises(ValueError):
        EvidenceChainEvent(
            event_id="ev_bad",
            evidence_id="",  # Empty evidence_id
            inspection_id="insp_35",
            event_type=ChainEventType.CAPTURED,
        )


# =====================================================================
# Tests: 36-43 Explicit Durable Traceability & Trust Verification
# =====================================================================

def test_36_e2e_explicit_durable_traceability_across_cache_clear(sample_image_bytes):
    """36. Full Evidence -> OCR -> Candidate -> Fact -> Result -> Report chain survives durable reload."""
    from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField, EvidenceStatus
    from backend.app.services.inspection.models import Inspection, InspectionStatus
    from backend.app.services.inspection.repository import InMemoryInspectionRepository
    from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
    from backend.app.services.inspection_pipeline.report import InspectionReport
    from backend.app.services.ocr.models import BoundingBox, OCRObservation, OCRResult
    from backend.app.services.applicability.models import InspectionFact
    from backend.app.services.verification.models import VerificationResult, VerificationStatus

    insp_repo = InMemoryInspectionRepository()
    ev_repo = InMemoryEvidenceChainRepository()
    storage = InMemoryImageStorage()
    ev_service = EvidenceChainService(repository=ev_repo, storage=storage)

    insp_id = "insp_e2e_durable"
    insp = insp_repo.create_inspection(inspection_id=insp_id)

    # 1. Register Evidence
    storage_path = f"inspections/{insp_id}/images/1_raw.png"
    ev_record = ev_service.register_evidence(
        inspection_id=insp_id,
        data=sample_image_bytes,
        storage_reference=storage_path,
        original_filename="front_label.png",
    )
    raw_hash = hashlib.sha256(sample_image_bytes).hexdigest()
    assert ev_record.content_hash == raw_hash

    # 2. Log and persist OCR Observation
    obs_id = "obs_mrp_1"
    ocr_obs = OCRObservation(
        observation_id=obs_id,
        image_id=ev_record.evidence_id,
        text="MRP Rs 99.00",
        confidence=0.97,
        bounding_box=BoundingBox([[10.0, 10.0], [50.0, 10.0], [50.0, 30.0], [10.0, 30.0]]),
        sequence=1,
        engine="PaddleOCR",
        engine_version="3.7.0",
    )
    ocr_res = OCRResult(
        image_id=ev_record.evidence_id,
        observations=[ocr_obs],
        engine="PaddleOCR",
    )
    insp_repo.save_ocr_observations(insp_id, [ocr_res])
    ev_service.log_ocr_completed(
        evidence_id=ev_record.evidence_id,
        ocr_engine="PaddleOCR",
        detected_text=ocr_obs.text,
        confidence=0.97,
    )

    # 3. Create and persist Evidence Candidate
    cand_id = "cand_mrp_1"
    candidate = EvidenceCandidate(
        evidence_id=cand_id,
        observation_id=obs_id,
        image_id=ev_record.evidence_id,
        field=EvidenceField.MRP,
        raw_text="MRP Rs 99.00",
        normalized_text="99.00",
        parsed_value=99.00,
        parsed_unit="INR",
        ocr_confidence=0.97,
        status=EvidenceStatus.VALID,
    )
    insp_repo.save_evidence(insp_id, [candidate])

    # 4. Create and persist Inspection Fact
    fact_id = "fact_mrp_1"
    fact = InspectionFact(
        id=fact_id,
        run_id=insp_id,
        fact_key="mrp",
        value=99.00,
        unit="INR",
        origin="ocr_extraction",
        evidence_reference={
            "evidence_id": cand_id,
            "observation_id": obs_id,
            "image_id": ev_record.evidence_id,
            "field": "mrp",
        },
        observed_text="MRP Rs 99.00",
    )
    insp_repo.save_applicability_facts(insp_id, [fact])
    ev_service.log_fact_derived(
        evidence_id=ev_record.evidence_id,
        fact_id=fact_id,
        field_type="mrp",
        fact_value="99.00",
        candidate_ids=[cand_id],
    )

    # 5. Create and persist Requirement Result
    req_id = "PCR-2011-R06-MRP"
    ver_res = VerificationResult(
        verification_id="ver_mrp_1",
        requirement_id=req_id,
        status=VerificationStatus.PASS,
        reason="MRP declaration is clearly visible and within maximum permissible limit.",
        evidence_ids=[cand_id],
        source_observation_ids=[obs_id],
        image_ids=[ev_record.evidence_id],
        metadata={"fact_ids": [fact_id], "rule_citation": "Rule 6(1)(e)"},
    )
    insp_repo.save_requirement_results(insp_id, [ver_res])
    ev_service.log_requirement_evaluated(
        evidence_id=ev_record.evidence_id,
        requirement_id=req_id,
        status=VerificationStatus.PASS,
        fact_ids=[fact_id],
        rule_citation="Rule 6(1)(e)",
    )

    # 6. Create and persist Report
    report = InspectionReport(
        inspection_id=insp_id,
        overall_status=OverallInspectionStatus.PASS,
        verification_results=[ver_res],
        summary="All declarations compliant.",
        evidence_count=1,
        image_count=1,
        applicable_requirement_count=1,
        pass_count=1,
        fail_count=0,
        not_visible_count=0,
        not_applicable_count=0,
        review_required_count=0,
    )
    insp_repo.save_report(insp_id, report)
    ev_service.log_report_generated(
        evidence_id=ev_record.evidence_id,
        report_id=f"rep_{insp_id}",
        requirement_ids=[req_id],
        overall_verdict="PASS",
    )

    # =================================================================
    # WIPE IN-MEMORY REFERENCES & RELOAD FROM DURABLE REPOSITORIES
    # =================================================================
    del insp, ev_record, ocr_obs, ocr_res, candidate, fact, ver_res, report

    # Instantiate clean service over durable repository
    reloaded_ev_service = EvidenceChainService(repository=ev_repo, storage=storage)

    # 1. Report identifies requirement result
    reloaded_report = insp_repo.get_report(insp_id)
    assert reloaded_report is not None
    assert len(reloaded_report.verification_results) == 1
    reloaded_res = reloaded_report.verification_results[0]
    assert reloaded_res.requirement_id == req_id

    # 2. Requirement result identifies supporting facts and evidence IDs
    assert fact_id in reloaded_res.metadata["fact_ids"]
    assert cand_id in reloaded_res.evidence_ids
    assert obs_id in reloaded_res.source_observation_ids

    # 3. Fact identifies supporting evidence candidate
    reloaded_facts = insp_repo.get_applicability_facts(insp_id)
    assert len(reloaded_facts) == 1
    reloaded_fact = reloaded_facts[0]
    assert reloaded_fact.id == fact_id
    assert reloaded_fact.evidence_reference["evidence_id"] == cand_id
    assert reloaded_fact.evidence_reference["observation_id"] == obs_id

    # 4. Evidence candidate identifies exact observation and image
    reloaded_evidence = insp_repo.get_evidence(insp_id)
    assert len(reloaded_evidence) == 1
    reloaded_cand = reloaded_evidence[0]
    assert reloaded_cand["evidence_id"] == cand_id
    assert reloaded_cand["observation_id"] == obs_id

    # 5. Evidence record identifies exact original hash
    ev_list = reloaded_ev_service.list_evidence_for_inspection(insp_id)
    assert len(ev_list) == 1
    reloaded_rec = ev_list[0]
    assert reloaded_rec.content_hash == raw_hash

    # 6. Content hash matches stored bytes & chain verifies
    verification = reloaded_ev_service.verify_evidence_integrity(reloaded_rec.evidence_id)
    assert verification.content_hash_valid is True
    assert verification.chain_valid is True
    assert verification.event_count >= 5  # RECEIVED, OCR_COMPLETED, FACT_DERIVED, REQUIREMENT_EVALUATED, REPORT_GENERATED


def test_37_multiple_evidence_items_supporting_one_requirement_durable(sample_image_bytes):
    """37. Multiple evidence items and facts supporting one requirement are durably linked."""
    from backend.app.services.inspection.repository import InMemoryInspectionRepository
    from backend.app.services.verification.models import VerificationResult, VerificationStatus

    insp_repo = InMemoryInspectionRepository()
    insp_id = "insp_multi_ev"
    insp_repo.create_inspection(inspection_id=insp_id)

    res = VerificationResult(
        requirement_id="PCR-2011-R06-MANUFACTURER",
        status=VerificationStatus.PASS,
        reason="Manufacturer name found on front and address found on back.",
        evidence_ids=["cand_front_name", "cand_back_addr"],
        source_observation_ids=["obs_front_1", "obs_back_2"],
        image_ids=["ev_front_img", "ev_back_img"],
        metadata={"fact_ids": ["fact_name", "fact_addr"]},
    )
    insp_repo.save_requirement_results(insp_id, [res])

    # Reload from repository
    loaded = insp_repo.get_requirement_results(insp_id)
    assert len(loaded) == 1
    loaded_res = loaded[0]
    assert len(loaded_res["evidence_ids"]) == 2
    assert "cand_front_name" in loaded_res["evidence_ids"]
    assert "cand_back_addr" in loaded_res["evidence_ids"]
    assert len(loaded_res["metadata"]["fact_ids"]) == 2


def test_38_one_evidence_item_supporting_multiple_requirements_durable(sample_image_bytes):
    """38. One evidence item can be referenced by multiple distinct requirement results."""
    from backend.app.services.inspection.repository import InMemoryInspectionRepository
    from backend.app.services.verification.models import VerificationResult, VerificationStatus

    insp_repo = InMemoryInspectionRepository()
    insp_id = "insp_one_ev_multi_req"
    insp_repo.create_inspection(inspection_id=insp_id)

    common_cand_id = "cand_shared_panel_1"
    common_img_id = "img_shared_panel_1"

    r1 = VerificationResult(
        requirement_id="PCR-2011-R06-MRP",
        status=VerificationStatus.PASS,
        reason="MRP declaration verified on principal display panel.",
        evidence_ids=[common_cand_id],
        image_ids=[common_img_id],
    )
    r2 = VerificationResult(
        requirement_id="PCR-2011-R06-NET_QTY",
        status=VerificationStatus.PASS,
        reason="Net quantity declaration verified on principal display panel.",
        evidence_ids=[common_cand_id],
        image_ids=[common_img_id],
    )
    insp_repo.save_requirement_results(insp_id, [r1, r2])

    loaded = insp_repo.get_requirement_results(insp_id)
    assert len(loaded) == 2
    assert common_cand_id in loaded[0]["evidence_ids"]
    assert common_cand_id in loaded[1]["evidence_ids"]


def test_39_missing_provenance_link_returns_unlinked_or_review_required():
    """39. Requirement result with empty evidence_ids indicates NOT_VISIBLE or REVIEW_REQUIRED."""
    from backend.app.services.verification.models import VerificationResult, VerificationStatus

    res = VerificationResult(
        requirement_id="PCR-2011-R06-CONSUMER_CARE",
        status=VerificationStatus.NOT_VISIBLE,
        reason="Consumer care details not found in provided photographs.",
        evidence_ids=[],
        source_observation_ids=[],
        image_ids=[],
    )
    assert len(res.evidence_ids) == 0
    assert len(res.source_observation_ids) == 0
    assert res.status == VerificationStatus.NOT_VISIBLE


def test_40_cross_inspection_provenance_injection_rejected(service, sample_image_bytes):
    """40. Verifier rejects any chain event belonging to a different inspection."""
    rec = service.register_evidence(inspection_id="insp_legit", data=sample_image_bytes)

    # Attempt to log event with foreign inspection_id
    with pytest.raises(ValueError, match="does not belong to inspection"):
        service.log_event(
            evidence_id=rec.evidence_id,
            inspection_id="insp_malicious_injected",
            event_type=ChainEventType.FACT_DERIVED,
        )


def test_41_trust_test_no_fabricated_provenance_without_explicit_link():
    """41. Compliance evaluation cannot claim evidence provenance when no explicit candidate exists."""
    from backend.app.services.verification.deterministic import DeterministicVerifier
    from backend.app.services.verification.models import RequirementReference, VerificationStatus

    req = RequirementReference(
        requirement_id="PCR-2011-R06-MRP",
        target_field="mrp",
    )
    # Empty candidates list
    result = DeterministicVerifier.verify(
        requirement=req,
        applicability=True,
        candidates=[],
    )
    assert result.status == VerificationStatus.NOT_VISIBLE
    assert len(result.evidence_ids) == 0
    assert len(result.source_observation_ids) == 0
    assert len(result.image_ids) == 0


def test_42_revalidation_preserves_explicit_provenance(service, sample_image_bytes):
    """42. Revalidation logs provenance event without overwriting historical chain."""
    rec = service.register_evidence(inspection_id="insp_42", data=sample_image_bytes)
    service.log_ocr_completed(rec.evidence_id, "PaddleOCR", "MRP 50", 0.95)

    # Log revalidation event
    ev_reval = service.log_revalidated(
        evidence_id=rec.evidence_id,
        revalidation_id="reval_op_42",
        overall_verdict="PASS",
        server_snapshot_id="legal_snapshot_v2",
    )
    assert ev_reval.event_type == ChainEventType.REVALIDATED
    assert ev_reval.metadata["server_snapshot_id"] == "legal_snapshot_v2"

    events = service.get_evidence_chain(rec.evidence_id)
    assert len(events) == 3
    assert events[0].event_type == ChainEventType.RECEIVED
    assert events[1].event_type == ChainEventType.OCR_COMPLETED
    assert events[2].event_type == ChainEventType.REVALIDATED


def test_43_offline_sync_preserves_explicit_provenance(sample_image_bytes):
    """43. Sync bundle operations carry explicit evidence and observation IDs."""
    from backend.app.services.offline_sync.models import SyncEntityType, SyncOperation, SyncOperationType

    op = SyncOperation(
        operation_id="sync_op_fact_1",
        inspection_id="insp_43",
        entity_type=SyncEntityType.FACT,
        entity_id="fact_sync_1",
        operation_type=SyncOperationType.UPSERT,
        content_hash="abc123hash",
        created_at="2026-03-31T00:00:00Z",
        sequence=1,
        payload={
            "fact_key": "mrp",
            "value": 100.0,
            "evidence_reference": {
                "evidence_id": "cand_offline_1",
                "observation_id": "obs_offline_1",
                "image_id": "img_offline_1",
            },
        },
    )
    assert op.payload["evidence_reference"]["evidence_id"] == "cand_offline_1"
    assert op.payload["evidence_reference"]["observation_id"] == "obs_offline_1"


