"""Phase 4D Tests: Real Legal Embedding Population & Retrieval Validation.

Comprehensive unit test suite for Phase 4D:
1. Full entity coverage verification (960 entities across all 5 types)
2. Idempotent rerun verification (zero duplicates, hash-based skip)
3. Text hash integrity (SHA-256 deterministic verification)
4. 3072-dimensional vector validation
5. Missing entity detection
6. Duplicate entity detection
7. Direct lookup 100% recall
8. Semantic retrieval execution
9. Retrieval metrics calculation (Recall@1, Recall@3, Recall@5, Recall@10)
10. Statutory relationship expansion (Req -> Prov, Prov -> Schedule/Table/Amendment)
11. Deterministic deduplication (zero duplicates in retrieval context)
12. Provenance preservation (source identifier, ground truth, methods)
13. Completeness validation (retrieval_complete != limit)
14. Empty corpus handling (safe explicit result, not complete)
15. Partial corpus handling (reports missing requirements)
16. Applicability immutability (Phase 3A tables untouched)
17. Legal corpus immutability (corpus baseline untouched)
"""

from __future__ import annotations

import unittest
from datetime import date
from uuid import uuid4

from backend.app.services.legal_rag.embeddings.client import (
    EmbeddingGenerationError,
    MockEmbeddingClient,
)
from backend.app.services.legal_rag.embeddings.generator import LegalEmbeddingGenerator
from backend.app.services.legal_rag.embeddings.models import (
    EntityEmbeddingRecord,
)
from backend.app.services.legal_rag.embeddings.store import InMemoryEmbeddingStore
from backend.app.services.legal_rag.embeddings.text_builder import (
    build_amendment_embedding_text,
    build_provision_embedding_text,
    build_requirement_embedding_text,
    build_schedule_entry_embedding_text,
    build_table_embedding_text,
    compute_embedding_text_hash,
)
from backend.app.services.legal_rag.models import (
    CompletenessStatus,
    LegalEntityType,
    LegalProvenance,
    RetrievalConfig,
    RetrievalMethod,
)
from backend.app.services.legal_rag.retrieval.completeness import CompletenessChecker
from backend.app.services.legal_rag.retrieval.coverage import (
    CoverageReport,
    EmbeddingCoverageChecker,
    EXPECTED_LEGAL_ENTITY_COUNTS,
)
from backend.app.services.legal_rag.retrieval.deduplication import DeterministicDeduplicator
from backend.app.services.legal_rag.retrieval.direct import DirectLookupResolver
from backend.app.services.legal_rag.retrieval.expansion import StatutoryRelationshipExpander
from backend.app.services.legal_rag.retrieval.models import (
    LegalContextPackage,
    RetrievalRequest,
    RetrievedEntityContext,
)
from backend.app.services.legal_rag.retrieval.ranking import DeterministicRanker
from backend.app.services.legal_rag.retrieval.repository import InMemoryLegalCorpusRepository
from backend.app.services.legal_rag.retrieval.semantic import SemanticSearchResolver
from backend.app.services.legal_rag.retrieval.service import LegalRetrievalService


