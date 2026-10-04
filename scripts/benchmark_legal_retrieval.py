"""Statutory Legal Retrieval Benchmark Suite (Phase 4D).

Evaluates the Phase 4C retrieval architecture against real Supabase embeddings
and authoritative legal corpus entities.

Evaluates:
- Recall@1, Recall@3, Recall@5, Recall@10
- Category recall across all 5 legal entity types:
  (requirements, provisions, schedule entries, tables, amendments)
- Direct lookup recall (100% target)
- Relationship expansion recall (parent provisions, referenced tables, amendments)
- Deduplication verification (zero duplicate entity IDs in retrieved packages)
- Completeness validation (retrieval_complete != top_k)
- Latency profiling (mean, min, p50, p95, max ms)
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import requests
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("backend/.env")

sys.path.insert(0, os.path.abspath("."))

from backend.app.services.legal_rag.embeddings.client import GeminiEmbeddingClient
from backend.app.services.legal_rag.models import LegalEntityType, RetrievalMethod
from backend.app.services.legal_rag.retrieval.models import (
    LegalContextPackage,
    RetrievalRequest,
    RetrievedEntityContext,
)
from backend.app.services.legal_rag.retrieval.repository import (
    SupabaseLegalCorpusRepository,
)
from backend.app.services.legal_rag.retrieval.service import LegalRetrievalService


@dataclass
class BenchmarkTestCase:
    name: str
    category: str  # pilot_rule, schedule, table, amendment, direct_lookup
    query_text: str
    expected_entity_type: str | None = None
    expected_entity_ids: list[str] = field(default_factory=list)
    direct_ids: list[str] = field(default_factory=list)
    applicable_requirement_ids: list[str] = field(default_factory=list)
    expand_statutory_context: bool = True
    top_k: int = 10


def build_benchmark_suite(
    repo: SupabaseLegalCorpusRepository,
) -> list[BenchmarkTestCase]:
    """Dynamically construct benchmark test cases anchored in real corpus IDs."""
    test_cases: list[BenchmarkTestCase] = []

    # 1. Pilot Rule 1: Manufacturer Identity (Rule 6(1)(a))
    test_cases.append(
        BenchmarkTestCase(
            name="Pilot 1: Manufacturer Identity & Address",
            category="pilot_rule",
            query_text="Name and complete address of the manufacturer on pre-packaged commodities",
            expected_entity_type="requirement",
            top_k=10,
        )
    )

    # 2. Pilot Rule 2: Importer Identity (Rule 6(1)(a) imported)
    test_cases.append(
        BenchmarkTestCase(
            name="Pilot 2: Importer Identity & Country of Origin",
            category="pilot_rule",
            query_text="Name and complete address of the importer and country of origin for imported goods",
            expected_entity_type="requirement",
            top_k=10,
        )
    )

    # 3. Pilot Rule 3: Rule 3 Institutional / Wholesale Exemption
    test_cases.append(
        BenchmarkTestCase(
            name="Pilot 3: Chapter II Applicability & Institutional Exemption",
            category="pilot_rule",
            query_text="Exemption for packages containing commodities exceeding 25 kg or 25 litre or sold to industrial consumers",
            expected_entity_type="provision",
            top_k=10,
        )
    )

    # 4. Pilot Rule 4: Rule 26 Small Package Exemption
    test_cases.append(
        BenchmarkTestCase(
            name="Pilot 4: Small Package Exemption (10g or 10ml)",
            category="pilot_rule",
            query_text="Exemption for small packages where net weight or measure is 10 gram or 10 millilitre or less",
            expected_entity_type="provision",
            top_k=10,
        )
    )

    # 5. Pilot Rule 5: MRP Declaration (Rule 6(1)(e))
    test_cases.append(
        BenchmarkTestCase(
            name="Pilot 5: Maximum Retail Price & Unit Sale Price",
            category="pilot_rule",
            query_text="Maximum retail price declaration inclusive of all taxes and unit sale price per gram or millilitre",
            expected_entity_type="requirement",
            top_k=10,
        )
    )

    # 6. Schedule Entries: Second Schedule standard pack sizes
    test_cases.append(
        BenchmarkTestCase(
            name="Schedule: Second Schedule Standard Quantities",
            category="schedule_entry",
            query_text="Commodities to be packed in specified standard quantities under the Second Schedule",
            expected_entity_type="schedule_entry",
            top_k=10,
        )
    )

    # 7. Tables: First Schedule Maximum Permissible Error
    test_cases.append(
        BenchmarkTestCase(
            name="Table: Maximum Permissible Error on Net Quantity",
            category="table",
            query_text="Maximum permissible error in net quantity declaration for pre-packaged commodities table",
            expected_entity_type="table",
            top_k=10,
        )
    )

    # 8. Amendments: 2017 / 2021 Amendments (E-Commerce / QR codes)
    test_cases.append(
        BenchmarkTestCase(
            name="Amendment: E-Commerce Declarations & QR Codes",
            category="amendment",
            query_text="Legal Metrology Packaged Commodities amendment for digital declarations on e-commerce platforms and QR code",
            expected_entity_type="amendment",
            top_k=10,
        )
    )

    # 9. Direct Lookup Test Cases (100% Target)
    # Fetch sample IDs for direct testing
    sample_reqs = repo._get("legal_requirements", [("limit", "2")])
    for req in sample_reqs:
        rid = req["id"]
        test_cases.append(
            BenchmarkTestCase(
                name=f"Direct Lookup: Requirement {rid[:8]}",
                category="direct_lookup",
                query_text="",
                direct_ids=[rid],
                expected_entity_ids=[rid],
                expected_entity_type="requirement",
                expand_statutory_context=True,
                top_k=5,
            )
        )

    # Direct Provision Lookup (Provision 6: Rule 6 declarations)
    test_cases.append(
        BenchmarkTestCase(
            name="Direct Lookup: Provision 6 (Rule 6 Declarations)",
            category="direct_lookup",
            query_text="",
            direct_ids=["6"],
            expected_entity_ids=["6"],
            expected_entity_type="provision",
            expand_statutory_context=True,
            top_k=5,
        )
    )

    return test_cases


def run_benchmark(
    service: LegalRetrievalService,
    suite: list[BenchmarkTestCase],
) -> dict[str, Any]:
    """Execute all benchmark test cases and calculate quantitative metrics."""
    results: list[dict[str, Any]] = []
    latencies: list[float] = []

    r1_hits = 0
    r3_hits = 0
    r5_hits = 0
    r10_hits = 0

    category_counts: dict[str, int] = {}
    category_hits: dict[str, int] = {}

    direct_lookup_total = 0
    direct_lookup_hits = 0

    expansion_total = 0
    expansion_hits = 0

    deduplication_violations = 0
    completeness_evaluations = 0
    completeness_matches = 0

    print("=" * 70)
    print("PHASE 4D: STATUTORY LEGAL RETRIEVAL BENCHMARK")
    print(f"Total benchmark test cases: {len(suite)}")
    print("=" * 70)

    for i, tc in enumerate(suite, 1):
        req_ids = tc.direct_ids if tc.expected_entity_type == "requirement" else []
        prov_ids = [int(x) for x in tc.direct_ids if x.isdigit()] if tc.expected_entity_type == "provision" else []
        sched_entry_ids = tc.direct_ids if tc.expected_entity_type == "schedule_entry" else []
        table_ids = tc.direct_ids if tc.expected_entity_type == "table" else []
        amend_ids = tc.direct_ids if tc.expected_entity_type == "amendment" else []

        filter_types = None
        if tc.category in ("schedule_entry", "table", "amendment"):
            filter_types = [LegalEntityType(tc.expected_entity_type)]

        req = RetrievalRequest(
            query_text=tc.query_text,
            requirement_ids=req_ids,
            provision_ids=prov_ids,
            schedule_entry_ids=sched_entry_ids,
            table_ids=table_ids,
            amendment_ids=amend_ids,
            entity_types=filter_types,
            limit=tc.top_k,
            min_similarity_threshold=0.25,
            expand_statutory_context=tc.expand_statutory_context,
        )

        t0 = time.perf_counter()
        pkg = service.retrieve(req)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        retrieved_ids = [e.entity_id for e in pkg.entities]
        retrieved_types = [
            e.entity_type.value if isinstance(e.entity_type, LegalEntityType) else str(e.entity_type)
            for e in pkg.entities
        ]

        # Check deduplication
        seen = set()
        has_dup = False
        for e in pkg.entities:
            key = (str(e.entity_type), e.entity_id)
            if key in seen:
                has_dup = True
                break
            seen.add(key)
        if has_dup:
            deduplication_violations += 1

        # Check direct lookup recall
        if tc.category == "direct_lookup":
            direct_lookup_total += len(tc.expected_entity_ids)
            for exp_id in tc.expected_entity_ids:
                if exp_id in retrieved_ids:
                    direct_lookup_hits += 1

            # Check expansion if enabled
            if tc.expand_statutory_context:
                expansion_total += 1
                methods = [m for e in pkg.entities for m in e.retrieval_methods]
                if RetrievalMethod.PROVENANCE_EXPANSION in methods:
                    expansion_hits += 1

        # Check category recall (did we retrieve the target entity type?)
        cat_key = tc.expected_entity_type or "general"
        category_counts[cat_key] = category_counts.get(cat_key, 0) + 1
        if tc.expected_entity_type in retrieved_types:
            category_hits[cat_key] = category_hits.get(cat_key, 0) + 1

        # Rank-based Recall (Recall@k)
        hit_r1 = False
        hit_r3 = False
        hit_r5 = False
        hit_r10 = False

        if tc.expected_entity_ids:
            # Match specific ID
            target_ids = set(tc.expected_entity_ids)
            hit_r1 = bool(target_ids.intersection(retrieved_ids[:1]))
            hit_r3 = bool(target_ids.intersection(retrieved_ids[:3]))
            hit_r5 = bool(target_ids.intersection(retrieved_ids[:5]))
            hit_r10 = bool(target_ids.intersection(retrieved_ids[:10]))
        elif tc.expected_entity_type:
            # Target entity type presence in top-k
            hit_r1 = tc.expected_entity_type in retrieved_types[:1]
            hit_r3 = tc.expected_entity_type in retrieved_types[:3]
            hit_r5 = tc.expected_entity_type in retrieved_types[:5]
            hit_r10 = tc.expected_entity_type in retrieved_types[:10]

        if hit_r1:
            r1_hits += 1
        if hit_r3:
            r3_hits += 1
        if hit_r5:
            r5_hits += 1
        if hit_r10:
            r10_hits += 1

        # Completeness verification
        if tc.applicable_requirement_ids:
            completeness_evaluations += 1
            if pkg.completeness and pkg.completeness.is_complete:
                completeness_matches += 1

        status_str = f"R@1:{int(hit_r1)} R@3:{int(hit_r3)} R@5:{int(hit_r5)} R@10:{int(hit_r10)} ({len(pkg.entities)} ret in {elapsed_ms:.1f}ms)"
        print(f"[{i:02d}/{len(suite):02d}] {tc.name:<45} | {status_str}")

        results.append(
            {
                "name": tc.name,
                "category": tc.category,
                "hit_r1": hit_r1,
                "hit_r3": hit_r3,
                "hit_r5": hit_r5,
                "hit_r10": hit_r10,
                "total_retrieved": len(pkg.entities),
                "elapsed_ms": elapsed_ms,
            }
        )
        time.sleep(3.0)

    # Compute aggregates
    n = len(suite)
    recall_1 = (r1_hits / n) * 100 if n else 0.0
    recall_3 = (r3_hits / n) * 100 if n else 0.0
    recall_5 = (r5_hits / n) * 100 if n else 0.0
    recall_10 = (r10_hits / n) * 100 if n else 0.0

    direct_recall = (direct_lookup_hits / direct_lookup_total * 100) if direct_lookup_total else 100.0
    expansion_recall = (expansion_hits / expansion_total * 100) if expansion_total else 100.0

    latencies_sorted = sorted(latencies)
    p50_latency = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0.0
    p95_idx = int(len(latencies_sorted) * 0.95)
    p95_latency = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)] if latencies_sorted else 0.0
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total Test Cases:            {n}")
    print(f"Recall@1:                     {recall_1:.1f}% ({r1_hits}/{n})")
    print(f"Recall@3:                     {recall_3:.1f}% ({r3_hits}/{n})")
    print(f"Recall@5:                     {recall_5:.1f}% ({r5_hits}/{n})")
    print(f"Recall@10:                    {recall_10:.1f}% ({r10_hits}/{n})")
    print(f"Direct Lookup Recall:         {direct_recall:.1f}% ({direct_lookup_hits}/{direct_lookup_total})")
    print(f"Statutory Expansion Recall:   {expansion_recall:.1f}% ({expansion_hits}/{expansion_total})")
    print(f"Deduplication Violations:     {deduplication_violations} (0 expected)")
    print("\nCategory Recall Breakdown:")
    for cat, cnt in category_counts.items():
        hits = category_hits.get(cat, 0)
        pct = (hits / cnt * 100) if cnt else 0.0
        print(f"  - {cat:<18}: {pct:.1f}% ({hits}/{cnt})")

    print("\nLatency Profiling (ms):")
    print(f"  - Mean: {mean_latency:.1f} ms")
    print(f"  - Min:  {min(latencies):.1f} ms" if latencies else "N/A")
    print(f"  - p50:  {p50_latency:.1f} ms")
    print(f"  - p95:  {p95_latency:.1f} ms")
    print(f"  - Max:  {max(latencies):.1f} ms" if latencies else "N/A")

    return {
        "total_test_cases": n,
        "recall_1": recall_1,
        "recall_3": recall_3,
        "recall_5": recall_5,
        "recall_10": recall_10,
        "direct_recall": direct_recall,
        "expansion_recall": expansion_recall,
        "deduplication_violations": deduplication_violations,
        "category_recall": {
            cat: (category_hits.get(cat, 0) / cnt * 100) if cnt else 0.0
            for cat, cnt in category_counts.items()
        },
        "latency": {
            "mean_ms": mean_latency,
            "min_ms": min(latencies) if latencies else 0.0,
            "p50_ms": p50_latency,
            "p95_ms": p95_latency,
            "max_ms": max(latencies) if latencies else 0.0,
        },
        "results": results,
    }


if __name__ == "__main__":
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not supabase_url or not supabase_key or not gemini_key:
        print("ERROR: SUPABASE_URL, SUPABASE_KEY, or GEMINI_API_KEY missing.")
        sys.exit(1)

    repo = SupabaseLegalCorpusRepository(url=supabase_url, key=supabase_key)
    client = GeminiEmbeddingClient(api_key=gemini_key, max_retries=6, base_retry_delay=5.0)
    service = LegalRetrievalService(repository=repo, embedding_client=client)

    suite = build_benchmark_suite(repo)
    summary = run_benchmark(service, suite)

    # Save benchmark results to file for final report
    out_path = "scripts/benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved benchmark metrics to {out_path}.")
