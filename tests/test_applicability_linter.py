"""Tests for Phase 3C Authoring Linter and Invariant Enforcement.

Covers all 11 Phase 3C linter invariants:
- valid rule key
- invalid rule key
- invalid version
- invalid temporal bounds
- missing root
- multiple roots
- cyclic tree
- depth > 3
- unknown fact key
- invalid operator/unit combination
- missing provenance
- mismatched provenance
- empty source quote
- invalid lifecycle transition
- attempted modification of approved version
- valid rule passes linting
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from uuid import uuid4

from backend.app.services.applicability.linter import (
    CANONICAL_FACT_KEYS,
    FORBIDDEN_FACT_KEYS,
    ApplicabilityLinter,
    ImmutabilityViolationError,
    LintValidationError,
    lint_rule_version,
)
from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityRule,
    ApplicabilityRuleSource,
    ApplicabilityRuleVersion,
)


class ApplicabilityLinterTests(unittest.TestCase):
    """Test suite covering Phase 3C authoring linter invariants."""

    def setUp(self):
        self.linter = ApplicabilityLinter()

        # Reusable valid baseline fixture
        self.rule_id = str(uuid4())
        self.version_id = str(uuid4())
        self.root_group_id = str(uuid4())
        self.cond_id = str(uuid4())
        self.req_id = str(uuid4())
        self.prov_id = 7194

        self.valid_rule = ApplicabilityRule(
            id=self.rule_id,
            rule_key="rule_6_1_a_manufacturer_identity",
        )
        self.valid_version = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="draft",
            valid_from=date(2011, 11, 1),
            valid_to=None,
        )
        self.valid_groups = [
            ApplicabilityConditionGroup(
                id=self.root_group_id,
                rule_version_id=self.version_id,
                parent_group_id=None,
                group_purpose="applicability",
                boolean_operator="AND",
                sequence=1,
                review_status="draft",
            )
        ]
        self.valid_conditions = [
            ApplicabilityCondition(
                id=self.cond_id,
                group_id=self.root_group_id,
                fact_key="is_prepackaged",
                operator="equals",
                expected_value=True,
                expected_unit=None,
                sequence=1,
                review_status="draft",
            )
        ]
        self.valid_sources = [
            ApplicabilityRuleSource(
                id=str(uuid4()),
                rule_version_id=self.version_id,
                requirement_id=self.req_id,
                provision_id=self.prov_id,
                source_role="supports",
                source_quote="Every package shall bear thereon or on label securely affixed thereto...",
                review_status="draft",
            ),
            ApplicabilityRuleSource(
                id=str(uuid4()),
                rule_version_id=self.version_id,
                requirement_id=self.req_id,
                provision_id=self.prov_id,
                condition_id=self.cond_id,
                source_role="condition",
                source_quote="(a) the name and address of the manufacturer...",
                review_status="draft",
            ),
        ]

    # -----------------------------------------------------------------
    # Invariant 1: Rule key format
    # -----------------------------------------------------------------
    def test_valid_rule_key(self):
        result = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual([], result.errors)

    def test_invalid_rule_key(self):
        invalid_keys = [
            "",
            "   ",
            "Rule-6-1-A",        # uppercase and dashes
            "rule 6 1 a",        # spaces
            "rule.6.1.a",        # dots
            "rule$key",          # special character
        ]
        for key in invalid_keys:
            with self.subTest(key=key):
                rule = ApplicabilityRule(id=self.rule_id, rule_key=key)
                res = self.linter.lint(
                    rule=rule,
                    version=self.valid_version,
                    groups=self.valid_groups,
                    conditions=self.valid_conditions,
                    sources=self.valid_sources,
                )
                self.assertFalse(res.is_valid)
                self.assertTrue(any("Rule key" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 2: Version number
    # -----------------------------------------------------------------
    def test_invalid_version_number(self):
        invalid_versions = [0, -1, -5, True, False]
        for ver in invalid_versions:
            with self.subTest(ver=ver):
                version = ApplicabilityRuleVersion(
                    id=self.version_id,
                    rule_id=self.rule_id,
                    version_number=ver,  # type: ignore
                    interpretation_status="draft",
                )
                res = self.linter.lint(
                    rule=self.valid_rule,
                    version=version,
                    groups=self.valid_groups,
                    conditions=self.valid_conditions,
                    sources=self.valid_sources,
                )
                self.assertFalse(res.is_valid)
                self.assertTrue(any("Version number" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 3: Temporal bounds
    # -----------------------------------------------------------------
    def test_invalid_temporal_bounds(self):
        # valid_to < valid_from
        version = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="draft",
            valid_from=date(2020, 1, 1),
            valid_to=date(2019, 1, 1),
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Temporal bounds invalid" in err for err in res.errors))

    def test_disallowed_hardcoded_placeholder_dates_without_amendment(self):
        # Disallow pilot placeholders 2021-12-31 without amendment_id evidence
        version = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="draft",
            valid_from=date(2011, 1, 1),
            valid_to=date(2021, 12, 31),
            amendment_id=None,
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Disallowed hardcoded/invented temporal boundary" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 4: Root applicability group
    # -----------------------------------------------------------------
    def test_missing_root_applicability_group(self):
        # No group has parent_group_id=None and purpose='applicability'
        groups = [
            ApplicabilityConditionGroup(
                id=self.root_group_id,
                rule_version_id=self.version_id,
                parent_group_id=None,
                group_purpose="exception",
                boolean_operator="OR",
                sequence=1,
                review_status="draft",
            )
        ]
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("must have exactly one root applicability group" in err for err in res.errors))

    def test_multiple_root_applicability_groups(self):
        g2_id = str(uuid4())
        groups = [
            self.valid_groups[0],
            ApplicabilityConditionGroup(
                id=g2_id,
                rule_version_id=self.version_id,
                parent_group_id=None,
                group_purpose="applicability",
                boolean_operator="AND",
                sequence=2,
                review_status="draft",
            ),
        ]
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("must have exactly one root applicability group (found 2)" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 5: Acyclic condition tree
    # -----------------------------------------------------------------
    def test_cyclic_tree_self_parent(self):
        g_id = str(uuid4())
        groups = [
            ApplicabilityConditionGroup(
                id=g_id,
                rule_version_id=self.version_id,
                parent_group_id=g_id,  # self parent
                group_purpose="applicability",
                boolean_operator="AND",
                sequence=1,
                review_status="draft",
            )
        ]
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("cannot be its own parent" in err for err in res.errors))

    def test_cyclic_tree_indirect_cycle(self):
        g1_id = str(uuid4())
        g2_id = str(uuid4())
        groups = [
            ApplicabilityConditionGroup(
                id=g1_id,
                rule_version_id=self.version_id,
                parent_group_id=g2_id,  # g1 -> g2
                group_purpose="applicability",
                boolean_operator="AND",
                sequence=1,
                review_status="draft",
            ),
            ApplicabilityConditionGroup(
                id=g2_id,
                rule_version_id=self.version_id,
                parent_group_id=g1_id,  # g2 -> g1
                group_purpose="applicability",
                boolean_operator="AND",
                sequence=2,
                review_status="draft",
            ),
        ]
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=groups,
            conditions=[],
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Cyclic condition tree detected" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 6: Maximum condition-tree depth <= 3
    # -----------------------------------------------------------------
    def test_tree_depth_exceeds_three(self):
        g1 = str(uuid4())  # depth 1 (root)
        g2 = str(uuid4())  # depth 2
        g3 = str(uuid4())  # depth 3
        g4 = str(uuid4())  # depth 4 (exceeds 3!)
        groups = [
            ApplicabilityConditionGroup(id=g1, rule_version_id=self.version_id, parent_group_id=None, group_purpose="applicability", boolean_operator="AND"),
            ApplicabilityConditionGroup(id=g2, rule_version_id=self.version_id, parent_group_id=g1, group_purpose="applicability", boolean_operator="AND"),
            ApplicabilityConditionGroup(id=g3, rule_version_id=self.version_id, parent_group_id=g2, group_purpose="applicability", boolean_operator="AND"),
            ApplicabilityConditionGroup(id=g4, rule_version_id=self.version_id, parent_group_id=g3, group_purpose="applicability", boolean_operator="AND"),
        ]
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=groups,
            conditions=[],
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("exceeds maximum allowed tree depth of 3" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 7: Canonical fact keys
    # -----------------------------------------------------------------
    def test_approved_canonical_fact_keys_accepted(self):
        for key in CANONICAL_FACT_KEYS:
            with self.subTest(key=key):
                cond = ApplicabilityCondition(
                    id=self.cond_id,
                    group_id=self.root_group_id,
                    fact_key=key,
                    operator="exists",
                    expected_value=None,
                )
                res = self.linter.lint(
                    rule=self.valid_rule,
                    version=self.valid_version,
                    groups=self.valid_groups,
                    conditions=[cond],
                    sources=self.valid_sources,
                )
                # Verify no fact_key errors
                fact_errors = [e for e in res.errors if "fact_key" in e]
                self.assertEqual([], fact_errors)

    def test_forbidden_and_unknown_fact_keys_rejected(self):
        for key in FORBIDDEN_FACT_KEYS | {"random_key", "custom_fact"}:
            with self.subTest(key=key):
                cond = ApplicabilityCondition(
                    id=self.cond_id,
                    group_id=self.root_group_id,
                    fact_key=key,
                    operator="exists",
                )
                res = self.linter.lint(
                    rule=self.valid_rule,
                    version=self.valid_version,
                    groups=self.valid_groups,
                    conditions=[cond],
                    sources=self.valid_sources,
                )
                self.assertFalse(res.is_valid)
                self.assertTrue(any("fact_key" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 8: Operator / unit compatibility
    # -----------------------------------------------------------------
    def test_missing_unit_on_quantitative_operator(self):
        cond = ApplicabilityCondition(
            id=self.cond_id,
            group_id=self.root_group_id,
            fact_key="quantity",
            operator="greater_than",
            expected_value=25,
            expected_unit=None,  # missing unit!
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=[cond],
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("missing required expected_unit" in err for err in res.errors))

    def test_forbidden_unit_on_non_quantitative_fact(self):
        cond = ApplicabilityCondition(
            id=self.cond_id,
            group_id=self.root_group_id,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
            expected_unit="kg",  # forbidden unit on boolean!
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=[cond],
            sources=self.valid_sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("must not specify expected_unit" in err for err in res.errors))

    def test_invalid_one_of_and_range_operators(self):
        # one_of with empty list
        cond_one_of = ApplicabilityCondition(
            id=self.cond_id,
            group_id=self.root_group_id,
            fact_key="commodity",
            operator="one_of",
            expected_value=[],
        )
        res1 = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=[cond_one_of],
            sources=self.valid_sources,
        )
        self.assertFalse(res1.is_valid)
        self.assertTrue(any("requires a non-empty list" in err for err in res1.errors))

        # range_inclusive with min > max
        cond_range = ApplicabilityCondition(
            id=self.cond_id,
            group_id=self.root_group_id,
            fact_key="quantity",
            operator="range_inclusive",
            expected_value=[50, 10],  # min > max
            expected_unit="g",
        )
        res2 = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=[cond_range],
            sources=self.valid_sources,
        )
        self.assertFalse(res2.is_valid)
        self.assertTrue(any("min (50) > max (10)" in err for err in res2.errors))

    # -----------------------------------------------------------------
    # Invariant 9: Source-to-condition provenance consistency
    # -----------------------------------------------------------------
    def test_missing_provenance_for_leaf_condition(self):
        # Remove the condition provenance from sources
        sources = [s for s in self.valid_sources if s.source_role != "condition"]
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=sources,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("has no supporting statutory provenance with source_role='condition'" in err for err in res.errors))

    def test_mismatched_provenance_condition_id(self):
        # Source points to non-existent condition_id
        bad_source = ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=self.version_id,
            requirement_id=self.req_id,
            provision_id=self.prov_id,
            condition_id=str(uuid4()),  # non-existent!
            source_role="condition",
            source_quote="Some quote",
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources + [bad_source],
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("references non-existent condition_id" in err for err in res.errors))

    def test_empty_source_quote(self):
        empty_quote_source = ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=self.version_id,
            requirement_id=self.req_id,
            provision_id=self.prov_id,
            condition_id=self.cond_id,
            source_role="condition",
            source_quote="   ",  # whitespace only
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=[empty_quote_source],
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("empty source_quote" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 10: Lifecycle transitions & Human review accreditation
    # -----------------------------------------------------------------
    def test_invalid_lifecycle_transition(self):
        prev = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="draft",
        )
        # Cannot skip in_review to approved
        curr = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="approved",
            reviewed_by="Advocate Sharma",
            reviewed_at=datetime.now(),
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=curr,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
            previous_version=prev,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Invalid lifecycle transition from 'draft' to 'approved'" in err for err in res.errors))

    def test_approval_without_human_reviewer_rejected(self):
        prev = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="in_review",
        )
        curr = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="approved",
            reviewed_by=None,  # missing reviewer!
            reviewed_at=datetime.now(),
        )
        res = self.linter.lint(
            rule=self.valid_rule,
            version=curr,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
            previous_version=prev,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("cannot be approved without an identified human reviewer" in err for err in res.errors))

    def test_approval_by_ai_system_strictly_forbidden(self):
        prev = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="in_review",
        )
        for ai_id in ["ai", "gemini", "assistant", "system", "llm"]:
            with self.subTest(ai_id=ai_id):
                curr = ApplicabilityRuleVersion(
                    id=self.version_id,
                    rule_id=self.rule_id,
                    version_number=1,
                    interpretation_status="approved",
                    reviewed_by=ai_id,
                    reviewed_at=datetime.now(),
                )
                res = self.linter.lint(
                    rule=self.valid_rule,
                    version=curr,
                    groups=self.valid_groups,
                    conditions=self.valid_conditions,
                    sources=self.valid_sources,
                    previous_version=prev,
                )
                self.assertFalse(res.is_valid)
                self.assertTrue(any("cannot approve rule versions. Human legal review is strictly required" in err for err in res.errors))

    # -----------------------------------------------------------------
    # Invariant 11: Approved versions are immutable
    # -----------------------------------------------------------------
    def test_attempted_modification_of_approved_version_raises_immutability_error(self):
        approved_prev = ApplicabilityRuleVersion(
            id=self.version_id,
            rule_id=self.rule_id,
            version_number=1,
            interpretation_status="approved",
            valid_from=date(2011, 11, 1),
            valid_to=None,
            reviewed_by="Senior Counsel Patel",
            reviewed_at=datetime(2022, 1, 1, 12, 0, 0),
        )

        # Attempted in-place modification of condition in version 1
        new_cond = ApplicabilityCondition(
            id=self.cond_id,
            group_id=self.root_group_id,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=False,  # changed value!
        )

        res = self.linter.lint(
            rule=self.valid_rule,
            version=approved_prev,  # same version number 1
            groups=self.valid_groups,
            conditions=[new_cond],
            sources=self.valid_sources,
            previous_version=approved_prev,
            previous_conditions=self.valid_conditions,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Immutability violation" in err for err in res.errors))

        with self.assertRaises(ImmutabilityViolationError):
            res.raise_if_invalid()

    # -----------------------------------------------------------------
    # Invariant: Valid rule passes linting
    # -----------------------------------------------------------------
    def test_valid_rule_passes_linting_and_convenience_function(self):
        res = lint_rule_version(
            rule=self.valid_rule,
            version=self.valid_version,
            groups=self.valid_groups,
            conditions=self.valid_conditions,
            sources=self.valid_sources,
        )
        self.assertTrue(res.is_valid)
        self.assertEqual([], res.errors)
        # Should not raise
        res.raise_if_invalid()


if __name__ == "__main__":
    unittest.main()
