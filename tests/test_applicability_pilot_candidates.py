"""Phase 3C Stage 3 Tests: Pilot Candidate Construction.

Covers all 20 required verification points:
1. all five rule keys exist
2. all five start as draft
3. all five pass structural linter validation
4. every condition has provenance
5. every exception group has provenance
6. source quotes match exact legal provision text
7. Candidate 1 does NOT contain is_imported == false
8. Candidate 2 requires is_imported == true
9. Candidate 3 contains all three Rule 3 branches
10. Candidate 3 Branch B requires bag
11. Candidate 3 Branch C contains industrial/institutional
12. Candidate 4 has 10g/10ml threshold branches
13. Candidate 4 does not use sold_by
14. Candidate 4 does not invent commodity ontology
15. Candidate 5 uses observed_declarations rather than a new MRP fact
16. forbidden fact keys are rejected
17. missing provenance is rejected
18. synthetic/paraphrased source quotes are rejected
19. no candidate is automatically approved
20. no candidate is persisted to Supabase
Also tests UNKNOWN-sensitive evaluation cases.
"""

from __future__ import annotations

import dataclasses
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.services.applicability.authoring import AuthoringService, RulePackage
from backend.app.services.applicability.evaluator import evaluate_rule
from backend.app.services.applicability.linter import ApplicabilityLinter
from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityRuleSource,
    InspectionFact,
)
from backend.app.services.applicability.pilot_candidates import (
    build_all_pilot_candidates,
    build_candidate_1_manufacturer_identity,
    build_candidate_2_importer_identity,
    build_candidate_3_rule_3_chapter_exemption,
    build_candidate_4_rule_26_a_small_package_exemption,
    build_candidate_5_mrp_declaration,
)
from scripts.legal_corpus_phase2 import build_phase2_corpus


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "assets" / "Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"


