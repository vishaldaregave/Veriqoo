"""Controlled population and verification script for public.legal_corpus_embeddings (Phase 4D).

Performs:
1. Strict pre-flight checks (corpus counts, credentials, schema, dimensions)
2. Deterministic text building with SHA-256 hashing
3. Batched Gemini API embeddings (gemini-embedding-001, 3072 dims, RETRIEVAL_DOCUMENT)
4. Idempotent persistence into public.legal_corpus_embeddings
5. Post-generation audit (exact counts, zero duplicates, text-hash integrity, vector dimensions)
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

# Load credentials from both .env and backend/.env
load_dotenv(".env")
load_dotenv("backend/.env")

sys.path.insert(0, os.path.abspath("."))

from backend.app.services.legal_rag.embeddings.client import GeminiEmbeddingClient

from backend.app.services.legal_rag.embeddings.generator import LegalEmbeddingGenerator
from backend.app.services.legal_rag.embeddings.store import SupabaseEmbeddingStore
from backend.app.services.legal_rag.embeddings.text_builder import (
    build_amendment_embedding_text,
    build_provision_embedding_text,
    build_requirement_embedding_text,
    build_schedule_entry_embedding_text,
    build_table_embedding_text,
    compute_embedding_text_hash,
)
from backend.app.services.legal_rag.models import LegalEntityType

EXPECTED_CORPUS_COUNTS = {
    "legal_documents": 1,
    "legal_provisions": 341,
    "legal_schedules": 7,
    "legal_tables": 10,
    "legal_schedule_entries": 96,
    "legal_amendments": 76,
    "legal_requirements": 437,
}

EXPECTED_ENTITY_COUNTS = {
    "requirement": 437,
    "provision": 341,
    "schedule_entry": 96,
    "table": 10,
    "amendment": 76,
}
TOTAL_EXPECTED_ENTITIES = 960


def preflight_check(url: str, key: str, api_key: str) -> bool:
    """Run all mandatory pre-flight checks before starting generation."""
    print("=" * 60)
    print("PHASE 4D: PRE-FLIGHT VERIFICATION")
    print("=" * 60)

    # 1. Verify credentials
    if not url or not key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_KEY.")
        return False
    if not api_key:
        print("ERROR: Missing GEMINI_API_KEY in backend/.env.")
        return False
    print("1. Credentials: SUPABASE and GEMINI API keys present.")

    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Range": "0-0", "Prefer": "count=exact"}

    # 2. Verify legal corpus counts
    print("2. Verifying legal corpus table row counts against locked baseline...")
    for tbl, exp_count in EXPECTED_CORPUS_COUNTS.items():
        resp = requests.get(f"{url}/rest/v1/{tbl}?select=id", headers=headers, timeout=30)
        if not resp.ok:
            print(f"ERROR: Failed to query {tbl}: {resp.status_code}")
            return False
        cr = resp.headers.get("content-range", "")
        count = int(cr.split("/")[-1]) if "/" in cr else 0
        if count != exp_count:
            print(f"ERROR: {tbl} count mismatch: got {count}, expected {exp_count}")
            return False
        print(f"   - {tbl}: {count} (MATCH)")

    # 3. Verify legacy legal_rules
    resp = requests.get(f"{url}/rest/v1/legal_rules?select=id", headers=headers, timeout=30)
    cr = resp.headers.get("content-range", "")
    lr_count = int(cr.split("/")[-1]) if "/" in cr else 0
    if lr_count != 51:
        print(f"ERROR: legal_rules count mismatch: got {lr_count}, expected 51")
        return False
    print(f"3. Legacy legal_rules count: {lr_count} (MATCH)")

    # 4. Check current embedding coverage
    resp = requests.get(f"{url}/rest/v1/legal_corpus_embeddings?select=id", headers=headers, timeout=30)
    cr = resp.headers.get("content-range", "")
    lce_count = int(cr.split("/")[-1]) if "/" in cr else 0
    print(f"4. Current legal_corpus_embeddings: {lce_count} / {TOTAL_EXPECTED_ENTITIES}")

    # 5. Quick test of Gemini embedding API
    print("5. Testing Gemini embedding API response (gemini-embedding-001, 3072 dims)...")
    test_client = GeminiEmbeddingClient(api_key=api_key)
    test_vec = test_client.embed_text("Legal Metrology Pre-Flight Test", task_type="RETRIEVAL_DOCUMENT")
    if len(test_vec) != 3072:
        print(f"ERROR: Gemini embedding returned {len(test_vec)} dims, expected 3072.")
        return False
    print("   - Gemini embedding API operational (3072 dims verified).")

    print("\nPRE-FLIGHT CHECKS PASSED SUCCESSFULLY.\n")
    return True


def fetch_all_entities(url: str, key: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch all 960 legal entities from Supabase PostgREST tables."""
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    entities = {}

    tables = {
        "requirements": "legal_requirements",
        "provisions": "legal_provisions",
        "schedule_entries": "legal_schedule_entries",
        "tables": "legal_tables",
        "amendments": "legal_amendments",
    }

    print("Fetching authoritative legal entities from Supabase...")
    for key_name, table_name in tables.items():
        resp = requests.get(f"{url}/rest/v1/{table_name}?select=*&limit=1000", headers=headers, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"Failed to fetch {table_name}: {resp.status_code}")
        data = resp.json()
        entities[key_name] = data
        print(f"  - Fetched {len(data)} {key_name}")

    total_fetched = sum(len(v) for v in entities.values())
    if total_fetched != TOTAL_EXPECTED_ENTITIES:
        raise RuntimeError(f"Total entities fetched {total_fetched} != expected {TOTAL_EXPECTED_ENTITIES}")

    return entities


