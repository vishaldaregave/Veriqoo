"""Synthetic in-memory test suite for Phase 3B Applicability Evaluation Engine.

Covers all 35 required scenarios:
1. equals
2. not_equals
3. one_of
4. greater_than
5. greater_or_equal
6. less_than
7. less_or_equal
8. range_inclusive
9. exists (known, unknown, not_observed, not_applicable, missing)
10. AND
11. OR
12. nested groups
13. AND UNKNOWN semantics
14. OR UNKNOWN semantics
15. missing fact
16. not_observed
17. not_applicable
18. exception true
19. exception unknown
20. draft rejection
21. in_review rejection
22. rejected rejection
23. retired rejection
24. approved evaluation
25. temporal selection
26. temporal ambiguity
27. root/cycle validation
28. unit registry + cross-dimension rejection
29. duplicate identical facts
30. conflicting duplicate facts
31. malformed operator
32. unrecognized unit
33. unreviewed conversion
34. Decimal boundary precision
35. service evaluate run

Enforces complete test isolation: zero database I/O, purely synthetic rules.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from backend.app.services.applicability import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityDecision,
    ApplicabilityDecisionEvidence,
    ApplicabilityRule,
    ApplicabilityRuleSource,
    ApplicabilityRuleVersion,
    ApplicabilityRun,
    ApplicabilityService,
    InspectionFact,
    TriState,
    convert_quantity,
    evaluate_condition,
    evaluate_rule,
    filter_approved_versions,
    select_temporal_version,
    validate_group_hierarchy,
)


def make_synth_rule(rule_key: str = "SYNTH_RULE_01") -> tuple[ApplicabilityRule, ApplicabilityRuleVersion]:
    rule_id = str(uuid4())
    version_id = str(uuid4())
    rule = ApplicabilityRule(id=rule_id, rule_key=rule_key)
    version = ApplicabilityRuleVersion(
        id=version_id,
        rule_id=rule_id,
        version_number=1,
        interpretation_status="approved",
    )
    return rule, version


def make_synth_hierarchy(
    version_id: str,
    operator: str = "AND",
    group_purpose: str = "applicability",
) -> ApplicabilityConditionGroup:
    return ApplicabilityConditionGroup(
        id=str(uuid4()),
        rule_version_id=version_id,
        parent_group_id=None,
        group_purpose=group_purpose,
        boolean_operator=operator,
        sequence=1,
    )


class ApplicabilityEngineTests(unittest.TestCase):
    """35 Unit Test Scenarios for Phase 3B."""

    def test_01_simple_equals(self):
        rule, version = make_synth_rule("SYNTH_RULE_EQUALS")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
        )
        fact_true = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=True
        )
        decision, evidence = evaluate_rule(
            version, [root], [cond], [], [fact_true]
        )
        self.assertEqual("applicable", decision.result)
        self.assertEqual(1, len(evidence))
        self.assertEqual("true", evidence[0].evaluation)

        # Mismatch case
        fact_false = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=False
        )
        dec_mismatch, _ = evaluate_rule(
            version, [root], [cond], [], [fact_false]
        )
        self.assertEqual("not_applicable", dec_mismatch.result)

    def test_02_not_equals(self):
        rule, version = make_synth_rule("SYNTH_RULE_NOT_EQUALS")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="sale_context",
            operator="not_equals",
            expected_value="export",
        )
        fact_domestic = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="sale_context", value="domestic"
        )
        dec1, _ = evaluate_rule(version, [root], [cond], [], [fact_domestic])
        self.assertEqual("applicable", dec1.result)

        fact_export = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="sale_context", value="export"
        )
        dec2, _ = evaluate_rule(version, [root], [cond], [], [fact_export])
        self.assertEqual("not_applicable", dec2.result)

    def test_03_one_of(self):
        rule, version = make_synth_rule("SYNTH_RULE_ONE_OF")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="actor_role",
            operator="one_of",
            expected_value=["manufacturer", "packer"],
        )
        fact_packer = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="actor_role", value="packer"
        )
        dec1, _ = evaluate_rule(version, [root], [cond], [], [fact_packer])
        self.assertEqual("applicable", dec1.result)

        fact_dealer = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="actor_role", value="dealer"
        )
        dec2, _ = evaluate_rule(version, [root], [cond], [], [fact_dealer])
        self.assertEqual("not_applicable", dec2.result)

    def test_04_greater_than(self):
        rule, version = make_synth_rule("SYNTH_RULE_GT")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="quantity",
            operator="greater_than",
            expected_value=Decimal("25"),
            expected_unit="kg",
        )
        fact_pass = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("25.1"), unit="kg"
        )
        dec1, _ = evaluate_rule(version, [root], [cond], [], [fact_pass])
        self.assertEqual("applicable", dec1.result)

        fact_boundary = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("25.0"), unit="kg"
        )
        dec2, _ = evaluate_rule(version, [root], [cond], [], [fact_boundary])
        self.assertEqual("not_applicable", dec2.result)

    def test_05_greater_or_equal(self):
        rule, version = make_synth_rule("SYNTH_RULE_GTE")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="quantity",
            operator="greater_or_equal",
            expected_value=Decimal("25"),
            expected_unit="kg",
        )
        fact_boundary = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("25.0"), unit="kg"
        )
        dec1, _ = evaluate_rule(version, [root], [cond], [], [fact_boundary])
        self.assertEqual("applicable", dec1.result)

        fact_fail = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("24.99"), unit="kg"
        )
        dec2, _ = evaluate_rule(version, [root], [cond], [], [fact_fail])
        self.assertEqual("not_applicable", dec2.result)

    def test_06_less_than(self):
        rule, version = make_synth_rule("SYNTH_RULE_LT")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="quantity",
            operator="less_than",
            expected_value=Decimal("10"),
            expected_unit="g",
        )
        fact_pass = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("9.99"), unit="g"
        )
        dec1, _ = evaluate_rule(version, [root], [cond], [], [fact_pass])
        self.assertEqual("applicable", dec1.result)

        fact_boundary = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("10.0"), unit="g"
        )
        dec2, _ = evaluate_rule(version, [root], [cond], [], [fact_boundary])
        self.assertEqual("not_applicable", dec2.result)

    def test_07_less_or_equal(self):
        rule, version = make_synth_rule("SYNTH_RULE_LTE")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="quantity",
            operator="less_or_equal",
            expected_value=Decimal("10"),
            expected_unit="g",
        )
        fact_boundary = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("10.0"), unit="g"
        )
        dec1, _ = evaluate_rule(version, [root], [cond], [], [fact_boundary])
        self.assertEqual("applicable", dec1.result)

        fact_fail = InspectionFact(
            id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("10.001"), unit="g"
        )
        dec2, _ = evaluate_rule(version, [root], [cond], [], [fact_fail])
        self.assertEqual("not_applicable", dec2.result)

    def test_08_range_inclusive(self):
        rule, version = make_synth_rule("SYNTH_RULE_RANGE")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=root.id,
            fact_key="quantity",
            operator="range_inclusive",
            expected_value=[Decimal("10"), Decimal("50")],
            expected_unit="g",
        )
        for val, expected in [
            (Decimal("10.0"), "applicable"),
            (Decimal("50.0"), "applicable"),
            (Decimal("25.0"), "applicable"),
            (Decimal("9.99"), "not_applicable"),
            (Decimal("50.01"), "not_applicable"),
        ]:
            with self.subTest(val=val):
                fact = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=val, unit="g")
                dec, _ = evaluate_rule(version, [root], [cond], [], [fact])
                self.assertEqual(expected, dec.result)

    def test_09_exists(self):
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=str(uuid4()), fact_key="commodity", operator="exists"
        )
        # known -> TRUE
        f_known = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="commodity", fact_status="known", value="tea")
        res, _ = evaluate_condition(cond, f_known)
        self.assertEqual(TriState.TRUE, res)

        # unknown -> UNKNOWN
        f_unknown = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="commodity", fact_status="unknown", value=None)
        res, _ = evaluate_condition(cond, f_unknown)
        self.assertEqual(TriState.UNKNOWN, res)

        # not_observed -> UNKNOWN
        f_not_obs = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="commodity", fact_status="not_observed", value=None)
        res, _ = evaluate_condition(cond, f_not_obs)
        self.assertEqual(TriState.UNKNOWN, res)

        # not_applicable -> FALSE
        f_na = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="commodity", fact_status="not_applicable", value=None)
        res, _ = evaluate_condition(cond, f_na)
        self.assertEqual(TriState.FALSE, res)

        # missing -> UNKNOWN
        res, _ = evaluate_condition(cond, None)
        self.assertEqual(TriState.UNKNOWN, res)

    def test_10_and_all_true(self):
        rule, version = make_synth_rule("SYNTH_AND_TRUE")
        root = make_synth_hierarchy(version.id, operator="AND")
        c1 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="is_prepackaged", operator="equals", expected_value=True)
        c2 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="sale_context", operator="equals", expected_value="retail")
        facts = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="sale_context", value="retail"),
        ]
        dec, ev = evaluate_rule(version, [root], [c1, c2], [], facts)
        self.assertEqual("applicable", dec.result)
        self.assertTrue(all(e.evaluation == "true" for e in ev))

    def test_11_or_any_true(self):
        rule, version = make_synth_rule("SYNTH_OR_TRUE")
        root = make_synth_hierarchy(version.id, operator="OR")
        c1 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="actor_role", operator="equals", expected_value="manufacturer", sequence=1)
        c2 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="actor_role", operator="equals", expected_value="packer", sequence=2)
        facts = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="actor_role", value="packer"),
        ]
        dec, ev = evaluate_rule(version, [root], [c1, c2], [], facts)
        self.assertEqual("applicable", dec.result)
        self.assertEqual("false", ev[0].evaluation)
        self.assertEqual("true", ev[1].evaluation)

    def test_12_nested_groups(self):
        # A AND (B OR C)
        rule, version = make_synth_rule("SYNTH_NESTED")
        root = make_synth_hierarchy(version.id, operator="AND")
        sub = ApplicabilityConditionGroup(
            id=str(uuid4()), rule_version_id=version.id, parent_group_id=root.id,
            group_purpose="applicability", boolean_operator="OR", sequence=2
        )
        c_a = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="is_prepackaged", operator="equals", expected_value=True, sequence=1)
        c_b = ApplicabilityCondition(id=str(uuid4()), group_id=sub.id, fact_key="actor_role", operator="equals", expected_value="importer", sequence=1)
        c_c = ApplicabilityCondition(id=str(uuid4()), group_id=sub.id, fact_key="sale_context", operator="equals", expected_value="retail", sequence=2)

        facts = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="actor_role", value="dealer"), # B is False
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="sale_context", value="retail"), # C is True -> Sub is True
        ]
        dec, _ = evaluate_rule(version, [root, sub], [c_a, c_b, c_c], [], facts)
        self.assertEqual("applicable", dec.result)

    def test_13_unknown_and_semantics(self):
        # FALSE AND UNKNOWN = FALSE
        self.assertEqual(TriState.FALSE, TriState.kleene_and(TriState.FALSE, TriState.UNKNOWN))
        self.assertEqual(TriState.FALSE, TriState.kleene_and(TriState.UNKNOWN, TriState.FALSE))
        # TRUE AND UNKNOWN = UNKNOWN
        self.assertEqual(TriState.UNKNOWN, TriState.kleene_and(TriState.TRUE, TriState.UNKNOWN))
        # UNKNOWN AND UNKNOWN = UNKNOWN
        self.assertEqual(TriState.UNKNOWN, TriState.kleene_and(TriState.UNKNOWN, TriState.UNKNOWN))

        # Test in engine evaluation
        rule, version = make_synth_rule("SYNTH_AND_SEMANTICS")
        root = make_synth_hierarchy(version.id, operator="AND")
        c1 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="is_prepackaged", operator="equals", expected_value=True, sequence=1)
        c2 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="commodity", operator="equals", expected_value="sugar", sequence=2)

        # c1 False, c2 Missing -> Decision FALSE (not_applicable)
        facts_false = [InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=False)]
        dec1, ev1 = evaluate_rule(version, [root], [c1, c2], [], facts_false)
        self.assertEqual("not_applicable", dec1.result)
        # Short-circuit verification: c2 is not_evaluated
        self.assertEqual("not_evaluated", ev1[1].evaluation)

        # c1 True, c2 Missing -> Decision UNKNOWN
        facts_true = [InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=True)]
        dec2, _ = evaluate_rule(version, [root], [c1, c2], [], facts_true)
        self.assertEqual("unknown", dec2.result)
        self.assertIn("commodity", dec2.evidence_needed)

    def test_14_unknown_or_semantics(self):
        # TRUE OR UNKNOWN = TRUE
        self.assertEqual(TriState.TRUE, TriState.kleene_or(TriState.TRUE, TriState.UNKNOWN))
        self.assertEqual(TriState.TRUE, TriState.kleene_or(TriState.UNKNOWN, TriState.TRUE))
        # FALSE OR UNKNOWN = UNKNOWN
        self.assertEqual(TriState.UNKNOWN, TriState.kleene_or(TriState.FALSE, TriState.UNKNOWN))
        # UNKNOWN OR UNKNOWN = UNKNOWN
        self.assertEqual(TriState.UNKNOWN, TriState.kleene_or(TriState.UNKNOWN, TriState.UNKNOWN))

        # Test in engine
        rule, version = make_synth_rule("SYNTH_OR_SEMANTICS")
        root = make_synth_hierarchy(version.id, operator="OR")
        c1 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="actor_role", operator="equals", expected_value="manufacturer", sequence=1)
        c2 = ApplicabilityCondition(id=str(uuid4()), group_id=root.id, fact_key="commodity", operator="equals", expected_value="oil", sequence=2)

        # c1 True, c2 Missing -> Decision TRUE (applicable)
        facts_true = [InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="actor_role", value="manufacturer")]
        dec1, ev1 = evaluate_rule(version, [root], [c1, c2], [], facts_true)
        self.assertEqual("applicable", dec1.result)
        self.assertEqual("not_evaluated", ev1[1].evaluation)

        # c1 False, c2 Missing -> Decision UNKNOWN
        facts_false = [InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="actor_role", value="dealer")]
        dec2, _ = evaluate_rule(version, [root], [c1, c2], [], facts_false)
        self.assertEqual("unknown", dec2.result)
        self.assertIn("commodity", dec2.evidence_needed)

    def test_15_missing_fact(self):
        rule, version = make_synth_rule("SYNTH_MISSING_FACT")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="quantity", operator="greater_than", expected_value=Decimal("10")
        )
        dec, ev = evaluate_rule(version, [root], [cond], [], [])
        self.assertEqual("unknown", dec.result)
        self.assertEqual(["quantity"], dec.evidence_needed)
        self.assertEqual("unknown", ev[0].evaluation)
        self.assertIn("missing", ev[0].reason)

    def test_16_not_observed(self):
        rule, version = make_synth_rule("SYNTH_NOT_OBSERVED")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="sale_context", operator="equals", expected_value="retail"
        )
        fact = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="sale_context", fact_status="not_observed", value=None)
        dec, ev = evaluate_rule(version, [root], [cond], [], [fact])
        self.assertEqual("unknown", dec.result)
        self.assertEqual("unknown", ev[0].evaluation)
        self.assertIn("not_observed", ev[0].reason)

    def test_17_not_applicable_fact(self):
        # Scalar operator -> UNKNOWN
        rule, version = make_synth_rule("SYNTH_NA_FACT")
        root = make_synth_hierarchy(version.id)
        cond_eq = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="consumer_type", operator="equals", expected_value="industrial"
        )
        fact = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="consumer_type", fact_status="not_applicable", value=None)
        dec, ev = evaluate_rule(version, [root], [cond_eq], [], [fact])
        self.assertEqual("unknown", dec.result)
        self.assertEqual("unknown", ev[0].evaluation)

        # exists operator -> FALSE
        cond_ex = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="consumer_type", operator="exists"
        )
        dec_ex, ev_ex = evaluate_rule(version, [root], [cond_ex], [], [fact])
        self.assertEqual("not_applicable", dec_ex.result)
        self.assertEqual("false", ev_ex[0].evaluation)

    def test_18_exception_true(self):
        # Rule with Root Applicability and Root Exception
        rule, version = make_synth_rule("SYNTH_EXC_TRUE")
        root_app = make_synth_hierarchy(version.id, group_purpose="applicability")
        root_exc = make_synth_hierarchy(version.id, group_purpose="exception")

        c_app = ApplicabilityCondition(id=str(uuid4()), group_id=root_app.id, fact_key="is_prepackaged", operator="equals", expected_value=True)
        # Exception: package > 25 kg
        c_exc = ApplicabilityCondition(id=str(uuid4()), group_id=root_exc.id, fact_key="quantity", operator="greater_than", expected_value=Decimal("25"), expected_unit="kg")

        # 1. A True + E True -> not_applicable (Exempted by exception)
        facts1 = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=True),
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("30"), unit="kg"),
        ]
        dec1, _ = evaluate_rule(version, [root_app, root_exc], [c_app, c_exc], [], facts1)
        self.assertEqual("not_applicable", dec1.result)
        self.assertIn("Exempted", dec1.reason)

        # 2. A False + E True -> not_applicable
        facts2 = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=False),
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("30"), unit="kg"),
        ]
        dec2, _ = evaluate_rule(version, [root_app, root_exc], [c_app, c_exc], [], facts2)
        self.assertEqual("not_applicable", dec2.result)

        # 3. A Unknown + E True -> not_applicable (Definitive exemption regardless of core applicability)
        facts3 = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("30"), unit="kg"),
        ]
        dec3, _ = evaluate_rule(version, [root_app, root_exc], [c_app, c_exc], [], facts3)
        self.assertEqual("not_applicable", dec3.result)

    def test_19_exception_unknown(self):
        rule, version = make_synth_rule("SYNTH_EXC_UNKNOWN")
        root_app = make_synth_hierarchy(version.id, group_purpose="applicability")
        root_exc = make_synth_hierarchy(version.id, group_purpose="exception")

        c_app = ApplicabilityCondition(id=str(uuid4()), group_id=root_app.id, fact_key="is_prepackaged", operator="equals", expected_value=True)
        c_exc = ApplicabilityCondition(id=str(uuid4()), group_id=root_exc.id, fact_key="quantity", operator="greater_than", expected_value=Decimal("25"), expected_unit="kg")

        # 1. A True + E Unknown -> UNKNOWN (Unresolved exception could flip result)
        facts1 = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=True),
            # quantity missing
        ]
        dec1, _ = evaluate_rule(version, [root_app, root_exc], [c_app, c_exc], [], facts1)
        self.assertEqual("unknown", dec1.result)
        self.assertIn("quantity", dec1.evidence_needed)

        # 2. A False + E Unknown -> not_applicable (Kleene short-circuit: core already failed)
        facts2 = [
            InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="is_prepackaged", value=False),
        ]
        dec2, _ = evaluate_rule(version, [root_app, root_exc], [c_app, c_exc], [], facts2)
        self.assertEqual("not_applicable", dec2.result)

    def test_20_draft_rejection(self):
        rule_id = str(uuid4())
        v = ApplicabilityRuleVersion(id=str(uuid4()), rule_id=rule_id, version_number=1, interpretation_status="draft")
        self.assertEqual([], filter_approved_versions([v]))
        root = make_synth_hierarchy(v.id)
        dec, _ = evaluate_rule(v, [root], [], [], [])
        self.assertEqual("unknown", dec.result)
        self.assertIn("draft", dec.reason)

    def test_21_in_review_rejection(self):
        v = ApplicabilityRuleVersion(id=str(uuid4()), rule_id=str(uuid4()), version_number=1, interpretation_status="in_review")
        self.assertEqual([], filter_approved_versions([v]))
        root = make_synth_hierarchy(v.id)
        dec, _ = evaluate_rule(v, [root], [], [], [])
        self.assertEqual("unknown", dec.result)
        self.assertIn("in_review", dec.reason)

    def test_22_rejected_rejection(self):
        v = ApplicabilityRuleVersion(id=str(uuid4()), rule_id=str(uuid4()), version_number=1, interpretation_status="rejected")
        self.assertEqual([], filter_approved_versions([v]))
        root = make_synth_hierarchy(v.id)
        dec, _ = evaluate_rule(v, [root], [], [], [])
        self.assertEqual("unknown", dec.result)
        self.assertIn("rejected", dec.reason)

    def test_23_retired_rejection(self):
        v = ApplicabilityRuleVersion(id=str(uuid4()), rule_id=str(uuid4()), version_number=1, interpretation_status="retired")
        self.assertEqual([], filter_approved_versions([v]))
        root = make_synth_hierarchy(v.id)
        dec, _ = evaluate_rule(v, [root], [], [], [])
        self.assertEqual("unknown", dec.result)
        self.assertIn("retired", dec.reason)

    def test_24_approved_evaluation(self):
        v = ApplicabilityRuleVersion(id=str(uuid4()), rule_id=str(uuid4()), version_number=1, interpretation_status="approved")
        self.assertEqual([v], filter_approved_versions([v]))

    def test_25_temporal_selection(self):
        rule_id = str(uuid4())
        v1 = ApplicabilityRuleVersion(
            id=str(uuid4()), rule_id=rule_id, version_number=1, interpretation_status="approved",
            valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)
        )
        v2 = ApplicabilityRuleVersion(
            id=str(uuid4()), rule_id=rule_id, version_number=2, interpretation_status="approved",
            valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31)
        )
        sel, err = select_temporal_version([v1, v2], date(2026, 6, 1))
        self.assertIsNone(err)
        self.assertIsNotNone(sel)
        self.assertEqual(v2.id, sel.id)

    def test_26_temporal_ambiguity(self):
        rule_id = str(uuid4())
        # 0 matching -> UNKNOWN
        v1 = ApplicabilityRuleVersion(
            id=str(uuid4()), rule_id=rule_id, version_number=1, interpretation_status="approved",
            valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)
        )
        sel0, err0 = select_temporal_version([v1], date(2027, 1, 1))
        self.assertIsNone(sel0)
        self.assertEqual("no approved rule version matches inspection date", err0)

        # >1 matching overlapping approved versions -> UNKNOWN
        v2 = ApplicabilityRuleVersion(
            id=str(uuid4()), rule_id=rule_id, version_number=2, interpretation_status="approved",
            valid_from=date(2025, 6, 1), valid_to=date(2026, 6, 1)
        )
        sel_amb, err_amb = select_temporal_version([v1, v2], date(2025, 8, 1))
        self.assertIsNone(sel_amb)
        self.assertEqual("ambiguous approved rule versions", err_amb)

    def test_27_root_and_cycle_validation(self):
        v_id = str(uuid4())
        # 1. 0 root applicability groups
        g_exc_only = ApplicabilityConditionGroup(id=str(uuid4()), rule_version_id=v_id, group_purpose="exception")
        valid, diag, _, _ = validate_group_hierarchy([g_exc_only])
        self.assertFalse(valid)
        self.assertEqual("Malformed rule hierarchy: expected exactly one root applicability group", diag)

        # 2. >1 root applicability groups
        g_app1 = ApplicabilityConditionGroup(id=str(uuid4()), rule_version_id=v_id, group_purpose="applicability")
        g_app2 = ApplicabilityConditionGroup(id=str(uuid4()), rule_version_id=v_id, group_purpose="applicability")
        valid, diag, _, _ = validate_group_hierarchy([g_app1, g_app2])
        self.assertFalse(valid)
        self.assertEqual("Malformed rule hierarchy: multiple root applicability groups", diag)

        # 3. Orphaned parent group reference
        g_orphan = ApplicabilityConditionGroup(id=str(uuid4()), rule_version_id=v_id, parent_group_id=str(uuid4()))
        valid, diag, _, _ = validate_group_hierarchy([g_app1, g_orphan])
        self.assertFalse(valid)
        self.assertEqual("Malformed rule hierarchy: orphaned parent group reference", diag)

        # 4. Cycle detected
        g_a_id = str(uuid4())
        g_b_id = str(uuid4())
        # g_app1 is root; g_a -> g_b -> g_a
        g_a = ApplicabilityConditionGroup(id=g_a_id, rule_version_id=v_id, parent_group_id=g_b_id)
        g_b = ApplicabilityConditionGroup(id=g_b_id, rule_version_id=v_id, parent_group_id=g_a_id)
        valid, diag, _, _ = validate_group_hierarchy([g_app1, g_a, g_b])
        self.assertFalse(valid)
        self.assertEqual("Malformed rule hierarchy: cycle detected", diag)

    def test_28_unit_registry_and_cross_dimension_rejection(self):
        # 1. Same-dimension reviewed conversion (kg -> g)
        val_g, err = convert_quantity(Decimal("2.5"), "kg", "g")
        self.assertIsNone(err)
        self.assertEqual(Decimal("2500"), val_g)

        # 2. Cross-dimension conversion forbidden (kg -> L)
        val_l, err_l = convert_quantity(Decimal("1"), "kg", "l")
        self.assertIsNone(val_l)
        self.assertIn("Incompatible unit dimensions", err_l)

        # 3. Cross-dimension conversion in engine returns UNKNOWN
        rule, version = make_synth_rule("SYNTH_UNIT_CROSS")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="quantity", operator="greater_than",
            expected_value=Decimal("10"), expected_unit="kg"
        )
        fact_vol = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("15"), unit="l")
        dec, ev = evaluate_rule(version, [root], [cond], [], [fact_vol])
        self.assertEqual("unknown", dec.result)
        self.assertIn("Incompatible unit dimensions", ev[0].reason)

    def test_29_duplicate_identical_facts(self):
        rule, version = make_synth_rule("SYNTH_DUP_IDENTICAL")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="quantity", operator="equals",
            expected_value=Decimal("500"), expected_unit="g"
        )
        run_id = str(uuid4())
        f1 = InspectionFact(id=str(uuid4()), run_id=run_id, fact_key="quantity", value=Decimal("500"), unit="g")
        f2 = InspectionFact(id=str(uuid4()), run_id=run_id, fact_key="quantity", value=Decimal("500"), unit="g")
        dec, _ = evaluate_rule(version, [root], [cond], [], [f1, f2])
        self.assertEqual("applicable", dec.result)

    def test_30_conflicting_duplicate_facts(self):
        rule, version = make_synth_rule("SYNTH_DUP_CONFLICT")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="quantity", operator="equals",
            expected_value=Decimal("500"), expected_unit="g"
        )
        run_id = str(uuid4())
        f1 = InspectionFact(id=str(uuid4()), run_id=run_id, fact_key="quantity", value=Decimal("500"), unit="g")
        f2 = InspectionFact(id=str(uuid4()), run_id=run_id, fact_key="quantity", value=Decimal("750"), unit="g")
        dec, ev = evaluate_rule(version, [root], [cond], [], [f1, f2])
        self.assertEqual("unknown", dec.result)
        self.assertIn("Conflicting inspection facts observed", ev[0].reason)

    def test_31_malformed_operator(self):
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=str(uuid4()), fact_key="commodity", operator="regex_match", expected_value=".*"
        )
        fact = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="commodity", value="tea")
        res, reason = evaluate_condition(cond, fact)
        self.assertEqual(TriState.UNKNOWN, res)
        self.assertIn("Unsupported operator", reason)

    def test_32_unrecognized_unit(self):
        val, err = convert_quantity(Decimal("10"), "furlong", "m")
        self.assertIsNone(val)
        self.assertIn("Unrecognized or unreviewed source unit", err)

    def test_33_unreviewed_conversion(self):
        # Both units are recognized in ontology but no factor registered between them
        val, err = convert_quantity(Decimal("10"), "piece", "g")
        self.assertIsNone(val)
        self.assertIn("Incompatible unit dimensions", err)

    def test_34_decimal_boundary_precision(self):
        # Strict boundary test: 25.0000000000000000001 > 25
        d_val = Decimal("25.0000000000000000001")
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=str(uuid4()), fact_key="quantity", operator="greater_than",
            expected_value=Decimal("25")
        )
        fact = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=d_val)
        res, _ = evaluate_condition(cond, fact)
        self.assertEqual(TriState.TRUE, res)

        # 25.0000000000000000000 == 25
        fact_eq = InspectionFact(id=str(uuid4()), run_id=str(uuid4()), fact_key="quantity", value=Decimal("25.0000000000000000000"))
        res_eq, _ = evaluate_condition(cond, fact_eq)
        self.assertEqual(TriState.FALSE, res_eq)

    def test_35_service_evaluate_run(self):
        run = ApplicabilityRun(
            id=str(uuid4()), inspection_reference="INSP-SYNTH-001", inspection_date=date(2026, 6, 1)
        )
        rule, version = make_synth_rule("SYNTH_RULE_SERVICE")
        root = make_synth_hierarchy(version.id)
        cond = ApplicabilityCondition(
            id=str(uuid4()), group_id=root.id, fact_key="is_prepackaged", operator="equals", expected_value=True
        )
        facts = [
            InspectionFact(id=str(uuid4()), run_id=run.id, fact_key="is_prepackaged", value=True)
        ]
        results = ApplicabilityService.evaluate_run(
            run=run,
            facts=facts,
            rules=[rule],
            rule_versions=[version],
            groups=[root],
            conditions=[cond],
        )
        self.assertEqual(1, len(results))
        decision, evidence = results[0]
        self.assertEqual("applicable", decision.result)
        self.assertEqual(1, len(evidence))
        self.assertEqual("true", evidence[0].evaluation)


if __name__ == "__main__":
    unittest.main()