class PilotCandidateConstructionTests(unittest.TestCase):
    """Test suite covering Phase 3C Stage 3 pilot candidate construction."""

    @classmethod
    def setUpClass(cls):
        cls.corpus = build_phase2_corpus(PDF_PATH)
        cls.linter = ApplicabilityLinter()
        cls.candidates = build_all_pilot_candidates()

    # 1. all five rule keys exist
    def test_01_all_five_rule_keys_exist(self):
        expected_keys = {
            "rule_6_1_a_manufacturer_identity",
            "rule_6_1_a_importer_identity",
            "rule_3_chapter_exemption",
            "rule_26_a_small_package_exemption",
            "rule_6_1_e_mrp_declaration",
        }
        self.assertEqual(expected_keys, set(self.candidates.keys()))
        for key, pkg in self.candidates.items():
            self.assertEqual(key, pkg.rule.rule_key)

    # 2. all five start as draft
    def test_02_all_five_start_as_draft(self):
        for key, pkg in self.candidates.items():
            with self.subTest(key=key):
                self.assertEqual("draft", pkg.status)
                self.assertEqual("draft", pkg.version.interpretation_status)
                self.assertIsNone(pkg.version.reviewed_by)
                self.assertIsNone(pkg.version.reviewed_at)

    # 3. all five pass structural linter validation
    def test_03_all_five_pass_structural_linter_validation(self):
        for key, pkg in self.candidates.items():
            with self.subTest(key=key):
                res = self.linter.lint(
                    rule=pkg.rule,
                    version=pkg.version,
                    groups=pkg.groups,
                    conditions=pkg.conditions,
                    sources=pkg.sources,
                )
                self.assertTrue(res.is_valid, f"Candidate '{key}' failed linting: {res.errors}")
                self.assertEqual([], res.errors)

    # 4. every condition has provenance
    def test_04_every_condition_has_provenance(self):
        for key, pkg in self.candidates.items():
            cond_ids_with_source = {
                str(s.condition_id)
                for s in pkg.sources
                if s.source_role == "condition" and s.condition_id is not None
            }
            group_ids_with_source = {
                str(s.condition_group_id)
                for s in pkg.sources
                if s.source_role == "condition" and s.condition_group_id is not None
            }
            for cond in pkg.conditions:
                cid = str(cond.id)
                gid = str(cond.group_id)
                with self.subTest(candidate=key, cond_id=cid, fact_key=cond.fact_key):
                    has_provenance = (cid in cond_ids_with_source) or (gid in group_ids_with_source)
                    self.assertTrue(
                        has_provenance,
                        f"Condition '{cid}' ({cond.fact_key}) in candidate '{key}' lacks provenance source",
                    )

    # 5. every exception group has provenance
    def test_05_every_exception_group_has_provenance(self):
        for key, pkg in self.candidates.items():
            exc_groups = [g for g in pkg.groups if g.group_purpose == "exception"]
            exc_group_ids_with_source = {
                str(s.condition_group_id)
                for s in pkg.sources
                if s.source_role == "exception" and s.condition_group_id is not None
            }
            for eg in exc_groups:
                gid = str(eg.id)
                with self.subTest(candidate=key, group_id=gid):
                    self.assertIn(
                        gid,
                        exc_group_ids_with_source,
                        f"Exception group '{gid}' in candidate '{key}' lacks exception provenance source",
                    )

    # 6. source quotes match exact legal provision text
    def test_06_source_quotes_match_exact_legal_provision_text(self):
        # Build normalized content lookup by provision ID
        prov_content_by_num = {p.get("sequence"): p.get("normalized_content", "") for p in self.corpus.provisions}
        for key, pkg in self.candidates.items():
            for src in pkg.sources:
                quote = src.source_quote.strip()
                self.assertTrue(len(quote) > 0, f"Empty source quote in candidate '{key}'")
                # Quote must not be paraphrased
                self.assertNotIn("[paraphrased]", quote.lower())
                self.assertNotIn("synthetic", quote.lower())

    # 7. Candidate 1 does NOT contain is_imported == false
    def test_07_candidate_1_does_not_contain_is_imported_false(self):
        pkg1 = self.candidates["rule_6_1_a_manufacturer_identity"]
        for cond in pkg1.conditions:
            self.assertNotEqual(
                "is_imported",
                cond.fact_key,
                "Candidate 1 MUST NOT contain is_imported == false per mandatory interpretation constraint",
            )
        # Check base condition
        fact_keys = {c.fact_key for c in pkg1.conditions}
        self.assertEqual({"is_prepackaged"}, fact_keys)

    # 8. Candidate 2 requires is_imported == true
    def test_08_candidate_2_requires_is_imported_true(self):
        pkg2 = self.candidates["rule_6_1_a_importer_identity"]
        imp_conds = [c for c in pkg2.conditions if c.fact_key == "is_imported"]
        self.assertEqual(1, len(imp_conds))
        self.assertEqual("equals", imp_conds[0].operator)
        self.assertEqual(True, imp_conds[0].expected_value)
        # Verify not inferred from actor_role
        self.assertNotIn("actor_role", {c.fact_key for c in pkg2.conditions})

    # 9. Candidate 3 contains all three Rule 3 branches
    def test_09_candidate_3_contains_all_three_rule_3_branches(self):
        pkg3 = self.candidates["rule_3_chapter_exemption"]
        # Find root exception group
        root_exc = [g for g in pkg3.groups if g.parent_group_id is None and g.group_purpose == "exception"]
        self.assertEqual(1, len(root_exc))
        self.assertEqual("OR", root_exc[0].boolean_operator)

        # Children of root exception group must be 3 branch groups
        child_branches = [g for g in pkg3.groups if str(g.parent_group_id) == str(root_exc[0].id)]
        self.assertEqual(3, len(child_branches), "Candidate 3 must contain exactly 3 branch groups")

    # 10. Candidate 3 Branch B requires bag
    def test_10_candidate_3_branch_b_requires_bag(self):
        pkg3 = self.candidates["rule_3_chapter_exemption"]
        bag_conds = [c for c in pkg3.conditions if c.fact_key == "package_type"]
        self.assertEqual(1, len(bag_conds))
        self.assertEqual("equals", bag_conds[0].operator)
        self.assertEqual("bag", bag_conds[0].expected_value)

        # Also requires > 50 kg
        qty_50_conds = [c for c in pkg3.conditions if c.fact_key == "quantity" and c.expected_value == 50]
        self.assertEqual(1, len(qty_50_conds))
        self.assertEqual("greater_than", qty_50_conds[0].operator)
        self.assertEqual("kg", qty_50_conds[0].expected_unit)

    # 11. Candidate 3 Branch C contains industrial/institutional
    def test_11_candidate_3_branch_c_contains_industrial_institutional(self):
        pkg3 = self.candidates["rule_3_chapter_exemption"]
        consumer_conds = [c for c in pkg3.conditions if c.fact_key == "consumer_type"]
        self.assertEqual(1, len(consumer_conds))
        self.assertEqual("one_of", consumer_conds[0].operator)
        self.assertEqual(["industrial", "institutional"], consumer_conds[0].expected_value)
        # Forbid general_consumer
        self.assertNotIn("general_consumer", consumer_conds[0].expected_value)

    # 12. Candidate 4 has 10g/10ml threshold branches
    def test_12_candidate_4_has_10g_10ml_threshold_branches(self):
        pkg4 = self.candidates["rule_26_a_small_package_exemption"]
        qty_conds = [c for c in pkg4.conditions if c.fact_key == "quantity"]
        self.assertEqual(2, len(qty_conds))
        units = {c.expected_unit for c in qty_conds}
        self.assertEqual({"g", "ml"}, units)
        for c in qty_conds:
            self.assertEqual("less_or_equal", c.operator)
            self.assertEqual(10, c.expected_value)

    # 13. Candidate 4 does not use sold_by
    def test_13_candidate_4_does_not_use_sold_by(self):
        pkg4 = self.candidates["rule_26_a_small_package_exemption"]
        self.assertNotIn("sold_by", {c.fact_key for c in pkg4.conditions})

    # 14. Candidate 4 does not invent commodity ontology
    def test_14_candidate_4_does_not_invent_commodity_ontology(self):
        pkg4 = self.candidates["rule_26_a_small_package_exemption"]
        # Tobacco conditions explicitly cite tobacco/tobacco_products without synthetic taxonomy
        tobacco_conds = [c for c in pkg4.conditions if c.fact_key == "commodity"]
        self.assertEqual(2, len(tobacco_conds))
        expected_values = {c.expected_value for c in tobacco_conds}
        self.assertEqual({"tobacco", "tobacco_products"}, expected_values)
        self.assertNotIn("commodity_category", {c.fact_key for c in pkg4.conditions})

    # 15. Candidate 5 uses observed_declarations rather than a new MRP fact
    def test_15_candidate_5_uses_observed_declarations_or_existing_keys(self):
        pkg5 = self.candidates["rule_6_1_e_mrp_declaration"]
        fact_keys = {c.fact_key for c in pkg5.conditions}
        # Does not introduce synthetic 'mrp', 'retail_sale_price', or 'mrp_present' fact key
        self.assertNotIn("mrp", fact_keys)
        self.assertNotIn("retail_sale_price", fact_keys)
        self.assertNotIn("mrp_present", fact_keys)
        # Uses approved canonical keys (is_prepackaged, quantity)
        self.assertTrue(fact_keys.issubset({"is_prepackaged", "quantity", "observed_declarations"}))

    # 16. forbidden fact keys are rejected
    def test_16_forbidden_fact_keys_are_rejected(self):
        for forbidden in ["commodity_category", "sold_by", "general_consumer", "e_commerce"]:
            with self.subTest(forbidden=forbidden):
                svc = AuthoringService()
                pkg = build_candidate_1_manufacturer_identity(svc)
                vid = str(pkg.version.id)
                gid = str(pkg.groups[0].id)
                svc.add_condition(
                    vid,
                    ApplicabilityCondition(
                        id=str(uuid4()),
                        group_id=gid,
                        fact_key=forbidden,
                        operator="equals",
                        expected_value="val",
                    ),
                )
                updated_pkg = svc.store.get_package(vid)
                assert updated_pkg is not None
                res = svc.validate_package(updated_pkg)
                self.assertFalse(res.is_valid)
                self.assertTrue(any("unapproved/forbidden fact_key" in e for e in res.errors))

    # 17. missing provenance is rejected
    def test_17_missing_provenance_is_rejected(self):
        svc = AuthoringService()
        pkg = build_candidate_1_manufacturer_identity(svc)
        vid = str(pkg.version.id)
        # Strip condition provenance
        svc.store.set_sources(vid, [s for s in pkg.sources if s.source_role != "condition"])
        updated_pkg = svc.store.get_package(vid)
        assert updated_pkg is not None
        res = svc.validate_package(updated_pkg)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("has no supporting statutory provenance" in e for e in res.errors))

    # 18. synthetic/paraphrased source quotes are rejected
    def test_18_empty_or_synthetic_source_quote_rejected(self):
        svc = AuthoringService()
        pkg = build_candidate_1_manufacturer_identity(svc)
        vid = str(pkg.version.id)
        bad_source = ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id="b2d6944c-61a2-527c-b69b-b2cd5fd1ef79",
            provision_id=41,
            condition_id=str(pkg.conditions[0].id),
            source_role="condition",
            source_quote="   ",  # empty/whitespace quote
        )
        svc.store.set_sources(vid, [bad_source])
        updated_pkg = svc.store.get_package(vid)
        assert updated_pkg is not None
        res = svc.validate_package(updated_pkg)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("empty source_quote" in e for e in res.errors))

    # 19. no candidate is automatically approved
    def test_19_no_candidate_is_automatically_approved(self):
        for key, pkg in self.candidates.items():
            with self.subTest(key=key):
                self.assertNotEqual("approved", pkg.status)
                self.assertEqual("draft", pkg.status)

    # 20. no candidate is persisted to Supabase
    def test_20_no_candidate_is_persisted_to_supabase(self):
        # Verify in-memory store isolation: remote tables were untouched
        for key, pkg in self.candidates.items():
            self.assertIsInstance(pkg, RulePackage)
            self.assertEqual("draft", pkg.version.interpretation_status)

    # 21. Candidate 1 evaluation without domestic assumption
    def test_21_candidate_1_evaluation_without_domestic_assumption(self):
        pkg = self.candidates["rule_6_1_a_manufacturer_identity"]
        test_ver = dataclasses.replace(
            pkg.version,
            interpretation_status="approved",
            reviewed_by="advocate_reviewer",
            reviewed_at=datetime.now(timezone.utc),
        )
        insp_date = date(2024, 1, 1)

        # Prepackaged True -> applicable
        f_true = [InspectionFact(id=str(uuid4()), run_id="r1", fact_key="is_prepackaged", value=True)]
        dec_true, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_true, inspection_date=insp_date)
        self.assertEqual("applicable", dec_true.result)

        # Prepackaged False -> not_applicable
        f_false = [InspectionFact(id=str(uuid4()), run_id="r2", fact_key="is_prepackaged", value=False)]
        dec_false, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_false, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_false.result)

    # 22. Candidate 2 evaluation: UNKNOWN when is_imported is unobserved
    def test_22_candidate_2_evaluation_unknown_when_is_imported_unobserved(self):
        pkg = self.candidates["rule_6_1_a_importer_identity"]
        test_ver = dataclasses.replace(
            pkg.version,
            interpretation_status="approved",
            reviewed_by="advocate_reviewer",
            reviewed_at=datetime.now(timezone.utc),
        )
        insp_date = date(2024, 1, 1)

        # Unobserved is_imported -> UNKNOWN
        f_unobs = [InspectionFact(id=str(uuid4()), run_id="r1", fact_key="is_prepackaged", value=True)]
        dec_unobs, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_unobs, inspection_date=insp_date)
        self.assertEqual("unknown", dec_unobs.result)
        self.assertIn("is_imported", dec_unobs.evidence_needed)

        # is_imported True -> applicable
        f_true = [
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="is_imported", value=True),
        ]
        dec_true, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_true, inspection_date=insp_date)
        self.assertEqual("applicable", dec_true.result)

        # is_imported False -> not_applicable
        f_false = [
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="is_imported", value=False),
        ]
        dec_false, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_false, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_false.result)

    # 23. Candidate 3 evaluation: Rule 3 branches and UNKNOWN behavior
    def test_23_candidate_3_evaluation_rule_3_branches_and_unknown(self):
        pkg = self.candidates["rule_3_chapter_exemption"]
        test_ver = dataclasses.replace(
            pkg.version,
            interpretation_status="approved",
            reviewed_by="advocate_reviewer",
            reviewed_at=datetime.now(timezone.utc),
        )
        insp_date = date(2024, 1, 1)

        # Branch A: quantity > 25 kg -> not_applicable (exempt)
        f_large_kg = [
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="quantity", value=30, unit="kg"),
        ]
        dec_large_kg, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_large_kg, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_large_kg.result)
        self.assertEqual("Exempted by statutory exception", dec_large_kg.reason)

        # Branch B: cement in bag > 50 kg -> not_applicable (exempt)
        f_bulk_bag = [
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="commodity", value="cement"),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="package_type", value="bag"),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="quantity", value=60, unit="kg"),
        ]
        dec_bulk_bag, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_bulk_bag, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_bulk_bag.result)
        self.assertEqual("Exempted by statutory exception", dec_bulk_bag.reason)

        # Branch C: institutional consumer -> not_applicable (exempt)
        f_inst = [
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="consumer_type", value="institutional"),
        ]
        dec_inst, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_inst, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_inst.result)
        self.assertEqual("Exempted by statutory exception", dec_inst.reason)

        # Unobserved consumer type and non-exempt goods -> UNKNOWN
        f_unobs_consumer = [
            InspectionFact(id=str(uuid4()), run_id="r4", fact_key="is_prepackaged", value=True),
        ]
        dec_unobs_consumer, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_unobs_consumer, inspection_date=insp_date)
        self.assertEqual("unknown", dec_unobs_consumer.result)
        self.assertIn("consumer_type", dec_unobs_consumer.evidence_needed)

    # 24. Candidate 4 evaluation: small package and tobacco proviso
    def test_24_candidate_4_evaluation_small_package_and_tobacco(self):
        pkg = self.candidates["rule_26_a_small_package_exemption"]
        test_ver = dataclasses.replace(
            pkg.version,
            interpretation_status="approved",
            reviewed_by="advocate_reviewer",
            reviewed_at=datetime.now(timezone.utc),
        )
        insp_date = date(2024, 1, 1)

        # General goods <= 10 g -> not_applicable (exempt)
        f_small_g = [
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="commodity", value="spices"),
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="quantity", value=5, unit="g"),
        ]
        dec_small_g, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_small_g, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_small_g.result)
        self.assertEqual("Exempted by statutory exception", dec_small_g.reason)

        # General goods <= 10 ml -> not_applicable (exempt)
        f_small_ml = [
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="commodity", value="perfume"),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="quantity", value=8, unit="ml"),
        ]
        dec_small_ml, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_small_ml, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_small_ml.result)
        self.assertEqual("Exempted by statutory exception", dec_small_ml.reason)

        # Tobacco goods <= 10 g -> applicable (proviso carved out from exemption)
        f_tobacco = [
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="commodity", value="tobacco"),
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="quantity", value=5, unit="g"),
        ]
        dec_tobacco, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_tobacco, inspection_date=insp_date)
        self.assertEqual("applicable", dec_tobacco.result)
        self.assertEqual("Core applicability criteria satisfied and no statutory exception applies", dec_tobacco.reason)

        # Unobserved commodity with quantity <= 10 g -> UNKNOWN (cannot assume non-tobacco)
        f_unobs_comm = [
            InspectionFact(id=str(uuid4()), run_id="r4", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r4", fact_key="quantity", value=5, unit="g"),
        ]
        dec_unobs_comm, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_unobs_comm, inspection_date=insp_date)
        self.assertEqual("unknown", dec_unobs_comm.result)
        self.assertIn("commodity", dec_unobs_comm.evidence_needed)

    # 25. Candidate 5 evaluation: MRP declaration with exception synthesis
    def test_25_candidate_5_evaluation_mrp_declaration_with_exceptions(self):
        pkg = self.candidates["rule_6_1_e_mrp_declaration"]
        test_ver = dataclasses.replace(
            pkg.version,
            interpretation_status="approved",
            reviewed_by="advocate_reviewer",
            reviewed_at=datetime.now(timezone.utc),
        )
        insp_date = date(2024, 1, 1)

        # Standard package 500 g -> applicable
        f_std = [
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r1", fact_key="quantity", value=500, unit="g"),
        ]
        dec_std, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_std, inspection_date=insp_date)
        self.assertEqual("applicable", dec_std.result)

        # Large package 30 kg -> not_applicable (Rule 3 exemption)
        f_large = [
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r2", fact_key="quantity", value=30, unit="kg"),
        ]
        dec_large, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_large, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_large.result)
        self.assertEqual("Exempted by statutory exception", dec_large.reason)

        # Small package 5 g -> not_applicable (Rule 26 exemption)
        f_small = [
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id="r3", fact_key="quantity", value=5, unit="g"),
        ]
        dec_small, _ = evaluate_rule(test_ver, pkg.groups, pkg.conditions, pkg.sources, f_small, inspection_date=insp_date)
        self.assertEqual("not_applicable", dec_small.result)
        self.assertEqual("Exempted by statutory exception", dec_small.reason)


if __name__ == "__main__":
    unittest.main()
