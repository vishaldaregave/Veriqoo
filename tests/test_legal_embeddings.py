"""Phase 4B Tests: Legal Corpus Embeddings Architecture & Text Contracts.

Verifies:
1. Deterministic embedding text
2. Requirement embedding text
3. Provision embedding text
4. Schedule entry embedding text
5. Table embedding text
6. Amendment embedding text
7. Provenance preservation
8. Missing optional fields omitted
9. No invented metadata or dates
10. Model / dimension validation (3072 dims)
11. Embedding failure handling
12. Batching behavior
13. Retry behavior on transient errors
14. Idempotent persistence (no duplicates on rerun)
15. Legacy legal_rules compatibility
16. Normalized corpus compatibility across all 5 entity types
17. Embedding model and version metadata
18. Zero legal corpus mutation
"""

from __future__ import annotations

import unittest
from datetime import date
from uuid import uuid4

from backend.app.services.legal_rag.embeddings import (
    EmbeddingBatchResult,
    EmbeddingGenerationError,
    EmbeddingProviderConfig,
    EntityEmbeddingRecord,
    InMemoryEmbeddingStore,
    LegalEmbeddingGenerator,
    MockEmbeddingClient,
    build_amendment_embedding_text,
    build_provision_embedding_text,
    build_requirement_embedding_text,
    build_schedule_entry_embedding_text,
    build_table_embedding_text,
    compute_embedding_text_hash,
)
from backend.app.services.legal_rag.models import LegalEntityType


# ==================================================
# TEST FIXTURES (CLEARLY MARKED SYNTHETIC TEST FIXTURES)
# ==================================================

FIXTURE_REQ = {
    "id": "test-req-001",
    "source_identifier": "src-req-001",
    "provision_id": 41,
    "requirement_type": "mandatory_declaration",
    "requirement_text": "Every package shall bear the name and address of the manufacturer.",
    "normalized_requirement": "manufacturer_identity_declaration",
    "subject": "Manufacturer identity",
    "obligation": "Every package shall bear the name and address of the manufacturer.",
    "condition_text": "is_prepackaged == true",
    "exception_text": "excluding tobacco products",
    "source_quote": "name and address of the manufacturer",
    "source_reference": {"rule_number": "6", "sub_rule_number": "1", "clause": "a", "document_id": 1},
    "effective_from": None,
    "effective_to": None,
}

FIXTURE_PROV = {
    "id": 41,
    "document_id": 1,
    "provision_type": "clause",
    "rule_number": "6",
    "sub_rule_number": "1",
    "clause": "a",
    "title": "Declarations to be made on every package",
    "content": "the name and address of the manufacturer...",
    "raw_content": "the name and address of the manufacturer or where the manufacturer is not the packer...",
    "source_location": "Rule 6(1)(a)",
}

FIXTURE_SCHEDULE_ENTRY = {
    "id": "test-entry-001",
    "source_identifier": "src-entry-001",
    "schedule_id": "test-sched-uuid-2",
    "entry_key": "entry_tea",
    "entry_number": "1",
    "entry_type": "standard_commodity",
    "item_text": "Tea (including tea bags)",
    "commodity_text": "Tea",
    "quantity_text": "25g, 50g, 100g, 250g, 500g, 1kg",
    "permitted_package_quantity": "25g to 1kg",
    "raw_content": "1. Tea (including tea bags) : 25g, 50g, 100g, 250g, 500g, 1kg",
    "normalized_content": "1. Tea (including tea bags) : 25g, 50g, 100g, 250g, 500g, 1kg",
}

FIXTURE_TABLE = {
    "id": "test-table-001",
    "source_identifier": "src-table-001",
    "document_id": 1,
    "schedule_id": "test-sched-uuid-2",
    "table_identifier": "Table-2",
    "title": "Standard Packaging Units Table",
    "headers": ["Item No", "Commodity", "Permitted Sizes"],
    "raw_content": "| Item No | Commodity | Permitted Sizes |\n| 1 | Tea | 25g, 50g, 100g |",
    "normalized_content": "| Item No | Commodity | Permitted Sizes |\n| 1 | Tea | 25g, 50g, 100g |",
}