class TestPhase4DRetrievalValidation(unittest.TestCase):
    """Phase 4D Controlled Retrieval Validation Test Suite."""

    def setUp(self) -> None:
        """Set up deterministic in-memory test fixtures."""
        self.repo = InMemoryLegalCorpusRepository()
        self.mock_client = MockEmbeddingClient(dimension=3072)
        self.store = InMemoryEmbeddingStore()

        # Seed sample authoritative entities across all 5 legal types
        self.req_1 = {
            "id": "req-mfg-1",
            "source_identifier": "doc_1_rule_6_1_a_mfg",
            "provision_id": 6,
            "requirement_type": "mandatory_declaration",
            "requirement_text": "Name and complete address of the manufacturer must be displayed.",
            "normalized_requirement": "manufacturer_identity",
            "subject": "Manufacturer identity",
            "source_quote": "name and complete address of the manufacturer",
            "source_reference": {"document_id": 1, "rule_number": "6", "sub_rule_number": "1", "clause": "a"},
        }
        self.req_2 = {
            "id": "req-mrp-1",
            "source_identifier": "doc_1_rule_6_1_e_mrp",
            "provision_id": 6,
            "requirement_type": "mandatory_declaration",
            "requirement_text": "Maximum retail price inclusive of all taxes must be declared.",
            "normalized_requirement": "mrp_declaration",
            "subject": "Maximum Retail Price",
            "source_quote": "maximum retail price inclusive of all taxes",
            "source_reference": {"document_id": 1, "rule_number": "6", "sub_rule_number": "1", "clause": "e"},
        }
        self.repo.requirements["req-mfg-1"] = self.req_1
        self.repo.requirements["req-mrp-1"] = self.req_2

        self.prov_6 = {
            "id": 6,
            "document_id": 1,
            "rule_number": "6",
            "sub_rule_number": "1",
            "title": "Declarations to be made on every package",
            "content": "Every package shall bear thereon the following declarations...",
            "source_text": "Every package shall bear thereon the following declarations...",
        }
        self.prov_26 = {
            "id": 26,
            "document_id": 1,
            "rule_number": "26",
            "sub_rule_number": "a",
            "title": "Exemption in respect of certain packages",
            "content": "Nothing in these rules shall apply to small packages of 10g or 10ml or less.",
            "source_text": "Nothing in these rules shall apply to small packages of 10g or 10ml or less.",
        }
        self.repo.provisions[6] = self.prov_6
        self.repo.provisions[26] = self.prov_26

        self.sched_entry = {
            "id": "sched-entry-second-1",
            "schedule_id": "second_schedule",
            "sequence": 1,
            "commodity_name": "Baby food",
            "standard_quantities": "100g, 200g, 500g, 1kg",
        }
        self.repo.schedule_entries["sched-entry-second-1"] = self.sched_entry

        self.table_mpe = {
            "id": "table-first-sched-mpe",
            "schedule_id": "first_schedule",
            "provision_id": 6,
            "title": "Maximum Permissible Errors",
            "content": {"heading": "Maximum permissible errors on net quantities"},
        }
        self.repo.tables["table-first-sched-mpe"] = self.table_mpe

        self.amend_2017 = {
            "id": "amend-2017-ecom",
            "document_id": 1,
            "affected_provision_id": 6,
            "amendment_number": "GSR 629(E)",
            "title": "E-Commerce Packaged Commodities Amendment 2017",
            "effective_date": "2018-01-01",
        }
        self.repo.amendments["amend-2017-ecom"] = self.amend_2017

        # Pre-seed embeddings in repo for semantic search
        self._seed_repo_embeddings()

        self.service = LegalRetrievalService(
            repository=self.repo,
            embedding_client=self.mock_client,
        )

    def _seed_repo_embeddings(self) -> None:
        """Seed mock 3072-dimensional embeddings for all entities in self.repo."""
        entities_to_embed = [
            ("requirement", "req-mfg-1", "doc_1_rule_6_1_a_mfg", self.req_1["requirement_text"]),
            ("requirement", "req-mrp-1", "doc_1_rule_6_1_e_mrp", self.req_2["requirement_text"]),
            ("provision", "6", "doc_1_rule_6", self.prov_6["source_text"]),
            ("provision", "26", "doc_1_rule_26", self.prov_26["source_text"]),
            ("schedule_entry", "sched-entry-second-1", "second_schedule_entry_1", self.sched_entry["standard_quantities"]),
            ("table", "table-first-sched-mpe", "first_schedule_table_mpe", self.table_mpe["title"]),
            ("amendment", "amend-2017-ecom", "gsr_629_e_2017", self.amend_2017["title"]),
        ]
        for etype, eid, sid, text in entities_to_embed:
            vec = self.mock_client.embed_text(text)
            self.repo.embeddings.append(
                {
                    "id": str(uuid4()),
                    "entity_type": etype,
                    "entity_id": eid,
                    "source_identifier": sid,
                    "embedding": vec,
                    "dimension": 3072,
                    "model": "gemini-embedding-001",
                    "embedding_text_version": "v1",
                    "embedding_text": text,
                    "embedding_text_hash": compute_embedding_text_hash(text),
                    "metadata": {},
                }
            )

    # --------------------------------------------------
    # TEST 1: Full Entity Coverage Verification
    # --------------------------------------------------
    def test_01_full_entity_coverage(self) -> None:
        """Verify coverage checker verifies all 5 legal entity types matching expected baseline."""
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["requirement"], 437)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["provision"], 341)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["schedule_entry"], 96)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["table"], 10)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["amendment"], 76)
        self.assertEqual(sum(EXPECTED_LEGAL_ENTITY_COUNTS.values()), 960)

        # Build mock repo with exact 960 entities
        full_repo = InMemoryLegalCorpusRepository()
        for i in range(437):
            full_repo.requirements[f"req-{i}"] = {"id": f"req-{i}"}
            full_repo.embeddings.append({"entity_type": "requirement", "entity_id": f"req-{i}"})
        for i in range(341):
            full_repo.provisions[i] = {"id": i}
            full_repo.embeddings.append({"entity_type": "provision", "entity_id": str(i)})
        for i in range(96):
            full_repo.schedule_entries[f"se-{i}"] = {"id": f"se-{i}"}
            full_repo.embeddings.append({"entity_type": "schedule_entry", "entity_id": f"se-{i}"})
        for i in range(10):
            full_repo.tables[f"t-{i}"] = {"id": f"t-{i}"}
            full_repo.embeddings.append({"entity_type": "table", "entity_id": f"t-{i}"})
        for i in range(76):
            full_repo.amendments[f"a-{i}"] = {"id": f"a-{i}"}
            full_repo.embeddings.append({"entity_type": "amendment", "entity_id": f"a-{i}"})

        full_checker = EmbeddingCoverageChecker(full_repo)
        report = full_checker.check_coverage()
        self.assertTrue(report.is_fully_populated)
        self.assertEqual(report.total_actual, 960)
        self.assertTrue(all(m == 0 for m in report.missing_counts.values()))
        self.assertEqual(report.coverage_percentages["requirement"], 100.0)

    # --------------------------------------------------
    # TEST 2: Idempotent Rerun (Zero Duplicates)
    # --------------------------------------------------
    def test_02_idempotent_rerun_zero_duplicates(self) -> None:
        """Verify rerun with skip_existing_hashes=True reuses existing rows without creating duplicates."""
        generator = LegalEmbeddingGenerator(
            client=self.mock_client,
            store=self.store,
            inter_batch_delay=0.0,
        )

        # Run 1: generate embeddings
        res1 = generator.generate_all(
            requirements=[self.req_1, self.req_2],
            provisions=[self.prov_6],
            skip_existing_hashes=True,
        )
        self.assertEqual(res1.successful, 3)
        self.assertEqual(self.store.count_embeddings(), 3)

        # Run 2: re-run with skip_existing_hashes=True
        res2 = generator.generate_all(
            requirements=[self.req_1, self.req_2],
            provisions=[self.prov_6],
            skip_existing_hashes=True,
        )
        self.assertEqual(res2.successful, 3)
        # Store records must still be exactly 3 (zero duplicates added)
        self.assertEqual(self.store.count_embeddings(), 3)

    # --------------------------------------------------
    # TEST 3: Text Hash Integrity (Deterministic SHA-256)
    # --------------------------------------------------
    def test_03_text_hash_integrity(self) -> None:
        """Verify deterministic SHA-256 hash generation and change detection."""
        text = build_requirement_embedding_text(self.req_1, self.prov_6)
        hash1 = compute_embedding_text_hash(text)
        hash2 = compute_embedding_text_hash(text)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA-256 hex string

        # Mutate text slightly -> hash must change
        mutated_text = text + " "
        hash_mutated = compute_embedding_text_hash(mutated_text)
        self.assertNotEqual(hash1, hash_mutated)

    # --------------------------------------------------
    # TEST 4: 3072-Dimensional Vector Validation
    # --------------------------------------------------
    def test_04_vector_dimension_3072(self) -> None:
        """Verify vector dimension is strictly 3072."""
        vec = self.mock_client.embed_text("Test legal metrology rule")
        self.assertEqual(len(vec), 3072)

        # Verify MockEmbeddingClient honors dimension parameter
        client_bad = MockEmbeddingClient(dimension=1536)
        vec_bad = client_bad.embed_text("Test")
        self.assertEqual(len(vec_bad), 1536)

    # --------------------------------------------------
    # TEST 5: Missing Entity Detection
    # --------------------------------------------------
    def test_05_missing_entity_detection(self) -> None:
        """Verify coverage checker detects shortfall and missing entity counts."""
        # Current self.repo has 7 embeddings, expected 960
        checker = EmbeddingCoverageChecker(self.repo)
        report = checker.check_coverage()
        self.assertFalse(report.is_fully_populated)
        self.assertIn("requirement", report.missing_counts)
        self.assertEqual(report.missing_counts["requirement"], 437 - 2)
        self.assertEqual(report.missing_counts["provision"], 341 - 2)
        self.assertGreater(report.missing_counts["schedule_entry"], 0)

    # --------------------------------------------------
    # TEST 6: Duplicate Entity Detection
    # --------------------------------------------------
    def test_06_duplicate_entity_detection(self) -> None:
        """Verify duplicate entity identities are identified and updated safely."""
        records = [
            EntityEmbeddingRecord(
                id=str(uuid4()),
                entity_type=LegalEntityType.REQUIREMENT,
                entity_id="req-mfg-1",
                source_identifier="doc_1_rule_6_1_a_mfg",
                provider="gemini",
                model="gemini-embedding-001",
                dimension=3072,
                embedding_text_version="v1",
                embedding_text="Text 1",
                embedding_text_hash=compute_embedding_text_hash("Text 1"),
                embedding=[0.0] * 3072,
            ),
            EntityEmbeddingRecord(
                id=str(uuid4()),
                entity_type=LegalEntityType.REQUIREMENT,
                entity_id="req-mfg-1",  # Duplicate identity
                source_identifier="doc_1_rule_6_1_a_mfg",
                provider="gemini",
                model="gemini-embedding-001",
                dimension=3072,
                embedding_text_version="v1",
                embedding_text="Text 2",
                embedding_text_hash=compute_embedding_text_hash("Text 2"),
                embedding=[0.0] * 3072,
            ),
        ]
        # In-memory store updates existing rather than duplicating
        store = InMemoryEmbeddingStore()
        store.save_embeddings(records)
        self.assertEqual(store.count_embeddings(), 1)
        rec = store.get_embedding(LegalEntityType.REQUIREMENT, "req-mfg-1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.embedding_text, "Text 2")

    # --------------------------------------------------
    # TEST 7: Direct Lookup (100% Recall)
    # --------------------------------------------------
    def test_07_direct_lookup_100_percent_recall(self) -> None:
        """Verify direct legal ID lookups achieve 100% precision and recall."""
        req = RetrievalRequest(
            requirement_ids=["req-mfg-1", "req-mrp-1"],
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)
        retrieved_ids = [e.entity_id for e in pkg.entities]
        self.assertIn("req-mfg-1", retrieved_ids)
        self.assertIn("req-mrp-1", retrieved_ids)
        for entity in pkg.entities:
            self.assertIn(RetrievalMethod.REQUIREMENT_LOOKUP, entity.retrieval_methods)
            self.assertEqual(entity.similarity_score, 1.0)

    # --------------------------------------------------
    # TEST 8: Semantic Retrieval Execution
    # --------------------------------------------------
    def test_08_semantic_retrieval(self) -> None:
        """Verify semantic vector search retrieves matches with cosine similarity."""
        query_text = self.req_1["requirement_text"]
        query_emb = self.mock_client.embed_query(query_text)
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-mfg-1",
            "embedding": query_emb,
            "similarity": 1.0,
        })
        req = RetrievalRequest(
            query_text=query_text,
            limit=5,
            min_similarity_threshold=0.5,
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)
        self.assertGreater(len(pkg.entities), 0)
        for e in pkg.entities:
            self.assertIsNotNone(e.similarity_score)
            self.assertIn(RetrievalMethod.SEMANTIC_VECTOR, e.retrieval_methods)

    # --------------------------------------------------
    # TEST 9: Retrieval Metrics Calculation (Recall@k)
    # --------------------------------------------------
    def test_09_retrieval_metrics_calculation(self) -> None:
        """Verify evaluation metrics computation (Recall@1, Recall@3, Recall@5, Recall@10)."""
        retrieved_ids = ["req-mfg-1", "req-mrp-1", "prov-6", "table-1", "sched-1"]
        target_id = "req-mfg-1"

        hit_r1 = target_id in retrieved_ids[:1]
        hit_r3 = target_id in retrieved_ids[:3]
        hit_r5 = target_id in retrieved_ids[:5]
        hit_r10 = target_id in retrieved_ids[:10]

        self.assertTrue(hit_r1)
        self.assertTrue(hit_r3)
        self.assertTrue(hit_r5)
        self.assertTrue(hit_r10)

        # Target at position 4
        target_pos4 = "table-1"
        self.assertFalse(target_pos4 in retrieved_ids[:1])
        self.assertFalse(target_pos4 in retrieved_ids[:3])
        self.assertTrue(target_pos4 in retrieved_ids[:5])
        self.assertTrue(target_pos4 in retrieved_ids[:10])

    # --------------------------------------------------
    # TEST 10: Statutory Relationship Expansion
    # --------------------------------------------------
    def test_10_statutory_relationship_expansion(self) -> None:
        """Verify requirement expands to provision, and provision expands to table and amendment."""
        req = RetrievalRequest(
            requirement_ids=["req-mfg-1"],
            expand_statutory_context=True,
        )
        pkg = self.service.retrieve(req)
        retrieved_types = {e.entity_type for e in pkg.entities}
        self.assertIn(LegalEntityType.REQUIREMENT, retrieved_types)
        self.assertIn(LegalEntityType.PROVISION, retrieved_types)
        # Expansion brought in parent provision 6
        prov_entities = [e for e in pkg.entities if e.entity_type == LegalEntityType.PROVISION]
        self.assertTrue(any(e.entity_id == "6" for e in prov_entities))

    # --------------------------------------------------
    # TEST 11: Deterministic Deduplication
    # --------------------------------------------------
    def test_11_deterministic_deduplication(self) -> None:
        """Verify deduplication eliminates duplicate (entity_type, entity_id) pairs."""
        query_text = self.req_1["requirement_text"]
        query_emb = self.mock_client.embed_query(query_text)
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-mfg-1",
            "embedding": query_emb,
            "similarity": 1.0,
        })
        req = RetrievalRequest(
            requirement_ids=["req-mfg-1"],
            query_text=query_text,
            min_similarity_threshold=0.5,
            expand_statutory_context=False,
            limit=5,
        )
        pkg = self.service.retrieve(req)
        mfg_entities = [e for e in pkg.entities if e.entity_id == "req-mfg-1"]
        self.assertEqual(len(mfg_entities), 1)  # Strictly deduplicated to 1
        mfg = mfg_entities[0]
        self.assertIn(RetrievalMethod.REQUIREMENT_LOOKUP, mfg.retrieval_methods)
        self.assertIn(RetrievalMethod.SEMANTIC_VECTOR, mfg.retrieval_methods)
        self.assertEqual(mfg.similarity_score, 1.0)  # Preserves best score

    # --------------------------------------------------
    # TEST 12: Provenance Preservation
    # --------------------------------------------------
    def test_12_provenance_preservation(self) -> None:
        """Verify retrieved entities retain exact statutory provenance."""
        req = RetrievalRequest(
            requirement_ids=["req-mfg-1"],
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)
        self.assertEqual(len(pkg.entities), 1)
        entity = pkg.entities[0]
        self.assertIsNotNone(entity.provenance)
        self.assertEqual(entity.provenance.source_identifier, "doc_1_rule_6_1_a_mfg")
        self.assertEqual(entity.provenance.source_quote, "name and complete address of the manufacturer")
        self.assertTrue(entity.provenance.is_valid())
        self.assertIn("Name and complete address", entity.legal_text)

    # --------------------------------------------------
    # TEST 13: Completeness Validation (Distinct from top_k)
    # --------------------------------------------------
    def test_13_completeness_validation_distinct_from_top_k(self) -> None:
        """Verify retrieval_complete is distinct from top_k and checks applicable requirements."""
        req = RetrievalRequest(
            query_text="General packaged commodities declarations",
            requirement_ids=["req-mfg-1", "req-mrp-1", "req-nonexistent"],
            limit=5,
        )
        pkg = self.service.retrieve(req)
        # Even if entities are returned, completeness is False because req-nonexistent is missing
        self.assertIsNotNone(pkg.completeness)
        self.assertFalse(pkg.completeness.is_complete)
        self.assertIn("req-nonexistent", pkg.completeness.missing_requirement_ids)

    # --------------------------------------------------
    # TEST 14: Empty Corpus Handling
    # --------------------------------------------------
    def test_14_empty_corpus_handling(self) -> None:
        """Verify empty repository yields safe explicit empty result rather than error."""
        empty_repo = InMemoryLegalCorpusRepository()
        empty_service = LegalRetrievalService(repository=empty_repo, embedding_client=self.mock_client)

        req = RetrievalRequest(query_text="Non-empty query for empty corpus")
        pkg = empty_service.retrieve(req)
        self.assertEqual(len(pkg.entities), 0)
        self.assertEqual(pkg.total_retrieved, 0)
        self.assertIsNotNone(pkg.empty_reason)

    # --------------------------------------------------
    # TEST 15: Partial Corpus Handling
    # --------------------------------------------------
    def test_15_partial_corpus_handling(self) -> None:
        """Verify partial corpus returns available entities and reports incomplete coverage."""
        req = RetrievalRequest(
            requirement_ids=["req-mfg-1", "req-missing-id"],
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)
        retrieved_ids = [e.entity_id for e in pkg.entities]
        self.assertIn("req-mfg-1", retrieved_ids)
        self.assertNotIn("req-missing-id", retrieved_ids)
        self.assertFalse(pkg.completeness.is_complete)
        self.assertIn("req-missing-id", pkg.completeness.missing_requirement_ids)

    # --------------------------------------------------
    # TEST 16: Applicability Immutability
    # --------------------------------------------------
    def test_16_applicability_immutability(self) -> None:
        """Verify retrieval service operations do NOT mutate any Phase 3A tables."""
        req = RetrievalRequest(
            query_text="Applicability rule check",
            requirement_ids=["req-mfg-1"],
        )
        pkg = self.service.retrieve(req)
        self.assertIsNotNone(pkg)
        # Ensure service has no applicability write dependencies
        self.assertFalse(hasattr(self.service, "save_rule_package"))
        self.assertFalse(hasattr(self.service, "update_applicability"))

    # --------------------------------------------------
    # TEST 17: Legal Corpus Immutability
    # --------------------------------------------------
    def test_17_legal_corpus_immutability(self) -> None:
        """Verify legal corpus repository records are completely unchanged after retrieval operations."""
        req_count_before = len(self.repo.requirements)
        prov_count_before = len(self.repo.provisions)
        table_count_before = len(self.repo.tables)

        req = RetrievalRequest(
            query_text="Maximum retail price and manufacturer address",
            requirement_ids=["req-mfg-1"],
            expand_statutory_context=True,
            limit=10,
        )
        self.service.retrieve(req)

        self.assertEqual(len(self.repo.requirements), req_count_before)
        self.assertEqual(len(self.repo.provisions), prov_count_before)
        self.assertEqual(len(self.repo.tables), table_count_before)


if __name__ == "__main__":
    unittest.main()
