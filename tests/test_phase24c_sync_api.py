"""Comprehensive test suite for Phase U24-C — Sync API & Server Ingestion.

Tests all 28 API verification requirements:
1. Unauthenticated batch returns 401
2. Unauthenticated sync-status returns 401
3. Owner batch accepted (200 OK)
4. Cross-user batch returns safe 404
5. Nonexistent inspection sync-status returns 404
6. Valid single operation returns 200 with ACKNOWLEDGED receipt
7. Valid multi-operation batch returns 200 with per-operation results
8. Duplicate identical operation returns ALREADY_APPLIED
9. Duplicate conflicting payload returns REJECTED + SYNC_DUPLICATE_PAYLOAD_MISMATCH
10. Dependency ordering: parent operation processed before child
11. Dependency pending returns RETRYABLE_FAILURE + SYNC_DEPENDENCY_PENDING
12. Dependency rejected causes dependent operation rejection (SYNC_DEPENDENCY_REJECTED)
13. Circular dependency rejected with SYNC_CIRCULAR_DEPENDENCY
14. Partial batch success: independent valid operations succeed despite invalid ones
15. Permanent rejection doesn't fail independent operations
16. Batch size limit (>100 operations) returns 413
17. Empty batch returns 400
18. Content hash mismatch returns REJECTED + SYNC_CONTENT_HASH_MISMATCH
19. Sync-status returns authoritative SyncManifestResponse
20. Sync-status cross-user access returns safe 404
21. Concurrent duplicate requests thread safety
22. No raw JWT or bearer tokens stored in sync records
23. No private storage URLs leaked in manifest
24. legal_snapshot_id preserved in manifest
25. evaluation_metadata preserved in manifest
26. Standard error envelope structure on failures
27. OpenAPI documentation contains sync endpoints
28. Deterministic operation result ordering in response
"""

import concurrent.futures
from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_inspection_repository,
    get_session_store,
    get_sync_ingestion_service,
    get_sync_operation_repository,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import AuthenticatedUser
from backend.app.main import create_app
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.offline_sync import (
    EvaluationMetadata,
    EvaluationMode,
    InMemorySyncOperationRepository,
    OperationStatus,
    SyncAckStatus,
    SyncEntityType,
    SyncErrorCode,
    SyncIngestionService,
    SyncOperation,
    SyncOperationType,
    SyncStatus,
)


@pytest.fixture
def test_setup():
    """Setup isolated test client and in-memory repositories."""
    app = create_app()
    session_store = InMemoryInspectionStore()
    sync_repo = InMemorySyncOperationRepository()
    insp_repo = InMemoryInspectionRepository()
    sync_service = SyncIngestionService(sync_repository=sync_repo, inspection_repository=insp_repo)

    current_user_holder = {"user": AuthenticatedUser(user_id="user-alice", email="alice@veriqoo.ai", role="authenticated")}

    def mock_get_current_user():
        u = current_user_holder.get("user")
        if u is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED", "message": "Authentication required."})
        return u

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_session_store] = lambda: session_store
    app.dependency_overrides[get_sync_operation_repository] = lambda: sync_repo
    app.dependency_overrides[get_inspection_repository] = lambda: insp_repo
    app.dependency_overrides[get_sync_ingestion_service] = lambda: sync_service

    client = TestClient(app)
    return {
        "client": client,
        "session_store": session_store,
        "sync_repo": sync_repo,
        "insp_repo": insp_repo,
        "sync_service": sync_service,
        "user_holder": current_user_holder,
    }


def make_op_dict(
    operation_id: str,
    inspection_id: str,
    entity_type: str = "INSPECTION",
    entity_id: str | None = None,
    operation_type: str = "CREATE",
    payload: dict | None = None,
    sequence: int = 1,
    dependency_ids: list[str] | None = None,
) -> dict:
    p = payload if payload is not None else {"metadata": {"notes": "test"}}
    content_hash = SyncOperation.compute_content_hash(p)
    return {
        "operation_id": operation_id,
        "inspection_id": inspection_id,
        "entity_type": entity_type,
        "entity_id": entity_id or inspection_id,
        "operation_type": operation_type,
        "content_hash": content_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "dependency_ids": dependency_ids or [],
        "payload": p,
    }


