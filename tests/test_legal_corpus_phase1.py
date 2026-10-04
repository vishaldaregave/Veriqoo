import unittest
from pathlib import Path
import re

from scripts.legal_corpus_parser import generate_coverage_report, parse_document


PDF_PATH = Path(__file__).resolve().parents[1] / "assets" / "Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"


class LegalCorpusPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = parse_document(PDF_PATH)

    def test_rule_1_detected(self):
        rule_1 = self.document.get_rule("1")
        self.assertIsNotNone(rule_1)
        self.assertTrue(rule_1.title)
        self.assertTrue(rule_1.content)

    def test_rule_31_detected(self):
        rule_31 = self.document.get_rule("31")
        self.assertIsNotNone(rule_31)
        self.assertIn("advertisement", (rule_31.raw_content or "").lower())

    def test_all_top_level_rule_numbers_detected(self):
        detected = {rule.rule_number for rule in self.document.rules}
        self.assertTrue({str(number) for number in range(1, 35)}.issubset(detected))

    def test_zero_padded_rule_number_normalizes_without_duplicate(self):
        self.assertEqual("1", self.document.get_rule("01").rule_number)
        normalized_numbers = [str(int(rule.rule_number)) if rule.rule_number.isdigit() else rule.rule_number for rule in self.document.rules]
        self.assertEqual(1, normalized_numbers.count("1"))
        rule_1 = self.document.get_rule("1")
        self.assertEqual("Short title, and Commencement.-", rule_1.title)
        self.assertIn("Legal Metrology (Packaged Commodities) Rules", rule_1.raw_content)
        self.assertTrue(rule_1.source_location)
        self.assertTrue(rule_1.children)
        self.assertTrue(
            all(
                child.parent_provision_id == rule_1.provision_id and child.rule_number == "1"
                for child in rule_1.children
            )
        )

    def test_rule_32a_is_preserved(self):
        rule_32a = self.document.get_rule("32A")
        self.assertIsNotNone(rule_32a)
        self.assertIn("compounding of offences", rule_32a.raw_content.lower())

    def test_rules_1_through_34_are_complete_without_duplicate_rule_1(self):
        numbers = [str(int(rule.rule_number)) if rule.rule_number.isdigit() else rule.rule_number for rule in self.document.rules]
        self.assertTrue({str(number) for number in range(1, 35)}.issubset(set(numbers)))
        self.assertEqual(1, numbers.count("1"))

    def test_sub_rule_parsing(self):
        rule_6 = self.document.get_rule("6")
        self.assertIsNotNone(rule_6)
        self.assertTrue(any(child.provision_type == "sub_rule" for child in rule_6.children))

    def test_clause_parsing(self):
        clause_nodes = [p for p in self.document.provisions if p.provision_type == "clause"]
        self.assertTrue(clause_nodes)

    def test_proviso_parsing(self):
        provisos = [p for p in self.document.provisions if p.provision_type == "proviso"]
        self.assertTrue(provisos)

    def test_explanation_parsing(self):
        explanations = [p for p in self.document.provisions if p.provision_type == "explanation"]
        self.assertTrue(explanations)

    def test_schedule_detection(self):
        self.assertTrue(self.document.schedules)
        self.assertTrue(any(schedule.title for schedule in self.document.schedules))

    def test_table_detection(self):
        self.assertTrue(any(table for table in self.document.tables))

    def test_parent_child_relationships(self):
        child_with_parent = next(
            (p for p in self.document.provisions if p.parent_provision_id is not None),
            None,
        )
        self.assertIsNotNone(child_with_parent)
        self.assertIsNotNone(child_with_parent.parent_provision_id)

    def test_amendment_text_preserved(self):
        self.assertTrue(self.document.amendments)
        self.assertTrue(
            any("Substituted" in text or "amended" in text.lower() for text in self.document.amendments)
        )

    def test_no_keyword_based_dropping(self):
        self.assertGreater(len(self.document.provisions), 200)
        self.assertIsNotNone(self.document.get_rule("31"))
        self.assertTrue(any(schedule.schedule_number for schedule in self.document.schedules))

    def test_coverage_report_has_expected_sections(self):
        report = generate_coverage_report(self.document)
        self.assertIn("rules_detected", report)
        self.assertIn("missing_rules", report)
        self.assertIn("schedules", report)
        self.assertIn("tables", report)
        self.assertIn("amendment_blocks", report)
        self.assertGreaterEqual(report["rules_detected"], 30)

    def test_new_migration_has_no_destructive_referential_actions(self):
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "supabase"
            / "migrations"
            / "20261002000000_legal_corpus_hierarchy.sql"
        )
        migration = migration_path.read_text(encoding="utf-8")
        self.assertNotRegex(migration, re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE))
        self.assertNotRegex(migration, re.compile(r"\bDELETE\b", re.IGNORECASE))
        self.assertNotRegex(migration, re.compile(r"\bTRUNCATE\b", re.IGNORECASE))
        self.assertNotRegex(migration, re.compile(r"\bON\s+DELETE\s+(?:CASCADE|SET\s+NULL)\b", re.IGNORECASE))
        self.assertNotIn("legal_rules", migration)


if __name__ == "__main__":
    unittest.main()
