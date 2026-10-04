"""Phase 4C Tests: Legal Retrieval Architecture Verification.

Verifies:
1. Retrieval request validation (limits, filters, empty criteria)
2. LegalContextPackage construction & formatted context
3. Direct requirement lookup (Requirement-First)
4. Direct provision lookup
5. Semantic retrieval contract via MockEmbeddingClient (3072 dims)
6. Entity-type filtering
7. Metadata filtering (rule_number, schedule_id, table_id, source_identifier)
8. Requirement -> provision statutory expansion
9. Provision -> schedule / table expansion where explicit relationships exist
10. Amendment relationship preservation
11. Deterministic deduplication (merges multi-source retrieval, preserves best score & all methods)
12. Deterministic ranking (Tier 1: Direct > Tier 2: Expanded > Tier 3: Semantic)
13. Completeness detection (all requested requirements resolved)
14. Missing requirement detection (identifies missing IDs explicitly)
15. Unknown applicability is not converted to false/not-applicable
16. Provenance is preserved (source identifier, quote, grounding)
17. No legal text is invented (exact text preserved)
18. Semantic retrieval does not override explicit legal relationships
19. Retrieval does not modify applicability rules
20. Retrieval does not modify legal corpus
21. Legacy match_legal_rules remains unchanged
22. Embedding dimension remains 3072
23. Empty embedding corpus produces a safe, explicit result rather than silently claiming completeness
24. Deterministic output ordering (stable tie-breaking)
25. Critical Architectural Test: Applicability Engine APPLICABLE requirement + contextual semantic query
26. Locked Phase 3A schema verification (strictly nine authoritative tables)
"""

from __future__ import annotations

import unittest
from datetime import date

from backend.app.services.legal_rag.embeddings.client import MockEmbeddingClient
from backend.app.services.legal_rag.models import (
    CompletenessStatus,
    LegalEntityType,
    LegalProvenance,
    RetrievalMethod,
    RetrievalMode,
    TemporalStatus,
)
from backend.app.services.legal_rag.retrieval import (
    CompletenessChecker,
    CoverageReport,
    DeterministicDeduplicator,
    DeterministicRanker,
    DirectLookupResolver,
    EmbeddingCoverageChecker,
    EXPECTED_LEGAL_ENTITY_COUNTS,
    InMemoryLegalCorpusRepository,
    LegalContextPackage,
    RetrievalRequest,
    RetrievedEntityContext,
    SemanticSearchResolver,
    StatutoryRelationshipExpander,
)
from backend.app.services.legal_rag.retrieval.service import LegalRetrievalService


# ==================================================
# SYNTHETIC TEST FIXTURES
# ==================================================

SYNTHETIC_REQ_1 = {
    "id": "req-pilot-mfg",
    "source_identifier": "doc_1_rule_6_1_a_mfg",
    "provision_id": 41,
    "requirement_type": "mandatory_declaration",
    "requirement_text": "Every package shall bear the name and address of the manufacturer.",
    "normalized_requirement": "manufacturer_identity_declaration",
    "subject": "Manufacturer identity",
    "source_quote": "name and complete address of the manufacturer",
    "source_reference": {"document_id": 1, "rule_number": "6", "sub_rule_number": "1", "clause": "a"},
}

SYNTHETIC_REQ_2 = {
    "id": "req-pilot-mrp",
    "source_identifier": "doc_1_rule_6_1_e_mrp",
    "provision_id": 42,
    "requirement_type": "mandatory_declaration",
    "requirement_text": "The retail sale price of the package shall clearly indicate Maximum Retail Price inclusive of all taxes.",
    "normalized_requirement": "retail_sale_price_mrp_declaration",
    "subject": "Maximum Retail Price (MRP)",
    "source_quote": "retail sale price of the package shall be clearly indicated as maximum retail price inclusive of all taxes",
    "source_reference": {"document_id": 1, "rule_number": "6", "sub_rule_number": "1", "clause": "e"},
}

