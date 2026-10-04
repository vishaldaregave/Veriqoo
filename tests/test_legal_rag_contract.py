"""Phase 4A Tests: Legal RAG Architecture & Retrieval Contract Verification.

Verifies:
1. Retrieval request validation (limits, modes, IDs, empty signal detection)
2. Result structure validation (types, fields, formatting)
3. Provenance preservation (corpus grounding, rejection of AI/synthetic provenance)
4. Entity type validation (all 5 canonical entities)
5. Requirement / provision distinction
6. Schedule / table distinction
7. Deduplication contract (provenance merging, cross-entity linking)
8. No-result behavior (deterministic empty response, no hallucinations)
9. Completeness is distinct from top-K retrieval (top-K does not satisfy completeness)
10. Requirement-ID based retrieval representation (applicable requirement resolution)
11. Temporal UNKNOWN is preserved
12. No invented dates
13. No fabricated legal text
14. Existing Phase 1–3 behavior remains unaffected
"""

from __future__ import annotations

import unittest
from datetime import date
from uuid import uuid4

from backend.app.services.legal_rag import (
    CompletenessStatus,
    LegalEntityType,
    LegalProvenance,
    LegalRetrievalContract,
    LegalRetrievalQuery,
    LegalRetrievalResponse,
    LegalRetrievalService,
    LegalSearchResult,
    RankingMetadata,
    RetrievalCompleteness,
    RetrievalConfig,
    RetrievalMethod,
    RetrievalMode,
    TemporalStatus,
    apply_provisional_threshold,
    build_schedule_entry_result,
    build_table_result,
    deduplicate_results,
    evaluate_completeness,
    format_schedule_entry_text,
    merge_provenance,
    rank_results,
    resolve_temporal_status,
    validate_provenance,
)


# ==================================================
# TEST FIXTURES (CLEARLY MARKED AS SYNTHETIC TEST OBJECTS)
# ==================================================

TEST_FIXTURE_REQ_1 = {
    "id": "test-req-001",
    "source_identifier": "test-src-ident-req-1",
    "provision_id": 41,
    "requirement_type": "mandatory_declaration",
    "requirement_text": "Every package shall bear the name and address of the manufacturer.",
    "normalized_requirement": "manufacturer_name_and_address_declaration",
    "subject": "Manufacturer identity declaration",
    "source_quote": "name and address of the manufacturer",
    "source_reference": {"document_id": 1, "rule_number": "6", "sub_rule_number": "1", "clause": "a", "source_page": 12},
    "effective_from": None,
    "effective_to": None,
}

TEST_FIXTURE_REQ_2 = {
    "id": "test-req-002",
    "source_identifier": "test-src-ident-req-2",
    "provision_id": 41,
    "requirement_type": "mandatory_declaration",
    "requirement_text": "Every package of imported goods shall bear the name and address of the importer.",
    "normalized_requirement": "importer_name_and_address_declaration",
    "subject": "Importer identity declaration",
    "source_quote": "and for any imported packages the name and address of the importer",
    "source_reference": {"document_id": 1, "rule_number": "6", "sub_rule_number": "1", "clause": "a", "source_page": 12},
    "effective_from": None,
    "effective_to": None,
}

TEST_FIXTURE_PROV_41 = {
    "id": 41,
    "document_id": 1,
    "rule_number": "6",
    "sub_rule_number": "1",
    "clause": "a",
    "provision_type": "clause",
    "title": "Declarations to be made on every package",
    "content": "the name and address of the manufacturer or where the manufacturer is not the packer...",
    "raw_content": "the name and address of the manufacturer or where the manufacturer is not the packer...",
    "source_location": "Rule 6(1)(a)",
}

TEST_FIXTURE_SCHEDULE_ENTRY = {
    "id": "test-sched-entry-001",
    "source_identifier": "test-src-sched-entry-1",
    "schedule_id": "test-sched-uuid-2",
    "entry_key": "entry_commodities_tea",
    "entry_number": "1",
    "entry_type": "standard_commodity",
    "commodity_text": "Tea",
    "quantity_text": "25g, 50g, 100g, 250g, 500g, 1kg",
    "item_text": "Tea (including tea bags)",
    "permitted_package_quantity": "25g, 50g, 100g, 250g, 500g, 1kg",
    "raw_content": "1. Tea (including tea bags) : 25g, 50g, 100g, 250g, 500g, 1kg",
    "normalized_content": "1. Tea (including tea bags) : 25g, 50g, 100g, 250g, 500g, 1kg",
    "cells": [{"column": "commodity", "value": "Tea"}, {"column": "quantities", "value": "25g to 1kg"}],
}