def run_embedding_generation(
    url: str,
    key: str,
    api_key: str,
    batch_size: int = 20,
    inter_batch_delay: float = 4.0,
) -> dict[str, Any]:
    """Run real embedding generation with batching and idempotency."""
    client = GeminiEmbeddingClient(api_key=api_key, max_retries=6, base_retry_delay=5.0)
    store = SupabaseEmbeddingStore(url=url, key=key)
    generator = LegalEmbeddingGenerator(
        client=client,
        store=store,
        text_version="v1",
        batch_size=batch_size,
        inter_batch_delay=inter_batch_delay,
    )

    entities = fetch_all_entities(url, key)

    print(f"\nStarting batch embedding generation (batch_size={batch_size})...")
    start_time = time.perf_counter()

    batch_result = generator.generate_all(
        requirements=entities["requirements"],
        provisions=entities["provisions"],
        schedule_entries=entities["schedule_entries"],
        tables=entities["tables"],
        amendments=entities["amendments"],
        skip_existing_hashes=True,
    )

    elapsed_sec = time.perf_counter() - start_time
    print(f"\nGeneration completed in {elapsed_sec:.2f}s ({elapsed_sec / 60:.2f} min).")
    print(f"Total processed: {batch_result.total_processed}")
    print(f"Successful / up to date: {batch_result.successful}")
    print(f"Failed: {batch_result.failed}")
    print("Entity breakdown:", batch_result.entity_counts)

    if batch_result.errors:
        print("ERRORS encountered:")
        for err in batch_result.errors[:5]:
            print(f"  - {err}")

    return {
        "batch_result": batch_result,
        "elapsed_sec": elapsed_sec,
    }