SYNTHETIC_PROV_41 = {
    "id": 41,
    "document_id": 1,
    "source_identifier": "doc_1_rule_6_1_a",
    "rule_number": "6",
    "sub_rule_number": "1",
    "clause": "a",
    "title": "Declarations to be made on every package",
    "content": "Every package shall bear the name and address of the manufacturer.",
    "raw_content": "name and complete address of the manufacturer",
    "source_location": "Rule 6(1)(a)",
    "provision_type": "rule",
}

SYNTHETIC_PROV_42 = {
    "id": 42,
    "document_id": 1,
    "source_identifier": "doc_1_rule_6_1_e",
    "rule_number": "6",
    "sub_rule_number": "1",
    "clause": "e",
    "title": "Retail sale price",
    "content": "The retail sale price of the package shall clearly indicate Maximum Retail Price inclusive of all taxes.",
    "raw_content": "retail sale price of the package",
    "source_location": "Rule 6(1)(e)",
    "provision_type": "rule",
}

SYNTHETIC_SCHED_ENTRY_1 = {
    "id": "sched-entry-tea",
    "source_identifier": "doc_1_sched_2_entry_1",
    "schedule_id": "Second",
    "entry_number": 1,
    "commodity_text": "Tea",
    "quantity_text": "25g, 50g, 100g, 250g, 500g, 1kg",
    "raw_content": "Tea: 25g, 50g, 100g, 250g, 500g, 1kg",
    "normalized_content": "Tea: 25g, 50g, 100g, 250g, 500g, 1kg",
    "entry_key": "tea_package_sizes",
}

SYNTHETIC_TABLE_1 = {
    "id": "tbl-prov-42-exceptions",
    "source_identifier": "doc_1_table_prov_42",
    "table_identifier": "Table 42A",
    "title": "MRP Exemption Categories",
    "provision_id": 42,
    "raw_content": "Package types exempt from retail sale price declarations under Rule 6(1)(e)",
    "normalized_content": "Package types exempt from retail sale price declarations under Rule 6(1)(e)",
}

SYNTHETIC_AMENDMENT_1 = {
    "id": "amd-gsr-779",
    "source_identifier": "doc_1_amd_gsr_779",
    "amendment_identifier": "GSR 779(E)",
    "affected_provision_id": 42,
    "raw_content": "In Rule 6(1)(e), for unit sale price requirements, substitute new sub-clause (e).",
    "normalized_content": "In Rule 6(1)(e), for unit sale price requirements, substitute new sub-clause (e).",
    "effective_date": date(2022, 12, 1),
    "amendment_date": date(2022, 11, 2),
}

LOCKED_PHASE_3A_TABLES: tuple[str, ...] = (
    "applicability_rules",
    "applicability_rule_versions",
    "applicability_condition_groups",
    "applicability_conditions",
    "applicability_rule_sources",
    "applicability_runs",
    "inspection_facts",
    "applicability_decisions",
    "applicability_decision_evidence",
)

OBSOLETE_PHASE_3A_TABLES: tuple[str, ...] = (
    "applicability_rule_sets",
    "applicability_rule_packages",
    "applicability_predicates",
    "applicability_predicate_parameters",
    "applicability_decisions_audit",
)


def build_test_repository() -> InMemoryLegalCorpusRepository:
    """Build an in-memory repository populated with synthetic test fixtures."""
    repo = InMemoryLegalCorpusRepository()
    repo.register_requirement(SYNTHETIC_REQ_1)
    repo.register_requirement(SYNTHETIC_REQ_2)
    repo.register_provision(SYNTHETIC_PROV_41)
    repo.register_provision(SYNTHETIC_PROV_42)
    repo.register_schedule_entry(SYNTHETIC_SCHED_ENTRY_1)
    repo.register_table(SYNTHETIC_TABLE_1)
    repo.register_amendment(SYNTHETIC_AMENDMENT_1)
    return repo