TEST_FIXTURE_TABLE = {
    "id": "test-table-001",
    "source_identifier": "test-src-table-1",
    "document_id": 1,
    "schedule_id": "test-sched-uuid-2",
    "table_identifier": "Table-2",
    "title": "Standard Packaging Units Table",
    "headers": ["Item No", "Commodity", "Permitted Sizes"],
    "raw_content": "| Item No | Commodity | Permitted Sizes |\n| 1 | Tea | 25g, 50g, 100g |",
    "normalized_content": "| Item No | Commodity | Permitted Sizes |\n| 1 | Tea | 25g, 50g, 100g |",
}

TEST_FIXTURE_AMENDMENT = {
    "id": "test-amd-001",
    "source_identifier": "test-src-amd-1",
    "document_id": 1,
    "affected_provision_id": 41,
    "amendment_identifier": "G.S.R. 779(E)",
    "amendment_date": date(2021, 11, 2),
    "effective_date": date(2022, 1, 1),
    "raw_content": "In rule 6, in sub-rule (1), for clause (a), the following clause shall be substituted...",
    "normalized_content": "In rule 6, in sub-rule (1), for clause (a), the following clause shall be substituted...",
}


class LegalRAGContractTests(unittest.TestCase):
    """Phase 4A test suite verifying the Legal RAG retrieval contract."""

    def setUp(self):
        self.service = LegalRetrievalService()
        self.service.register_requirement(TEST_FIXTURE_REQ_1)
        self.service.register_requirement(TEST_FIXTURE_REQ_2)
        self.service.register_provision(TEST_FIXTURE_PROV_41)
        self.service.register_schedule_entry(TEST_FIXTURE_SCHEDULE_ENTRY)
        self.service.register_table(TEST_FIXTURE_TABLE)
        self.service.register_amendment(TEST_FIXTURE_AMENDMENT)

    # --------------------------------------------------
    # 1. Retrieval Request Validation
    # --------------------------------------------------

    def test_01_retrieval_request_validation(self):
        # Empty query with no signals
        empty_q = LegalRetrievalQuery()
        errors = self.service.validate_query(empty_q)
        self.assertTrue(any("no retrieval signals" in e for e in errors))

        # Invalid limit
        bad_limit = LegalRetrievalQuery(query_text="mrp", limit=0)
        errors = self.service.validate_query(bad_limit)
        self.assertTrue(any("limit must be positive" in e for e in errors))

        # Excessive limit
        too_high = LegalRetrievalQuery(query_text="mrp", limit=1000)
        errors = self.service.validate_query(too_high)
        self.assertTrue(any("exceeds maximum allowed" in e for e in errors))

        # Invalid similarity threshold
        bad_thresh = LegalRetrievalQuery(query_text="mrp", min_similarity_threshold=1.5)
        errors = self.service.validate_query(bad_thresh)
        self.assertTrue(any("Similarity threshold must be between 0.0 and 1.0" in e for e in errors))

        # Invalid provision ID
        bad_prov = LegalRetrievalQuery(provision_ids=[-5])
        errors = self.service.validate_query(bad_prov)
        self.assertTrue(any("provision_id must be a positive integer" in e for e in errors))

        # Valid query produces no errors
        valid_q = LegalRetrievalQuery(requirement_ids=["test-req-001"], mode=RetrievalMode.REQUIREMENT_CONTEXT)
        self.assertEqual([], self.service.validate_query(valid_q))

    # --------------------------------------------------
    # 2. Result Structure Validation
    # --------------------------------------------------

    def test_02_result_structure_validation(self):
        res = self.service.retrieve(
            LegalRetrievalQuery(requirement_ids=["test-req-001"], mode=RetrievalMode.REQUIREMENT_CONTEXT)
        )
        self.assertGreater(len(res.results), 0)
        first = res.results[0]

        # Field existence & type checks
        self.assertIsInstance(first.entity_type, LegalEntityType)
        self.assertEqual(first.entity_type, LegalEntityType.REQUIREMENT)
        self.assertEqual(first.entity_id, "test-req-001")
        self.assertEqual(first.source_identifier, "test-src-ident-req-1")
        self.assertIsNotNone(first.provenance)
        self.assertIsInstance(first.provenance, LegalProvenance)
        self.assertIsInstance(first.ranking, RankingMetadata)
        self.assertIsInstance(first.retrieval_method, RetrievalMethod)

        # Context format check
        formatted = first.format_for_context()
        self.assertIn("[REQUIREMENT] ID: test-req-001", formatted)
        self.assertIn("Statutory Quote:", formatted)
        self.assertIn("Legal Reference:", formatted)

    # --------------------------------------------------
    # 3. Provenance Preservation
    # --------------------------------------------------

    def test_03_provenance_preservation(self):
        # Valid provenance
        valid_prov = LegalProvenance(
            source_identifier="valid-src",
            document_id=1,
            provision_id=41,
            rule_number="6",
            source_quote="name and address of manufacturer",
        )
        self.assertTrue(valid_prov.is_valid())
        self.assertEqual([], validate_provenance(valid_prov))

        # Missing quote
        empty_quote = LegalProvenance(source_identifier="valid-src", document_id=1, provision_id=41, source_quote="  ")
        self.assertFalse(empty_quote.is_valid())
        errors = validate_provenance(empty_quote)
        self.assertTrue(any("source_quote is empty" in e for e in errors))

        # AI / Synthetic markers rejected
        for bad_quote in [
            "Gemini says this package requires an MRP",
            "model inferred manufacturer name",
            "Vector search says rule 6 applies",
            "[paraphrased] rule text",
            "synthetic legal rule",
        ]:
            with self.subTest(quote=bad_quote):
                bad_prov = LegalProvenance(
                    source_identifier="valid-src",
                    document_id=1,
                    provision_id=41,
                    source_quote=bad_quote,
                )
                self.assertFalse(bad_prov.is_valid())
                errs = validate_provenance(bad_prov)
                self.assertTrue(any("ungrounded/synthetic marker" in e for e in errs))

    # --------------------------------------------------
    # 4. Entity Type Validation
    # --------------------------------------------------

    def test_04_entity_type_validation(self):
        expected_types = {
            LegalEntityType.REQUIREMENT,
            LegalEntityType.PROVISION,
            LegalEntityType.SCHEDULE_ENTRY,
            LegalEntityType.TABLE,
            LegalEntityType.AMENDMENT,
        }
        actual_types = set(LegalEntityType)
        self.assertEqual(expected_types, actual_types)

        # Retrieve one of each entity from service
        req_res = self.service.retrieve(LegalRetrievalQuery(requirement_ids=["test-req-001"]))
        prov_res = self.service.retrieve(LegalRetrievalQuery(provision_ids=[41]))
        entry_res = self.service.retrieve(LegalRetrievalQuery(schedule_entry_ids=["test-sched-entry-001"]))
        tbl_res = self.service.retrieve(LegalRetrievalQuery(table_ids=["test-table-001"]))
        amd_res = self.service.retrieve(LegalRetrievalQuery(amendment_ids=["test-amd-001"]))

        self.assertEqual(LegalEntityType.REQUIREMENT, req_res.results[0].entity_type)
        self.assertEqual(LegalEntityType.PROVISION, prov_res.results[0].entity_type)
        self.assertEqual(LegalEntityType.SCHEDULE_ENTRY, entry_res.results[0].entity_type)
        self.assertEqual(LegalEntityType.TABLE, tbl_res.results[0].entity_type)
        self.assertEqual(LegalEntityType.AMENDMENT, amd_res.results[0].entity_type)

    # --------------------------------------------------
    # 5. Requirement vs Provision Distinction
    # --------------------------------------------------

    def test_05_requirement_provision_distinction(self):
        req_res = self.service.retrieve(LegalRetrievalQuery(requirement_ids=["test-req-001"]))
        prov_res = self.service.retrieve(LegalRetrievalQuery(provision_ids=[41]))

        req = next(r for r in req_res.results if r.entity_type == LegalEntityType.REQUIREMENT)
        prov = next(r for r in prov_res.results if r.entity_type == LegalEntityType.PROVISION)

        # Requirement carries normalized compliance obligation
        self.assertIsNotNone(req.normalized_requirement)
        self.assertEqual("manufacturer_name_and_address_declaration", req.normalized_requirement)

        # Provision carries statutory hierarchy
        self.assertIsNone(prov.normalized_requirement)
        self.assertIn("Rule 6(1)(a)", prov.title)
        self.assertNotEqual(req.entity_type, prov.entity_type)

    # --------------------------------------------------
    # 6. Schedule vs Table Distinction
    # --------------------------------------------------

    def test_06_schedule_table_distinction(self):
        entry_res = self.service.retrieve(LegalRetrievalQuery(schedule_entry_ids=["test-sched-entry-001"]))
        tbl_res = self.service.retrieve(LegalRetrievalQuery(table_ids=["test-table-001"]))

        entry = entry_res.results[0]
        table = tbl_res.results[0]

        # Schedule entry preserves structured commodity and quantities
        self.assertEqual(LegalEntityType.SCHEDULE_ENTRY, entry.entity_type)
        self.assertEqual("Tea", entry.commodity_text)
        self.assertIn("25g", entry.quantity_text)
        self.assertGreater(len(entry.raw_cells), 0)

        # Table preserves headers and table identifier
        self.assertEqual(LegalEntityType.TABLE, table.entity_type)
        self.assertEqual(["Item No", "Commodity", "Permitted Sizes"], table.table_headers)
        self.assertIn("Table-2", table.metadata["table_identifier"])

    # --------------------------------------------------
    # 7. Deduplication Contract
    # --------------------------------------------------

    def test_07_deduplication_contract(self):
        # Query that returns the same requirement via exact lookup AND lexical query
        query = LegalRetrievalQuery(
            requirement_ids=["test-req-001"],
            query_text="manufacturer address",
            mode=RetrievalMode.REQUIREMENT_CONTEXT,
        )
        res = self.service.retrieve(query)

        # Should only contain 1 requirement result (not 2 duplicates)
        req_results = [r for r in res.results if r.entity_id == "test-req-001"]
        self.assertEqual(1, len(req_results))

        # Provenance is preserved and combined
        first_req = req_results[0]
        self.assertIsNotNone(first_req.provenance)
        self.assertEqual("test-src-ident-req-1", first_req.provenance.source_identifier)

        # Cross-entity linkage: provision 41 was pulled in via provenance expansion
        prov_results = [r for r in res.results if r.entity_type == LegalEntityType.PROVISION]
        if prov_results:
            self.assertIn("41", first_req.linked_entity_ids)

    # --------------------------------------------------
    # 8. No-Result Behavior
    # --------------------------------------------------

    def test_08_no_result_behavior(self):
        # Query for non-existent IDs
        query = LegalRetrievalQuery(
            requirement_ids=["non-existent-req-999"],
            mode=RetrievalMode.REQUIREMENT_CONTEXT,
        )
        res = self.service.retrieve(query)

        self.assertEqual(0, len(res.results))
        self.assertEqual(0, res.total_found)
        self.assertIsNotNone(res.no_result_reason)
        self.assertIn("No matching", res.no_result_reason)
        # Verify no fabricated content in formatted context
        self.assertEqual("No applicable legal provisions retrieved.", res.formatted_context)

    # --------------------------------------------------
    # 9. Completeness is Distinct from Top-K Retrieval
    # --------------------------------------------------

    def test_09_completeness_is_distinct_from_top_k_retrieval(self):
        # Request 2 requirements, but only 1 is in the search result
        requested_ids = ["test-req-001", "test-req-002", "test-req-missing-003"]
        dummy_results = [
            LegalSearchResult(
                entity_type=LegalEntityType.REQUIREMENT,
                entity_id="test-req-001",
                source_identifier="src-1",
                provenance=LegalProvenance(source_identifier="src-1", document_id=1, provision_id=41, source_quote="quote"),
            )
        ]

        completeness = evaluate_completeness(
            requested_requirement_ids=requested_ids,
            results=dummy_results,
            semantic_top_k_count=10,  # 10 semantic results found!
        )

        # Top-K count is 10, BUT completeness is PARTIAL and False
        self.assertEqual(10, completeness.semantic_top_k_count)
        self.assertEqual(CompletenessStatus.PARTIAL, completeness.status)
        self.assertFalse(completeness.is_complete)
        self.assertEqual({"test-req-002", "test-req-missing-003"}, completeness.missing_requirement_ids)
        self.assertTrue(any("cannot substitute for missing applicable" in note for note in completeness.notes))

        # Now test full coverage
        dummy_results.extend([
            LegalSearchResult(
                entity_type=LegalEntityType.REQUIREMENT,
                entity_id="test-req-002",
                source_identifier="src-2",
                provenance=LegalProvenance(source_identifier="src-2", document_id=1, provision_id=41, source_quote="quote"),
            ),
            LegalSearchResult(
                entity_type=LegalEntityType.REQUIREMENT,
                entity_id="test-req-missing-003",
                source_identifier="src-3",
                provenance=LegalProvenance(source_identifier="src-3", document_id=1, provision_id=41, source_quote="quote"),
            ),
        ])

        complete_eval = evaluate_completeness(
            requested_requirement_ids=requested_ids,
            results=dummy_results,
            semantic_top_k_count=3,
        )
        self.assertEqual(CompletenessStatus.COMPLETE, complete_eval.status)
        self.assertTrue(complete_eval.is_complete)
        self.assertEqual(set(), complete_eval.missing_requirement_ids)

    # --------------------------------------------------
    # 10. Requirement-ID Based Retrieval Representation
    # --------------------------------------------------

    def test_10_requirement_id_based_retrieval(self):
        res = self.service.retrieve_for_applicable_requirements(
            requirement_ids=["test-req-001", "test-req-002"]
        )
        self.assertIsNotNone(res.completeness)
        self.assertTrue(res.completeness.is_complete)
        self.assertEqual(CompletenessStatus.COMPLETE, res.completeness.status)

        retrieved_ids = {r.entity_id for r in res.results if r.entity_type == LegalEntityType.REQUIREMENT}
        self.assertTrue({"test-req-001", "test-req-002"}.issubset(retrieved_ids))

    # --------------------------------------------------
    # 11. Temporal UNKNOWN is Preserved
    # --------------------------------------------------

    def test_11_temporal_unknown_is_preserved(self):
        # Missing dates in statutory record -> UNKNOWN
        status1 = resolve_temporal_status(effective_from=None, effective_to=None, as_of_date=date(2023, 1, 1))
        self.assertEqual(TemporalStatus.UNKNOWN, status1)

        # Missing as_of_date in inspection -> UNKNOWN
        status2 = resolve_temporal_status(effective_from=date(2022, 1, 1), effective_to=None, as_of_date=None)
        self.assertEqual(TemporalStatus.UNKNOWN, status2)

        # Both missing -> UNKNOWN
        status3 = resolve_temporal_status(effective_from=None, effective_to=None, as_of_date=None)
        self.assertEqual(TemporalStatus.UNKNOWN, status3)

    # --------------------------------------------------
    # 12. No Invented Dates
    # --------------------------------------------------

    def test_12_no_invented_dates(self):
        # Requirements with no dates in source remain None
        res = self.service.retrieve(LegalRetrievalQuery(requirement_ids=["test-req-001"]))
        req = next(r for r in res.results if r.entity_type == LegalEntityType.REQUIREMENT)
        self.assertIsNone(req.effective_from)
        self.assertIsNone(req.effective_to)
        self.assertEqual(TemporalStatus.UNKNOWN, req.temporal_status)

        # Amendment with explicit date retains ONLY that explicit date
        amd_res = self.service.retrieve(LegalRetrievalQuery(amendment_ids=["test-amd-001"]))
        amd = next(r for r in amd_res.results if r.entity_type == LegalEntityType.AMENDMENT)
        self.assertEqual(date(2022, 1, 1), amd.effective_from)
        self.assertIsNone(amd.effective_to)

    # --------------------------------------------------
    # 13. No Fabricated Legal Text
    # --------------------------------------------------

    def test_13_no_fabricated_legal_text(self):
        res = self.service.retrieve(LegalRetrievalQuery(requirement_ids=["test-req-001"]))
        req = res.results[0]
        # Text must exactly match registered test fixture
        self.assertEqual(TEST_FIXTURE_REQ_1["requirement_text"], req.relevant_text)
        self.assertEqual(TEST_FIXTURE_REQ_1["source_quote"], req.source_quote)
        self.assertNotIn("synthetic", req.relevant_text.lower())
        self.assertNotIn("paraphrased", req.relevant_text.lower())

    # --------------------------------------------------
    # 14. Existing Phase 1–3 Behavior Remains Unaffected
    # --------------------------------------------------

    def test_14_existing_phase_1_to_3_behavior_remains_unaffected(self):
        # Check Phase 3 applicability pilot rules can still be built
        from backend.app.services.applicability.pilot_rules import build_all_pilot_rules
        pilot_rules = build_all_pilot_rules()
        self.assertEqual(5, len(pilot_rules))
        for key, pkg in pilot_rules.items():
            self.assertEqual("draft", pkg.status)

        # Check vocabulary remains intact
        from backend.app.services.applicability_vocabulary import FACT_KEYS, SOURCE_ROLES
        self.assertIn("is_prepackaged", FACT_KEYS)
        self.assertIn("condition", SOURCE_ROLES)
        self.assertIn("exception", SOURCE_ROLES)


if __name__ == "__main__":
    unittest.main()