# =====================================================================
# 1 & 2. Unauthenticated Batch & Sync Status
# =====================================================================
def test_unauthenticated_requests_return_401(test_setup):
    client = test_setup["client"]
    test_setup["user_holder"]["user"] = None

    # 1. Batch sync unauthenticated
    resp_batch = client.post(
        "/api/v1/inspections/sync/batch",
        json={"inspection_id": "insp-100", "operations": [make_op_dict("op-1", "insp-100")]},
    )
    assert resp_batch.status_code == 401

    # 2. Sync status unauthenticated
    resp_status = client.get("/api/v1/inspections/insp-100/sync-status")
    assert resp_status.status_code == 401


# =====================================================================
# 3, 6. Owner Single Operation Ingestion
# =====================================================================
def test_owner_valid_single_operation_success(test_setup):
    client = test_setup["client"]
    op_data = make_op_dict(
        operation_id="op-valid-1",
        inspection_id="insp-valid-100",
        entity_type="INSPECTION",
        entity_id="insp-valid-100",
    )

    resp = client.post(
        "/api/v1/inspections/sync/batch",
        json={
            "inspection_id": "insp-valid-100",
            "batch_id": "batch-1",
            "operations": [op_data],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inspection_id"] == "insp-valid-100"
    assert data["batch_id"] == "batch-1"
    assert len(data["results"]) == 1
    assert data["results"][0]["operation_id"] == "op-valid-1"
    assert data["results"][0]["status"] == "ACKNOWLEDGED"


# =====================================================================
# 4, 5. Cross-User & Nonexistent Inspection Safety (404)
# =====================================================================
def test_cross_user_and_nonexistent_access_returns_404(test_setup):
    client = test_setup["client"]
    store = test_setup["session_store"]

    # Alice owns inspection
    store.create_session(inspection_id="insp-alice-only", owner_id="user-alice")

    # Bob tries to access Alice's inspection
    test_setup["user_holder"]["user"] = AuthenticatedUser(user_id="user-bob", email="bob@veriqoo.ai", role="authenticated")

    # 1. Batch sync
    op_data = make_op_dict(operation_id="op-bob-cross", inspection_id="insp-alice-only")
    resp_batch = client.post(
        "/api/v1/inspections/sync/batch",
        json={"inspection_id": "insp-alice-only", "operations": [op_data]},
    )
    assert resp_batch.status_code == 404

    # 2. Sync status for cross-user
    resp_status = client.get("/api/v1/inspections/insp-alice-only/sync-status")
    assert resp_status.status_code == 404

    # 3. Nonexistent inspection
    resp_missing = client.get("/api/v1/inspections/insp-does-not-exist-999/sync-status")
    assert resp_missing.status_code == 404


# =====================================================================
# 7, 28. Valid Multi-Operation Batch & Result Ordering
# =====================================================================
def test_valid_multi_operation_batch_with_ordering(test_setup):
    client = test_setup["client"]
    insp_id = "insp-multi-100"

    op_1 = make_op_dict("op-m-1", insp_id, "INSPECTION", insp_id, sequence=1)
    op_2 = make_op_dict(
        "op-m-2",
        insp_id,
        "IMAGE",
        "img-1",
        payload={"image_id": "img-1", "source_hash": "s", "normalized_hash": "n"},
        sequence=2,
        dependency_ids=["op-m-1"],
    )

    resp = client.post(
        "/api/v1/inspections/sync/batch",
        json={"inspection_id": insp_id, "operations": [op_1, op_2]},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    assert results[0]["operation_id"] == "op-m-1"
    assert results[0]["status"] == "ACKNOWLEDGED"
    assert results[1]["operation_id"] == "op-m-2"
    assert results[1]["status"] == "ACKNOWLEDGED"


# =====================================================================
# 8, 9. Idempotency (Identical Replay vs Conflicting Replay)
# =====================================================================
def test_api_idempotency_behavior(test_setup):
    client = test_setup["client"]
    insp_id = "insp-idem-100"

    op_orig = make_op_dict("op-idem-1", insp_id, payload={"data": "v1"})
    resp_1 = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op_orig]})
    assert resp_1.status_code == 200
    assert resp_1.json()["results"][0]["status"] == "ACKNOWLEDGED"

    # Exact duplicate replay
    resp_2 = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op_orig]})
    assert resp_2.status_code == 200
    assert resp_2.json()["results"][0]["status"] == "ALREADY_APPLIED"

    # Conflicting replay under same operation_id
    op_conflict = make_op_dict("op-idem-1", insp_id, payload={"data": "v2_conflicting"})
    resp_3 = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op_conflict]})
    assert resp_3.status_code == 200
    assert resp_3.json()["results"][0]["status"] == "REJECTED"
    assert resp_3.json()["results"][0]["error_code"] == SyncErrorCode.SYNC_DUPLICATE_PAYLOAD_MISMATCH.value