def post_generation_audit(url: str, key: str) -> bool:
    """Verify exact counts, integrity, zero duplicates, and vector dimensions."""
    print("\n" + "=" * 60)
    print("POST-GENERATION AUDIT & INTEGRITY VERIFICATION")
    print("=" * 60)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    # 1. Exact entity counts
    print("1. Auditing row counts in public.legal_corpus_embeddings by entity_type...")
    for etype, exp_count in EXPECTED_ENTITY_COUNTS.items():
        resp = requests.get(
            f"{url}/rest/v1/legal_corpus_embeddings?select=id&entity_type=eq.{etype}",
            headers={**headers, "Range": "0-0", "Prefer": "count=exact"},
            timeout=30,
        )
        cr = resp.headers.get("content-range", "")
        count = int(cr.split("/")[-1]) if "/" in cr else 0
        if count != exp_count:
            print(f"ERROR: {etype} count mismatch: got {count}, expected {exp_count}")
            return False
        print(f"   - {etype}: {count} / {exp_count} (100% COVERAGE)")

    # Total count
    resp = requests.get(
        f"{url}/rest/v1/legal_corpus_embeddings?select=id",
        headers={**headers, "Range": "0-0", "Prefer": "count=exact"},
        timeout=30,
    )
    cr = resp.headers.get("content-range", "")
    total_count = int(cr.split("/")[-1]) if "/" in cr else 0
    if total_count != TOTAL_EXPECTED_ENTITIES:
        print(f"ERROR: Total embedding count mismatch: got {total_count}, expected {TOTAL_EXPECTED_ENTITIES}")
        return False
    print(f"\nTotal legal_corpus_embeddings in database: {total_count} / {TOTAL_EXPECTED_ENTITIES} (100.0%)")

    # 2. Check for duplicate entity identities
    print("2. Checking for duplicate (entity_type, entity_id, model, embedding_text_version)...")
    # Fetch all records with paging
    all_records: list[dict[str, Any]] = []
    page_size = 500
    offset = 0
    while True:
        resp = requests.get(
            f"{url}/rest/v1/legal_corpus_embeddings?select=entity_type,entity_id,embedding_text_hash,embedding_text&offset={offset}&limit={page_size}",
            headers=headers,
            timeout=60,
        )
        if not resp.ok:
            print(f"ERROR: Failed to fetch embeddings for audit: {resp.status_code}")
            return False
        data = resp.json()
        if not data:
            break
        all_records.extend(data)
        if len(data) < page_size:
            break
        offset += page_size

    identities = set()
    duplicates = []
    for r in all_records:
        ident = (r["entity_type"], r["entity_id"])
        if ident in identities:
            duplicates.append(ident)
        identities.add(ident)

    if duplicates:
        print(f"ERROR: Found {len(duplicates)} duplicate identities: {duplicates[:5]}")
        return False
    print(f"   - Duplicate identities: 0 (PASSED, {len(identities)} unique entities)")

    # 3. Text-hash integrity
    print("3. Verifying SHA-256 text-hash integrity across all stored embeddings...")
    hash_mismatches = []
    for r in all_records:
        calc_hash = compute_embedding_text_hash(r["embedding_text"])
        if calc_hash != r["embedding_text_hash"]:
            hash_mismatches.append(r["entity_id"])

    if hash_mismatches:
        print(f"ERROR: Found {len(hash_mismatches)} hash mismatches: {hash_mismatches[:5]}")
        return False
    print(f"   - Hash integrity: 100% matched ({len(all_records)} / {len(all_records)})")

    # 4. Vector dimension check on sample rows
    print("4. Validating vector dimensionality (3072 dims)...")
    resp = requests.get(
        f"{url}/rest/v1/legal_corpus_embeddings?select=entity_id,entity_type,dimension,embedding&limit=5",
        headers=headers,
        timeout=60,
    )
    if resp.ok:
        sample_rows = resp.json()
        for s in sample_rows:
            emb_str = s.get("embedding", "")
            # If returned as string representation '[0.1, ...]' or list
            if isinstance(emb_str, str):
                vec = json.loads(emb_str)
            else:
                vec = emb_str
            if len(vec) != 3072:
                print(f"ERROR: Vector dimension mismatch on {s['entity_id']}: got {len(vec)}")
                return False
        print(f"   - Vector dimension validated on sample: exactly 3072 dimensions.")

    print("\nALL POST-GENERATION AUDIT CHECKS PASSED (100% COVERAGE & INTEGRITY).\n")
    return True


if __name__ == "__main__":
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not preflight_check(supabase_url, supabase_key, gemini_key):
        sys.exit(1)

    gen_stats = run_embedding_generation(supabase_url, supabase_key, gemini_key, batch_size=20)

    if not post_generation_audit(supabase_url, supabase_key):
        sys.exit(1)

    print("Phase 4D embedding generation and audit successfully finished.")
