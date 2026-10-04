from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260829000000_enable_legal_rule_embeddings.sql"
)
MATCH_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260829000001_match_legal_rules.sql"
)


@dataclass(frozen=True)
class EmbeddingColumn:
    exists: bool
    type_schema: str | None = None
    type_name: str | None = None
    type_modifier: int | None = None


@dataclass(frozen=True)
class FunctionCatalogEntry:
    schema: str
    name: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]


def simulated_match_function_action(functions: tuple[FunctionCatalogEntry, ...]) -> str:
    signature = ("extensions.vector", "pg_catalog.int4")
    exists = any(
        function.schema == "public"
        and function.name == "match_legal_rules"
        and function.input_types == signature
        for function in functions
    )
    return "skip existing function" if exists else "create intended function"


def simulated_migration_action(column: EmbeddingColumn) -> str:
    if not column.exists:
        return "add extensions.vector(3072)"
    if (
        column.type_schema == "extensions"
        and column.type_name == "vector"
        and column.type_modifier == 3072
    ):
        return "no-op"
    raise RuntimeError("public.legal_rules.embedding must be vector(3072) for gemini-embedding-001")


class LegalRuleEmbeddingMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.migration = MIGRATION_PATH.read_text(encoding="utf-8")

    def test_missing_embedding_column_is_created_as_vector_3072(self):
        column = EmbeddingColumn(exists=False)
        self.assertEqual("add extensions.vector(3072)", simulated_migration_action(column))
        self.assertRegex(
            self.migration,
            re.compile(r"ADD\s+COLUMN\s+embedding\s+extensions\.vector\(3072\)", re.I),
        )

    def test_existing_extensions_vector_3072_is_a_no_op(self):
        column = EmbeddingColumn(True, "extensions", "vector", 3072)
        self.assertEqual("no-op", simulated_migration_action(column))
        self.assertIn("type_namespace.nspname = 'extensions'", self.migration)
        self.assertIn("type_row.typname = 'vector'", self.migration)
        self.assertIn("column_row.atttypmod = 3072", self.migration)
        self.assertNotIn("3072 + 4", self.migration)

    def test_incompatible_existing_column_fails_without_conversion(self):
        incompatible_columns = (
            EmbeddingColumn(True, "public", "vector", 3072),
            EmbeddingColumn(True, "extensions", "vector", 768),
            EmbeddingColumn(True, "pg_catalog", "text", -1),
        )
        for column in incompatible_columns:
            with self.subTest(column=column):
                with self.assertRaisesRegex(RuntimeError, "must be vector\\(3072\\)"):
                    simulated_migration_action(column)
        self.assertIn("raise exception", self.migration.lower())

    def test_extension_creation_is_idempotent(self):
        self.assertRegex(
            self.migration,
            re.compile(r"CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+vector\s+WITH\s+SCHEMA\s+extensions", re.I),
        )

    def test_migration_cannot_drop_or_rewrite_existing_embeddings(self):
        self.assertNotRegex(self.migration, re.compile(r"\bDROP\s+COLUMN\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\bALTER\s+COLUMN\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\bDELETE\s+FROM\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\bTRUNCATE\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\bUPDATE\s+public\.legal_rules\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\bDROP\s+TABLE\b", re.I))


class MatchLegalRulesMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.migration = MATCH_MIGRATION_PATH.read_text(encoding="utf-8")

    def test_absent_signature_has_creation_path(self):
        self.assertEqual("create intended function", simulated_match_function_action(()))
        self.assertRegex(
            self.migration,
            re.compile(r"IF\s+NOT\s+EXISTS[\s\S]*?EXECUTE\s+\$create_function\$[\s\S]*?CREATE\s+FUNCTION\s+public\.match_legal_rules", re.I),
        )
        self.assertIn("query_embedding extensions.vector(3072)", self.migration)
        self.assertIn("match_count integer default 5", self.migration)

    def test_existing_signature_skips_creation(self):
        existing = FunctionCatalogEntry(
            "public",
            "match_legal_rules",
            ("extensions.vector", "pg_catalog.int4"),
            ("uuid", "text", "text", "text", "text", "text", "double precision"),
        )
        self.assertEqual("skip existing function", simulated_match_function_action((existing,)))
        self.assertIn("function_namespace.nspname = 'public'", self.migration)
        self.assertIn("function_row.proname = 'match_legal_rules'", self.migration)
        self.assertIn("function_row.pronargs = 2", self.migration)
        self.assertIn("function_row.proargtypes[0] = 'extensions.vector'::regtype", self.migration)
        self.assertIn("function_row.proargtypes[1] = 'pg_catalog.int4'::regtype", self.migration)

    def test_existing_uuid_output_shape_is_ignored_and_preserved(self):
        existing = FunctionCatalogEntry(
            "public",
            "match_legal_rules",
            ("extensions.vector", "pg_catalog.int4"),
            ("uuid",),
        )
        self.assertEqual("skip existing function", simulated_match_function_action((existing,)))
        predicate = self.migration.split("if not exists (", 1)[1].split(") then", 1)[0]
        self.assertNotIn("prorettype", predicate)
        self.assertNotIn("proallargtypes", predicate)
        self.assertNotRegex(self.migration, re.compile(r"DROP\s+FUNCTION", re.I))

    def test_no_unconditional_create_or_replace(self):
        self.assertNotRegex(self.migration, re.compile(r"CREATE\s+OR\s+REPLACE\s+FUNCTION", re.I))

    def test_existing_legal_rules_data_and_embeddings_are_not_modified(self):
        self.assertNotRegex(self.migration, re.compile(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE)\s+public\.legal_rules\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\b(DROP|ALTER)\s+COLUMN\s+embedding\b", re.I))
        self.assertNotRegex(self.migration, re.compile(r"\bUPDATE\s+public\.legal_rules\s+SET\s+embedding\b", re.I))


if __name__ == "__main__":
    unittest.main()