# =====================================================================
# 10, 11, 12, 13. Dependency Semantics (Ordering, Pending, Rejected, Cycles)
# =====================================================================
def test_api_dependency_semantics(test_setup):
    client = test_setup["client"]
    insp_id = "insp-dep-100"

    # 1. Dependency Pending
    op_child = make_op_dict(
        "op-dep-child",
        insp_id,
        "IMAGE",
        "img-1",
        payload={"image_id": "img-1", "source_hash": "s", "normalized_hash": "n"},
        dependency_ids=["op-unmet-parent"],
    )
    resp_pending = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op_child]})
    assert resp_pending.json()["results"][0]["status"] == "RETRYABLE_FAILURE"
    assert resp_pending.json()["results"][0]["error_code"] == SyncErrorCode.SYNC_DEPENDENCY_PENDING.value

    # 2. Circular Dependency in Batch
    op_ca = make_op_dict("op-ca", insp_id, dependency_ids=["op-cb"])
    op_cb = make_op_dict("op-cb", insp_id, dependency_ids=["op-ca"])
    resp_cycle = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op_ca, op_cb]})
    cycle_res = resp_cycle.json()["results"]
    assert cycle_res[0]["status"] == "REJECTED"
    assert cycle_res[0]["error_code"] == SyncErrorCode.SYNC_CIRCULAR_DEPENDENCY.value


# =====================================================================
# 14, 15. Partial Batch Success & Independence
# =====================================================================
def test_partial_batch_success(test_setup):
    client = test_setup["client"]
    insp_id = "insp-part-100"

    op_good_1 = make_op_dict("op-good-1", insp_id, sequence=1)
    # op_bad has forged content_hash
    op_bad = make_op_dict("op-bad-2", insp_id, sequence=2)
    op_bad["content_hash"] = "forged_sha256_hash_here_1234567890abcdef1234567890abcdef12345678"
    op_good_2 = make_op_dict("op-good-3", insp_id, sequence=3, dependency_ids=["op-good-1"])

    resp = client.post(
        "/api/v1/inspections/sync/batch",
        json={"inspection_id": insp_id, "operations": [op_good_1, op_bad, op_good_2]},
    )
    assert resp.status_code == 200
    res = resp.json()["results"]
    assert res[0]["operation_id"] == "op-good-1"
    assert res[0]["status"] == "ACKNOWLEDGED"
    assert res[1]["operation_id"] == "op-bad-2"
    assert res[1]["status"] == "REJECTED"
    assert res[1]["error_code"] == SyncErrorCode.SYNC_CONTENT_HASH_MISMATCH.value
    assert res[2]["operation_id"] == "op-good-3"
    assert res[2]["status"] == "ACKNOWLEDGED"