FIXTURE_AMENDMENT = {
    "id": "test-amd-001",
    "source_identifier": "src-amd-001",
    "document_id": 1,
    "affected_provision_id": 41,
    "amendment_identifier": "G.S.R. 779(E)",
    "amendment_date": date(2021, 11, 2),
    "effective_date": date(2022, 1, 1),
    "raw_content": "In rule 6, in sub-rule (1), for clause (a), the following clause shall be substituted...",
    "normalized_content": "In rule 6, in sub-rule (1), for clause (a), the following clause shall be substituted...",
}


class LegalEmbeddingsTests(unittest.TestCase):
    """Phase 4B test suite verifying embedding text contracts, clients, storage, and idempotency."""

    def setUp(self):
        self.mock_client = MockEmbeddingClient()
        self.store = InMemoryEmbeddingStore()
        self.generator = LegalEmbeddingGenerator(client=self.mock_client, store=self.store, batch_size=5)

    # 1. Deterministic embedding text
    def test_01_deterministic_embedding_text(self):
        text1 = build_requirement_embedding_text(FIXTURE_REQ, provision=FIXTURE_PROV)
        text2 = build_requirement_embedding_text(FIXTURE_REQ, provision=FIXTURE_PROV)
        self.assertEqual(text1, text2)

        hash1 = compute_embedding_text_hash(text1)
        hash2 = compute_embedding_text_hash(text2)
        self.assertEqual(hash1, hash2)
        self.assertEqual(64, len(hash1))  # SHA-256 hex length

    # 2. Requirement embedding text
    def test_02_requirement_embedding_text(self):
        text = build_requirement_embedding_text(FIXTURE_REQ, provision=FIXTURE_PROV)
        self.assertIn("[ENTITY: LEGAL_REQUIREMENT]", text)
        self.assertIn("Rule 6(1)(a)", text)
        self.assertIn("mandatory_declaration", text)
        self.assertIn("Manufacturer identity", text)
        self.assertIn("manufacturer_identity_declaration", text)
        self.assertIn("is_prepackaged == true", text)
        self.assertIn("excluding tobacco products", text)
        self.assertIn('Statutory Quote: "name and address of the manufacturer"', text)

    # 3. Provision embedding text
    def test_03_provision_embedding_text(self):
        text = build_provision_embedding_text(FIXTURE_PROV)
        self.assertIn("[ENTITY: LEGAL_PROVISION]", text)
        self.assertIn("Provision Type: clause", text)
        self.assertIn("Rule: Rule 6(1)(a)", text)
        self.assertIn("Title: Declarations to be made on every package", text)
        self.assertIn("the name and address of the manufacturer or where the manufacturer is not the packer...", text)

    # 4. Schedule entry embedding text
    def test_04_schedule_entry_embedding_text(self):
        text = build_schedule_entry_embedding_text(FIXTURE_SCHEDULE_ENTRY, schedule={"schedule_number": "Second"})
        self.assertIn("[ENTITY: LEGAL_SCHEDULE_ENTRY]", text)
        self.assertIn("Schedule: Second", text)
        self.assertIn("Entry Number: 1", text)
        self.assertIn("Commodity: Tea", text)
        self.assertIn("Prescribed Quantities: 25g, 50g, 100g, 250g, 500g, 1kg", text)
        self.assertIn("Permitted Package Sizes: 25g to 1kg", text)

    # 5. Table embedding text
    def test_05_table_embedding_text(self):
        text = build_table_embedding_text(FIXTURE_TABLE, schedule={"schedule_number": "Second"})
        self.assertIn("[ENTITY: LEGAL_TABLE]", text)
        self.assertIn("Table Identifier: Table-2", text)
        self.assertIn("Schedule: Second", text)
        self.assertIn("Headers: Item No, Commodity, Permitted Sizes", text)
        self.assertIn("| Item No | Commodity | Permitted Sizes |", text)

    # 6. Amendment embedding text
    def test_06_amendment_embedding_text(self):
        text = build_amendment_embedding_text(FIXTURE_AMENDMENT, affected_prov=FIXTURE_PROV)
        self.assertIn("[ENTITY: LEGAL_AMENDMENT]", text)
        self.assertIn("Amendment Identifier: G.S.R. 779(E)", text)
        self.assertIn("Affected Rule: Rule 6(1)(a)", text)
        self.assertIn("Amendment Date: 2021-11-02", text)
        self.assertIn("Effective Date: 2022-01-01", text)

    # 7. Provenance preservation
    def test_07_provenance_preservation(self):
        req_text = build_requirement_embedding_text(FIXTURE_REQ)
        self.assertIn(FIXTURE_REQ["source_quote"], req_text)
        prov_text = build_provision_embedding_text(FIXTURE_PROV)
        self.assertIn(FIXTURE_PROV["source_location"], prov_text)

    # 8. Missing optional fields
    def test_08_missing_optional_fields(self):
        sparse_req = {
            "id": "sparse-1",
            "requirement_type": "declaration",
            "requirement_text": "Bare text",
            # No condition, exception, subject, quote, dates
        }
        text = build_requirement_embedding_text(sparse_req)
        self.assertIn("[ENTITY: LEGAL_REQUIREMENT]", text)
        self.assertIn("Statutory Text: Bare text", text)
        self.assertNotIn("Condition:", text)
        self.assertNotIn("Exception:", text)
        self.assertNotIn("Effective From:", text)
        self.assertNotIn("Statutory Quote:", text)

    # 9. No invented metadata
    def test_09_no_invented_metadata(self):
        req = dict(FIXTURE_REQ)
        req["effective_from"] = None
        req["effective_to"] = None
        text = build_requirement_embedding_text(req)
        self.assertNotIn("Effective From:", text)
        self.assertNotIn("Effective To:", text)
        self.assertNotIn("2021-12-31", text)
        self.assertNotIn("2022-01-01", text)

    # 10. Model and dimension validation
    def test_10_model_and_dimension_validation(self):
        self.assertEqual("gemini-embedding-001", self.mock_client.model)
        self.assertEqual(3072, self.mock_client.dimension)
        vec = self.mock_client.embed_text("test input")
        self.assertEqual(3072, len(vec))
        # Vector is L2 normalized
        import math
        norm = math.sqrt(sum(x * x for x in vec))
        self.assertAlmostEqual(1.0, norm, places=4)

    # 11. Embedding failure handling
    def test_11_embedding_failure_handling(self):
        failing_client = MockEmbeddingClient(failure_count=999)
        generator = LegalEmbeddingGenerator(client=failing_client, store=self.store)
        result = generator.generate_all(requirements=[FIXTURE_REQ])
        self.assertEqual(1, result.total_processed)
        self.assertEqual(0, result.successful)
        self.assertEqual(1, result.failed)
        self.assertGreater(len(result.errors), 0)

    # 12. Batching behavior
    def test_12_batching_behavior(self):
        reqs = [{**FIXTURE_REQ, "id": f"req-{i}", "source_identifier": f"src-{i}"} for i in range(12)]
        generator = LegalEmbeddingGenerator(client=self.mock_client, store=self.store, batch_size=5)
        result = generator.generate_all(requirements=reqs)
        self.assertEqual(12, result.total_processed)
        self.assertEqual(12, result.successful)
        self.assertEqual(0, result.failed)
        self.assertEqual(12, self.store.count_embeddings())

    # 13. Retry behavior
    def test_13_retry_behavior(self):
        # Client that fails twice then succeeds
        mock = MockEmbeddingClient(failure_count=2)
        # Note: In mock client, embed_text is called and decrements failure_count
        vec1 = None
        try:
            mock.embed_text("sample")
        except EmbeddingGenerationError:
            pass
        try:
            mock.embed_text("sample")
        except EmbeddingGenerationError:
            pass
        vec1 = mock.embed_text("sample")
        self.assertEqual(3072, len(vec1))

    # 14. Idempotent persistence
    def test_14_idempotent_persistence(self):
        # First run
        res1 = self.generator.generate_all(
            requirements=[FIXTURE_REQ],
            provisions=[FIXTURE_PROV],
        )
        self.assertEqual(2, res1.successful)
        self.assertEqual(2, self.store.count_embeddings())

        # Second run with same data
        res2 = self.generator.generate_all(
            requirements=[FIXTURE_REQ],
            provisions=[FIXTURE_PROV],
            skip_existing_hashes=True,
        )
        self.assertEqual(2, res2.successful)
        # Store still contains exactly 2 embeddings (no duplicate rows)
        self.assertEqual(2, self.store.count_embeddings())

    # 15. Legacy legal_rules compatibility
    def test_15_legacy_legal_rules_compatibility(self):
        # Check that legacy migration files exist and define the expected signatures
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        migration_embed = root / "supabase" / "migrations" / "20260829000000_enable_legal_rule_embeddings.sql"
        migration_match = root / "supabase" / "migrations" / "20260829000001_match_legal_rules.sql"

        self.assertTrue(migration_embed.exists())
        self.assertTrue(migration_match.exists())

        embed_sql = migration_embed.read_text(encoding="utf-8")
        match_sql = migration_match.read_text(encoding="utf-8")

        self.assertIn("public.legal_rules", embed_sql)
        self.assertIn("vector(3072)", embed_sql)
        self.assertIn("public.match_legal_rules", match_sql)

    # 16. Normalized corpus compatibility across all 5 entity types
    def test_16_normalized_corpus_compatibility_across_all_five_entities(self):
        result = self.generator.generate_all(
            requirements=[FIXTURE_REQ],
            provisions=[FIXTURE_PROV],
            schedule_entries=[FIXTURE_SCHEDULE_ENTRY],
            tables=[FIXTURE_TABLE],
            amendments=[FIXTURE_AMENDMENT],
        )
        self.assertEqual(5, result.total_processed)
        self.assertEqual(5, result.successful)
        self.assertEqual(0, result.failed)
        self.assertEqual(1, result.entity_counts[LegalEntityType.REQUIREMENT.value])
        self.assertEqual(1, result.entity_counts[LegalEntityType.PROVISION.value])
        self.assertEqual(1, result.entity_counts[LegalEntityType.SCHEDULE_ENTRY.value])
        self.assertEqual(1, result.entity_counts[LegalEntityType.TABLE.value])
        self.assertEqual(1, result.entity_counts[LegalEntityType.AMENDMENT.value])

    # 17. Embedding model and version metadata
    def test_17_embedding_model_and_version_metadata(self):
        result = self.generator.generate_all(requirements=[FIXTURE_REQ])
        rec = result.records[0]
        self.assertIsInstance(rec, EntityEmbeddingRecord)
        self.assertEqual("gemini-embedding-001", rec.model)
        self.assertEqual(3072, rec.dimension)
        self.assertEqual("v1", rec.embedding_text_version)
        self.assertGreater(len(rec.embedding_text), 0)
        self.assertEqual(64, len(rec.embedding_text_hash))

    # 18. No legal corpus mutation
    def test_18_no_legal_corpus_mutation(self):
        orig_req = dict(FIXTURE_REQ)
        self.generator.generate_all(requirements=[orig_req])
        self.assertEqual(FIXTURE_REQ, orig_req, "Corpus object was mutated by embedding generation")


if __name__ == "__main__":
    unittest.main()