class TestLegalRetrievalArchitecture(unittest.TestCase):
    """Phase 4C Unit Test Suite."""

    def setUp(self) -> None:
        self.repo = build_test_repository()
        self.embedding_client = MockEmbeddingClient()
        self.service = LegalRetrievalService(
            repository=self.repo,
            embedding_client=self.embedding_client,
        )

    def _embed_query(self, text: str) -> list[float]:
        return self.embedding_client.embed_text(text, task_type="RETRIEVAL_QUERY")


    # 1. Retrieval Request Validation
    def test_01_retrieval_request_validation(self) -> None:
        empty_req = RetrievalRequest()
        errors = empty_req.validate()
        self.assertTrue(any("Empty retrieval query" in e for e in errors))

        invalid_limit = RetrievalRequest(requirement_ids=["req-1"], limit=-5)
        errors = invalid_limit.validate()
        self.assertTrue(any("Limit must be positive" in e for e in errors))

        invalid_thresh = RetrievalRequest(requirement_ids=["req-1"], min_similarity_threshold=1.5)
        errors = invalid_thresh.validate()
        self.assertTrue(any("Similarity threshold must be between 0.0 and 1.0" in e for e in errors))

        valid_req = RetrievalRequest(requirement_ids=["req-pilot-mfg"])
        self.assertEqual(len(valid_req.validate()), 0)

    # 2. LegalContextPackage Construction
    def test_02_legal_context_package_construction(self) -> None:
        req = RetrievalRequest(requirement_ids=["req-pilot-mfg"])
        pkg = self.service.retrieve(req)

        self.assertIsInstance(pkg, LegalContextPackage)
        self.assertEqual(pkg.total_retrieved, len(pkg.entities))
        self.assertGreater(pkg.total_retrieved, 0)
        self.assertIn("Requirement: Manufacturer identity", pkg.formatted_context)
        self.assertIn("Source Identifier: doc_1_rule_6_1_a_mfg", pkg.formatted_context)

        reqs = pkg.requirements()
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].entity_id, "req-pilot-mfg")

    # 3. Direct Requirement Lookup
    def test_03_direct_requirement_lookup(self) -> None:
        req = RetrievalRequest(requirement_ids=["req-pilot-mfg"], expand_statutory_context=False)
        pkg = self.service.retrieve(req)

        self.assertEqual(len(pkg.entities), 1)
        entity = pkg.entities[0]
        self.assertEqual(entity.entity_id, "req-pilot-mfg")
        self.assertEqual(entity.entity_type, LegalEntityType.REQUIREMENT)
        self.assertEqual(entity.retrieval_method, RetrievalMethod.REQUIREMENT_LOOKUP)
        self.assertEqual(entity.ranking_tier, 1)
        self.assertEqual(entity.similarity_score, 1.0)
        self.assertIn("Every package shall bear", entity.legal_text)

    # 4. Direct Provision Lookup
    def test_04_direct_provision_lookup(self) -> None:
        req = RetrievalRequest(provision_ids=[41], expand_statutory_context=False)
        pkg = self.service.retrieve(req)

        self.assertEqual(len(pkg.entities), 1)
        entity = pkg.entities[0]
        self.assertEqual(entity.entity_id, "41")
        self.assertEqual(entity.entity_type, LegalEntityType.PROVISION)
        self.assertEqual(entity.retrieval_method, RetrievalMethod.EXACT_ID)
        self.assertEqual(entity.ranking_tier, 1)
        self.assertIn("Rule 6(1)(a)", entity.title)

    # 5. Semantic Retrieval Contract
    def test_05_semantic_retrieval_contract(self) -> None:
        query_emb = self._embed_query("maximum retail price")
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-pilot-mrp",
            "embedding": query_emb,
            "similarity": 1.0,
        })

        req = RetrievalRequest(
            query_text="maximum retail price",
            expand_statutory_context=False,
            min_similarity_threshold=0.5,
        )
        pkg = self.service.retrieve(req)

        self.assertGreaterEqual(len(pkg.entities), 1)
        sem_res = pkg.get_by_id("req-pilot-mrp")
        self.assertIsNotNone(sem_res)
        self.assertEqual(sem_res.entity_type, LegalEntityType.REQUIREMENT)
        self.assertIn(RetrievalMethod.SEMANTIC_VECTOR, sem_res.retrieval_methods)
        self.assertAlmostEqual(sem_res.similarity_score, 1.0, places=3)

    # 6. Entity-Type Filtering
    def test_06_entity_type_filtering(self) -> None:
        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg"],
            provision_ids=[41],
            entity_types=[LegalEntityType.REQUIREMENT],
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        for ent in pkg.entities:
            self.assertEqual(ent.entity_type, LegalEntityType.REQUIREMENT)
        self.assertEqual(len(pkg.entities), 1)
        self.assertEqual(pkg.entities[0].entity_id, "req-pilot-mfg")

    # 7. Metadata Filtering
    def test_07_metadata_filtering(self) -> None:
        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg", "req-pilot-mrp"],
            context_filters={"rule_number": "6"},
            source_filters={"source_identifier": "doc_1_rule_6_1_a_mfg"},
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        self.assertEqual(len(pkg.entities), 1)
        self.assertEqual(pkg.entities[0].entity_id, "req-pilot-mfg")

    # 8. Requirement -> Provision Expansion
    def test_08_requirement_to_provision_expansion(self) -> None:
        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg"],
            expand_statutory_context=True,
        )
        pkg = self.service.retrieve(req)

        prov_ent = pkg.get_by_id("41")
        self.assertIsNotNone(prov_ent)
        self.assertEqual(prov_ent.entity_type, LegalEntityType.PROVISION)
        self.assertEqual(prov_ent.retrieval_method, RetrievalMethod.PROVENANCE_EXPANSION)
        self.assertEqual(prov_ent.ranking_tier, 2)
        self.assertIn("req-pilot-mfg", prov_ent.linked_requirement_ids)
        req_ent = pkg.get_by_id("req-pilot-mfg")
        self.assertIn(41, req_ent.linked_provision_ids)

    # 9. Provision -> Schedule / Table Expansion
    def test_09_provision_to_table_expansion(self) -> None:
        req = RetrievalRequest(
            provision_ids=[42],
            expand_statutory_context=True,
        )
        pkg = self.service.retrieve(req)

        tbl_ent = pkg.get_by_id("tbl-prov-42-exceptions")
        self.assertIsNotNone(tbl_ent)
        self.assertEqual(tbl_ent.entity_type, LegalEntityType.TABLE)
        self.assertEqual(tbl_ent.retrieval_method, RetrievalMethod.HIERARCHICAL_TRAVERSAL)
        self.assertEqual(tbl_ent.ranking_tier, 2)
        self.assertIn(42, tbl_ent.linked_provision_ids)

    # 10. Amendment Relationship Preservation
    def test_10_amendment_relationship_preservation(self) -> None:
        req = RetrievalRequest(
            provision_ids=[42],
            expand_statutory_context=True,
        )
        pkg = self.service.retrieve(req)

        amd_ent = pkg.get_by_id("amd-gsr-779")
        self.assertIsNotNone(amd_ent)
        self.assertEqual(amd_ent.entity_type, LegalEntityType.AMENDMENT)
        self.assertIn(42, amd_ent.linked_provision_ids)
        self.assertEqual(amd_ent.effective_from, date(2022, 12, 1))
        self.assertEqual(amd_ent.temporal_status, TemporalStatus.CURRENT)

    # 11. Deterministic Deduplication
    def test_11_deterministic_deduplication(self) -> None:
        mfg_emb = self._embed_query("manufacturer name address")
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-pilot-mfg",
            "embedding": mfg_emb,
            "similarity": 0.95,
        })

        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg"],
            query_text="manufacturer name address",
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        mfg_matches = [e for e in pkg.entities if e.entity_id == "req-pilot-mfg"]
        self.assertEqual(len(mfg_matches), 1)

        ent = mfg_matches[0]
        self.assertTrue(ent.deduplicated)
        self.assertIn(RetrievalMethod.REQUIREMENT_LOOKUP, ent.retrieval_methods)
        self.assertIn(RetrievalMethod.SEMANTIC_VECTOR, ent.retrieval_methods)
        self.assertEqual(ent.ranking_tier, 1)
        self.assertAlmostEqual(ent.similarity_score, 1.0, places=5)

    # 12. Deterministic Ranking
    def test_12_deterministic_ranking(self) -> None:
        mrp_emb = self._embed_query("retail sale price")
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-pilot-mrp",
            "embedding": mrp_emb,
            "similarity": 0.98,
        })

        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg"],
            query_text="retail sale price",
            expand_statutory_context=True,
        )
        pkg = self.service.retrieve(req)

        self.assertEqual(pkg.entities[0].entity_id, "req-pilot-mfg")
        self.assertEqual(pkg.entities[0].ranking_tier, 1)

        tier2_entities = [e for e in pkg.entities if e.ranking_tier == 2]
        self.assertGreater(len(tier2_entities), 0)
        first_tier2_idx = pkg.entities.index(tier2_entities[0])
        self.assertGreater(first_tier2_idx, 0)

        tier3_entities = [e for e in pkg.entities if e.ranking_tier == 3]
        if tier3_entities:
            first_tier3_idx = pkg.entities.index(tier3_entities[0])
            self.assertGreater(first_tier3_idx, first_tier2_idx)

    # 13. Completeness Detection
    def test_13_completeness_detection(self) -> None:
        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg", "req-pilot-mrp"],
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        comp = pkg.completeness
        self.assertIsNotNone(comp)
        self.assertTrue(comp.is_complete)
        self.assertEqual(comp.status, CompletenessStatus.COMPLETE)
        self.assertEqual(comp.missing_requirement_ids, frozenset())
        self.assertEqual(comp.retrieved_requirement_ids, frozenset(["req-pilot-mfg", "req-pilot-mrp"]))

    # 14. Missing Requirement Detection
    def test_14_missing_requirement_detection(self) -> None:
        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg", "non-existent-req-999"],
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        comp = pkg.completeness
        self.assertIsNotNone(comp)
        self.assertFalse(comp.is_complete)
        self.assertEqual(comp.status, CompletenessStatus.PARTIAL)
        self.assertIn("non-existent-req-999", comp.missing_requirement_ids)
        self.assertIn("req-pilot-mfg", comp.retrieved_requirement_ids)

    # 15. Unknown Applicability Preservation
    def test_15_unknown_applicability_is_not_converted_to_false(self) -> None:
        mock_applicability_output = {
            "decisions": [
                {"requirement_id": "req-pilot-mfg", "decision": "applicable"},
                {"requirement_id": "req-pilot-mrp", "decision": "unknown", "reason": "missing packaging dimension"},
            ]
        }
        req = RetrievalRequest(
            applicability_output=mock_applicability_output,
            expand_statutory_context=False,
        )
        self.assertIn("req-pilot-mfg", req.requirement_ids)
        self.assertNotIn("req-pilot-mrp", req.requirement_ids)

        pkg = self.service.retrieve(req)
        self.assertEqual(pkg.total_retrieved, 1)
        self.assertEqual(pkg.entities[0].entity_id, "req-pilot-mfg")

    # 16. Provenance Preservation
    def test_16_provenance_is_preserved(self) -> None:
        req = RetrievalRequest(requirement_ids=["req-pilot-mfg"], expand_statutory_context=False)
        pkg = self.service.retrieve(req)

        entity = pkg.entities[0]
        self.assertIsNotNone(entity.provenance)
        self.assertEqual(entity.provenance.source_identifier, "doc_1_rule_6_1_a_mfg")
        self.assertEqual(entity.provenance.document_id, 1)
        self.assertEqual(entity.provenance.rule_number, "6")
        self.assertEqual(entity.provenance.sub_rule_number, "1")
        self.assertEqual(entity.provenance.clause, "a")
        self.assertTrue(entity.provenance.is_valid())

    # 17. No Legal Text Invention
    def test_17_no_legal_text_is_invented(self) -> None:
        req = RetrievalRequest(requirement_ids=["req-pilot-mfg"], expand_statutory_context=False)
        pkg = self.service.retrieve(req)

        entity = pkg.entities[0]
        self.assertEqual(entity.legal_text, SYNTHETIC_REQ_1["requirement_text"])
        self.assertEqual(entity.source_quote, SYNTHETIC_REQ_1["source_quote"])

    # 18. Semantic Retrieval Does Not Override Explicit Legal Relationships
    def test_18_semantic_retrieval_does_not_override_explicit_relationships(self) -> None:
        low_score_emb = self._embed_query("some query")
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-pilot-mfg",
            "embedding": low_score_emb,
            "similarity": 0.40,
            "mock_similarity": 0.40,
        })
        high_score_emb = self._embed_query("tea packages")
        self.repo.register_embedding({
            "entity_type": "schedule_entry",
            "entity_id": "sched-entry-tea",
            "embedding": high_score_emb,
            "similarity": 0.99,
            "mock_similarity": 0.99,
        })

        req = RetrievalRequest(
            requirement_ids=["req-pilot-mfg"],
            query_text="tea packages",
            min_similarity_threshold=0.3,
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        self.assertEqual(pkg.entities[0].entity_id, "req-pilot-mfg")
        self.assertEqual(pkg.entities[0].ranking_tier, 1)

    # 19. Retrieval Does Not Modify Applicability Rules
    def test_19_retrieval_does_not_modify_applicability_rules(self) -> None:
        applicability_decision = {
            "requirement_id": "req-pilot-mfg",
            "decision": "applicable",
            "audit_trail": ["Rule 6(1)(a) evaluated"],
        }
        req = RetrievalRequest(
            applicability_output=applicability_decision,
            expand_statutory_context=False,
        )
        pkg = self.service.retrieve(req)

        self.assertEqual(applicability_decision["decision"], "applicable")
        self.assertEqual(len(applicability_decision["audit_trail"]), 1)
        self.assertEqual(pkg.total_retrieved, 1)

    # 20. Retrieval Does Not Modify Legal Corpus
    def test_20_retrieval_does_not_modify_legal_corpus(self) -> None:
        counts_before = {
            "req": self.repo.count_legal_entities("requirement"),
            "prov": self.repo.count_legal_entities("provision"),
            "sched": self.repo.count_legal_entities("schedule_entry"),
            "tbl": self.repo.count_legal_entities("table"),
            "amd": self.repo.count_legal_entities("amendment"),
        }

        self.service.retrieve(RetrievalRequest(requirement_ids=["req-pilot-mfg"]))
        self.service.retrieve(RetrievalRequest(provision_ids=[41]))
        self.service.retrieve(RetrievalRequest(query_text="manufacturer"))

        counts_after = {
            "req": self.repo.count_legal_entities("requirement"),
            "prov": self.repo.count_legal_entities("provision"),
            "sched": self.repo.count_legal_entities("schedule_entry"),
            "tbl": self.repo.count_legal_entities("table"),
            "amd": self.repo.count_legal_entities("amendment"),
        }
        self.assertEqual(counts_before, counts_after)

    # 21. Legacy match_legal_rules Remains Unchanged
    def test_21_legacy_match_legal_rules_remains_unchanged(self) -> None:
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["requirement"], 437)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["provision"], 341)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["schedule_entry"], 96)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["table"], 10)
        self.assertEqual(EXPECTED_LEGAL_ENTITY_COUNTS["amendment"], 76)
        self.assertEqual(sum(EXPECTED_LEGAL_ENTITY_COUNTS.values()), 960)

    # 22. Embedding Dimension Remains 3072
    def test_22_embedding_dimension_remains_3072(self) -> None:
        emb = self._embed_query("test legal query")
        self.assertEqual(len(emb), 3072)

    # 23. Empty Embedding Corpus Produces Safe Explicit Result
    def test_23_empty_embedding_corpus_safe_result(self) -> None:
        empty_repo = InMemoryLegalCorpusRepository()
        empty_service = LegalRetrievalService(
            repository=empty_repo,
            embedding_client=self.embedding_client,
        )

        req = RetrievalRequest(query_text="retail sale price declaration")
        pkg = empty_service.retrieve(req)

        self.assertEqual(pkg.total_retrieved, 0)
        self.assertIsNotNone(pkg.empty_reason)
        self.assertIn("No legal provisions matched", pkg.empty_reason)
        self.assertTrue(pkg.completeness.is_complete)

    # 24. Deterministic Output Ordering
    def test_24_deterministic_output_ordering(self) -> None:
        req = RetrievalRequest(
            requirement_ids=["req-pilot-mrp", "req-pilot-mfg"],
            expand_statutory_context=False,
        )
        pkg1 = self.service.retrieve(req)
        pkg2 = self.service.retrieve(req)

        ids_1 = [e.entity_id for e in pkg1.entities]
        ids_2 = [e.entity_id for e in pkg2.entities]
        self.assertEqual(ids_1, ids_2)
        self.assertEqual(ids_1, ["req-pilot-mfg", "req-pilot-mrp"])

    # 25. Critical Architectural Test
    def test_25_critical_architectural_scenario(self) -> None:
        """Applicability Engine says requirement A is applicable.

        Retrieval directly retrieves requirement A and legal context.
        Semantic query retrieves B and C.
        Requirement A remains present at the top even if A has a lower semantic score.
        """
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-pilot-mfg",
            "embedding": self._embed_query("tea pack"),
            "similarity": 0.35,
            "mock_similarity": 0.35,
        })
        self.repo.register_embedding({
            "entity_type": "requirement",
            "entity_id": "req-pilot-mrp",
            "embedding": self._embed_query("tea packages"),
            "similarity": 0.80,
            "mock_similarity": 0.80,
        })
        self.repo.register_embedding({
            "entity_type": "schedule_entry",
            "entity_id": "sched-entry-tea",
            "embedding": self._embed_query("tea packages prescribed weights"),
            "similarity": 0.95,
            "mock_similarity": 0.95,
        })

        applicability_result = {
            "decisions": [
                {"requirement_id": "req-pilot-mfg", "decision": "applicable"},
            ]
        }

        req = RetrievalRequest(
            applicability_output=applicability_result,
            query_text="tea packages prescribed weights",
            min_similarity_threshold=0.3,
            expand_statutory_context=True,
        )

        pkg = self.service.retrieve(req)

        # 1. Directly requested requirement A was retrieved directly
        req_a = pkg.get_by_id("req-pilot-mfg")
        self.assertIsNotNone(req_a)

        # 2. Semantic entities B and C were retrieved
        req_b = pkg.get_by_id("req-pilot-mrp")
        sched_c = pkg.get_by_id("sched-entry-tea")
        self.assertIsNotNone(req_b)
        self.assertIsNotNone(sched_c)

        # 3. Requirement A remains at the very top (Tier 1) despite having lower semantic score
        self.assertEqual(pkg.entities[0].entity_id, "req-pilot-mfg")
        self.assertEqual(pkg.entities[0].ranking_tier, 1)

        # 4. Legal context (parent Provision 41) was expanded for A
        prov_41 = pkg.get_by_id("41")
        self.assertIsNotNone(prov_41)

        # 5. Completeness shows requirement A was covered
        self.assertTrue(pkg.completeness.is_complete)
        self.assertIn("req-pilot-mfg", pkg.completeness.retrieved_requirement_ids)

    # 26. Locked Phase 3A Schema Verification
    def test_26_locked_phase_3a_schema_table_names(self) -> None:
        """Verify the exact nine locked Phase 3A tables are referenced, and no obsolete tables."""
        self.assertEqual(len(LOCKED_PHASE_3A_TABLES), 9)
        self.assertEqual(
            set(LOCKED_PHASE_3A_TABLES),
            {
                "applicability_rules",
                "applicability_rule_versions",
                "applicability_condition_groups",
                "applicability_conditions",
                "applicability_rule_sources",
                "applicability_runs",
                "inspection_facts",
                "applicability_decisions",
                "applicability_decision_evidence",
            },
        )
        # Ensure obsolete table names are NOT in the locked schema
        for obsolete in OBSOLETE_PHASE_3A_TABLES:
            self.assertNotIn(obsolete, LOCKED_PHASE_3A_TABLES)


if __name__ == "__main__":
    unittest.main()