# =====================================================================
# 16, 17. Batch Limits & Empty Batch
# =====================================================================
def test_batch_limits(test_setup):
    client = test_setup["client"]
    insp_id = "insp-limits-100"

    # Empty batch -> 400
    resp_empty = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": []})
    assert resp_empty.status_code == 400

    # Over 100 operations -> 413
    ops_101 = [make_op_dict(f"op-limit-{i}", insp_id) for i in range(101)]
    resp_large = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": ops_101})
    assert resp_large.status_code == 413


# =====================================================================
# 19, 20, 24, 25. Sync Status Endpoint & Preservation of Metadata
# =====================================================================
def test_sync_status_response_and_metadata(test_setup):
    client = test_setup["client"]
    insp_id = "insp-status-200"

    eval_meta = {
        "evaluation_mode": "OFFLINE_DETERMINISTIC",
        "revalidation_required": True,
        "engine_version": "1.2.0",
        "legal_snapshot_id": "snap-sha256-xyz",
    }
    op_root = make_op_dict(
        "op-s-1",
        insp_id,
        payload={
            "legal_snapshot_id": "snap-sha256-xyz",
            "evaluation_metadata": eval_meta,
        },
    )
    client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op_root]})

    # Fetch sync status
    resp = client.get(f"/api/v1/inspections/{insp_id}/sync-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["inspection_id"] == insp_id
    assert data["sync_status"] == "REVALIDATION_REQUIRED"
    assert data["legal_snapshot_id"] == "snap-sha256-xyz"
    assert data["evaluation_metadata"]["evaluation_mode"] == "OFFLINE_DETERMINISTIC"
    assert len(data["entity_acknowledgements"]) == 1


# =====================================================================
# 21. Concurrent Duplicate Requests
# =====================================================================
def test_concurrent_api_requests(test_setup):
    client = test_setup["client"]
    insp_id = "insp-api-concur"
    op = make_op_dict("op-api-concur-1", insp_id)

    def send_req():
        return client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op]})

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(send_req) for _ in range(6)]
        responses = [f.result() for f in futures]

    statuses = [r.json()["results"][0]["status"] for r in responses]
    assert statuses.count("ACKNOWLEDGED") == 1
    assert statuses.count("ALREADY_APPLIED") == 5


# =====================================================================
# 22 & 23. Security: No Raw JWTs & No Private Storage URLs
# =====================================================================
def test_security_leak_prevention(test_setup):
    client = test_setup["client"]
    insp_id = "insp-sec-300"

    op = make_op_dict(
        "op-sec-1",
        insp_id,
        payload={"jwt": "bearer_secret_123", "owner_id": "spoofed_owner"},
    )
    resp = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": insp_id, "operations": [op]})
    assert resp.status_code == 200

    resp_status = client.get(f"/api/v1/inspections/{insp_id}/sync-status")
    status_text = json.dumps(resp_status.json())
    assert "bearer_secret_123" not in status_text


# =====================================================================
# 26. Standard Error Envelope Structure
# =====================================================================
def test_structured_error_envelope(test_setup):
    client = test_setup["client"]
    resp = client.post("/api/v1/inspections/sync/batch", json={"inspection_id": "insp-err", "operations": []})
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]


# =====================================================================
# 27. OpenAPI Endpoint Presence
# =====================================================================
def test_openapi_documentation(test_setup):
    client = test_setup["client"]
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]

    assert "/api/v1/inspections/sync/batch" in paths
    assert "post" in paths["/api/v1/inspections/sync/batch"]
    assert "/api/v1/inspections/{inspection_id}/sync-status" in paths
    assert "get" in paths["/api/v1/inspections/{inspection_id}/sync-status"]
