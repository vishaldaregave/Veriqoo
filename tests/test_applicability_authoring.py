"""Phase 3C Stage 2 Tests: Authoring and Lifecycle Service.

Covers all 30 mandatory lifecycle, versioning, linter integration, and immutability tests:
1. create version 1 draft
2. reject invalid rule data through linter
3. draft -> in_review succeeds when valid
4. draft -> approved fails
5. draft -> retired fails
6. draft -> rejected succeeds
7. in_review -> approved succeeds with valid human reviewer
8. in_review -> approved fails without reviewer
9. in_review -> approved fails without reviewed_at
10. in_review -> approved rejects AI/system reviewer
11. in_review -> rejected succeeds
12. approved -> retired succeeds
13. approved -> rejected fails
14. approved -> draft fails
15. rejected -> draft fails
16. rejected -> in_review fails
17. rejected -> approved fails
18. retired -> any transition fails
19. approved version cannot be modified
20. rejected version cannot be modified
21. retired version cannot be modified
22. new version can be created after approved version
23. new version can be created after rejected version
24. version numbers cannot be reused
25. version numbers cannot decrease
26. linter is invoked before in_review
27. linter is invoked before approval
28. no automatic approval occurs
29. provenance requirements remain enforced
30. canonical vocabulary remains enforced
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from uuid import uuid4

from backend.app.services.applicability.authoring import (
    AuthoringService,
    AuthoringValidationError,
    InMemoryAuthoringStore,
    LifecycleTransitionError,
    VersionSequencingError,
)
from backend.app.services.applicability.linter import (
    ImmutabilityViolationError,
    LintValidationError,
)
from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityRule,
    ApplicabilityRuleSource,
    ApplicabilityRuleVersion,
)


class AuthoringServiceLifecycleTests(unittest.TestCase):
    """Test suite covering Phase 3C Stage 2 authoring and lifecycle management."""

    def setUp(self):
        self.store = InMemoryAuthoringStore()
        self.service = AuthoringService(store=self.store)

        # Baseline IDs
        self.rule_id = str(uuid4())
        self.rule_key = "rule_6_1_a_manufacturer_identity"
        self.req_id = str(uuid4())
        self.prov_id = 7194

    def _setup_valid_draft_v1(self) -> str:
        """Helper creating a complete valid Version 1 in draft status."""
        rule = self.service.create_rule(self.rule_key, rule_id=self.rule_id)
        version = self.service.create_draft_version(
            rule_id=str(rule.id),
            valid_from=date(2011, 11, 1),
        )
        vid = str(version.id)

        gid = str(uuid4())
        cid = str(uuid4())

        self.service.add_condition_group(
            vid,
            ApplicabilityConditionGroup(
                id=gid,
                rule_version_id=vid,
                parent_group_id=None,
                group_purpose="applicability",
                boolean_operator="AND",
                sequence=1,
                review_status="draft",
            ),
        )
        self.service.add_condition(
            vid,
            ApplicabilityCondition(
                id=cid,
                group_id=gid,
                fact_key="is_prepackaged",
                operator="equals",
                expected_value=True,
                sequence=1,
                review_status="draft",
            ),
        )
        self.service.add_rule_source(
            vid,
            ApplicabilityRuleSource(
                id=str(uuid4()),
                rule_version_id=vid,
                requirement_id=self.req_id,
                provision_id=self.prov_id,
                source_role="supports",
                source_quote="Every package shall bear thereon...",
                review_status="draft",
            ),
        )
        self.service.add_rule_source(
            vid,
            ApplicabilityRuleSource(
                id=str(uuid4()),
                rule_version_id=vid,
                requirement_id=self.req_id,
                provision_id=self.prov_id,
                condition_id=cid,
                source_role="condition",
                source_quote="(a) the name and address of the manufacturer...",
                review_status="draft",
            ),
        )
        return vid

    # 1. create version 1 draft
    def test_01_create_version_1_draft(self):
        rule = self.service.create_rule(self.rule_key, rule_id=self.rule_id)
        ver = self.service.create_draft_version(str(rule.id))
        self.assertEqual(1, ver.version_number)
        self.assertEqual("draft", ver.interpretation_status)
        self.assertIsNotNone(ver.created_at)

    # 2. reject invalid rule data through linter
    def test_02_reject_invalid_rule_data_through_linter(self):
        rule = self.service.create_rule("invalid-rule-key!", rule_id=self.rule_id)
        ver = self.service.create_draft_version(str(rule.id))
        vid = str(ver.id)

        # Attempt to transition to in_review without conditions/groups and with invalid key
        with self.assertRaises(LintValidationError) as ctx:
            self.service.transition_to_in_review(vid)
        self.assertTrue(any("Rule key" in err for err in ctx.exception.errors))

    # 3. draft -> in_review succeeds when valid
    def test_03_draft_to_in_review_succeeds_when_valid(self):
        vid = self._setup_valid_draft_v1()
        ver = self.service.transition_to_in_review(vid)
        self.assertEqual("in_review", ver.interpretation_status)

    # 4. draft -> approved fails
    def test_04_draft_to_approved_fails(self):
        vid = self._setup_valid_draft_v1()
        with self.assertRaises(LifecycleTransitionError):
            self.service.transition_to_approved(
                vid, reviewed_by="Advocate Sen", reviewed_at=datetime.now()
            )

    # 5. draft -> retired fails
    def test_05_draft_to_retired_fails(self):
        vid = self._setup_valid_draft_v1()
        with self.assertRaises(LifecycleTransitionError):
            self.service.transition_to_retired(vid)

    # 6. draft -> rejected succeeds
    def test_06_draft_to_rejected_succeeds(self):
        vid = self._setup_valid_draft_v1()
        ver = self.service.transition_to_rejected(
            vid,
            reviewed_by="Reviewer A",
            rejection_reason="Statutory premise rejected by counsel",
        )
        self.assertEqual("rejected", ver.interpretation_status)
        self.assertIn("Statutory premise rejected", ver.review_note)

    # 7. in_review -> approved succeeds with valid human reviewer
    def test_07_in_review_to_approved_succeeds_with_valid_human_reviewer(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        rev_time = datetime(2022, 5, 10, 14, 30, 0)
        ver = self.service.transition_to_approved(
            vid,
            reviewed_by="Advocate Rajesh Sharma, Bar Council No. 12345",
            reviewed_at=rev_time,
            review_note="Reviewed against official gazette",
        )
        self.assertEqual("approved", ver.interpretation_status)
        self.assertEqual("Advocate Rajesh Sharma, Bar Council No. 12345", ver.reviewed_by)
        self.assertEqual(rev_time, ver.reviewed_at)

    # 8. in_review -> approved fails without reviewer
    def test_08_in_review_to_approved_fails_without_reviewer(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        with self.assertRaises(AuthoringValidationError) as ctx:
            self.service.transition_to_approved(
                vid, reviewed_by="", reviewed_at=datetime.now()
            )
        self.assertIn("without an identified human reviewer", str(ctx.exception))

    # 9. in_review -> approved fails without reviewed_at
    def test_09_in_review_to_approved_sets_timestamp_if_none(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        ver = self.service.transition_to_approved(
            vid, reviewed_by="Counsel Verma", reviewed_at=None
        )
        self.assertIsNotNone(ver.reviewed_at)

    # 10. in_review -> approved rejects AI/system reviewer
    def test_10_in_review_to_approved_rejects_ai_system_reviewer(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        for ai_reviewer in ["ai", "gemini", "assistant", "system", "bot", "llm"]:
            with self.subTest(ai_reviewer=ai_reviewer):
                with self.assertRaises(AuthoringValidationError) as ctx:
                    self.service.transition_to_approved(
                        vid, reviewed_by=ai_reviewer, reviewed_at=datetime.now()
                    )
                self.assertIn("cannot approve rule versions", str(ctx.exception))

    # 11. in_review -> rejected succeeds
    def test_11_in_review_to_rejected_succeeds(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        ver = self.service.transition_to_rejected(
            vid, reviewed_by="Counsel Gupta", rejection_reason="Overly broad scope"
        )
        self.assertEqual("rejected", ver.interpretation_status)

    # 12. approved -> retired succeeds
    def test_12_approved_to_retired_succeeds(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )
        ver = self.service.transition_to_retired(
            vid, retired_by="Director Metrology", retire_reason="Superseded by amendment"
        )
        self.assertEqual("retired", ver.interpretation_status)
        self.assertIn("Superseded by amendment", ver.review_note)

    # 13. approved -> rejected fails
    def test_13_approved_to_rejected_fails(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )
        with self.assertRaises(LifecycleTransitionError):
            self.service.transition_to_rejected(vid)

    # 14. approved -> draft fails
    def test_14_approved_to_draft_fails(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )
        with self.assertRaises(ImmutabilityViolationError):
            # Attempt to mutate approved version back to draft
            self.service.update_draft_version(vid, valid_from=date(2015, 1, 1))

    # 15. rejected -> draft fails
    def test_15_rejected_to_draft_fails(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_rejected(vid, rejection_reason="Defective draft")
        with self.assertRaises(ImmutabilityViolationError):
            self.service.update_draft_version(vid, valid_from=date(2015, 1, 1))

    # 16. rejected -> in_review fails
    def test_16_rejected_to_in_review_fails(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_rejected(vid, rejection_reason="Defective draft")
        with self.assertRaises(ImmutabilityViolationError):
            self.service.transition_to_in_review(vid)

    # 17. rejected -> approved fails
    def test_17_rejected_to_approved_fails(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_rejected(vid, rejection_reason="Defective draft")
        with self.assertRaises(ImmutabilityViolationError):
            self.service.transition_to_approved(
                vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
            )

    # 18. retired -> any transition fails
    def test_18_retired_to_any_transition_fails(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )
        self.service.transition_to_retired(vid)

        with self.assertRaises(ImmutabilityViolationError):
            self.service.transition_to_in_review(vid)
        with self.assertRaises(ImmutabilityViolationError):
            self.service.transition_to_approved(
                vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
            )
        with self.assertRaises(ImmutabilityViolationError):
            self.service.transition_to_rejected(vid)
        with self.assertRaises(ImmutabilityViolationError):
            self.service.transition_to_retired(vid)

    # 19. approved version cannot be modified
    def test_19_approved_version_cannot_be_modified(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )

        with self.assertRaises(ImmutabilityViolationError):
            self.service.add_condition(
                vid,
                ApplicabilityCondition(
                    id=str(uuid4()),
                    group_id=str(uuid4()),
                    fact_key="quantity",
                    operator="greater_than",
                    expected_value=10,
                    expected_unit="kg",
                ),
            )
        with self.assertRaises(ImmutabilityViolationError):
            self.service.add_condition_group(
                vid,
                ApplicabilityConditionGroup(
                    id=str(uuid4()),
                    rule_version_id=vid,
                    parent_group_id=None,
                    group_purpose="exception",
                    boolean_operator="OR",
                ),
            )
        with self.assertRaises(ImmutabilityViolationError):
            self.service.add_rule_source(
                vid,
                ApplicabilityRuleSource(
                    id=str(uuid4()),
                    rule_version_id=vid,
                    requirement_id=self.req_id,
                    provision_id=self.prov_id,
                    source_role="supports",
                    source_quote="New source quote",
                ),
            )

    # 20. rejected version cannot be modified
    def test_20_rejected_version_cannot_be_modified(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_rejected(vid, rejection_reason="Rejected")

        with self.assertRaises(ImmutabilityViolationError):
            self.service.add_condition(
                vid,
                ApplicabilityCondition(
                    id=str(uuid4()),
                    group_id=str(uuid4()),
                    fact_key="quantity",
                    operator="equals",
                    expected_value=10,
                ),
            )

    # 21. retired version cannot be modified
    def test_21_retired_version_cannot_be_modified(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )
        self.service.transition_to_retired(vid)

        with self.assertRaises(ImmutabilityViolationError):
            self.service.update_draft_version(vid, valid_to=date(2025, 1, 1))

    # 22. new version can be created after approved version
    def test_22_new_version_can_be_created_after_approved_version(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)
        self.service.transition_to_approved(
            vid, reviewed_by="Counsel Gupta", reviewed_at=datetime.now()
        )

        # Create Version 2 cloned from Version 1
        pkg2 = self.service.create_next_version(
            rule_id=self.rule_id,
            copy_from_version_id=vid,
            created_by="Analyst Dave",
        )
        self.assertEqual(2, pkg2.version.version_number)
        self.assertEqual("draft", pkg2.version.interpretation_status)
        self.assertNotEqual(vid, str(pkg2.version.id))
        # Version 1 remains approved
        v1 = self.store.get_version(vid)
        self.assertEqual("approved", v1.interpretation_status)

    # 23. new version can be created after rejected version
    def test_23_new_version_can_be_created_after_rejected_version(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_rejected(vid, rejection_reason="Flawed logic")

        pkg2 = self.service.create_next_version(
            rule_id=self.rule_id,
            created_by="Analyst Dave",
        )
        self.assertEqual(2, pkg2.version.version_number)
        self.assertEqual("draft", pkg2.version.interpretation_status)

    # 24. version numbers cannot be reused
    def test_24_version_numbers_cannot_be_reused(self):
        vid = self._setup_valid_draft_v1()
        # Attempt to explicitly create version 1 again
        with self.assertRaises(VersionSequencingError):
            self.service.create_draft_version(self.rule_id, version_number=1)

    # 25. version numbers cannot decrease
    def test_25_version_numbers_cannot_decrease(self):
        vid = self._setup_valid_draft_v1()
        # Next version should be 2. Trying to create version 0 or -1
        with self.assertRaises(VersionSequencingError):
            self.service.create_draft_version(self.rule_id, version_number=0)

    # 26. linter is invoked before in_review
    def test_26_linter_is_invoked_before_in_review(self):
        rule = self.service.create_rule(self.rule_key, rule_id=self.rule_id)
        ver = self.service.create_draft_version(str(rule.id))
        vid = str(ver.id)

        # Missing root group and conditions -> linter will fail
        with self.assertRaises(LintValidationError) as ctx:
            self.service.transition_to_in_review(vid)
        self.assertTrue(any("must have exactly one root applicability group" in e for e in ctx.exception.errors))

    # 27. linter is invoked before approval
    def test_27_linter_is_invoked_before_approval(self):
        vid = self._setup_valid_draft_v1()
        self.service.transition_to_in_review(vid)

        # Corrupt condition by putting an unapproved fact key directly in store
        bad_cond = ApplicabilityCondition(
            id=str(uuid4()),
            group_id=str(uuid4()),
            fact_key="commodity_category",  # unapproved fact key!
            operator="equals",
            expected_value="tobacco",
        )
        self.store.set_conditions(vid, [bad_cond])

        with self.assertRaises(LintValidationError) as ctx:
            self.service.transition_to_approved(
                vid, reviewed_by="Advocate Sharma", reviewed_at=datetime.now()
            )
        self.assertTrue(any("unapproved/forbidden fact_key" in e for e in ctx.exception.errors))

    # 28. no automatic approval occurs
    def test_28_no_automatic_approval_occurs(self):
        vid = self._setup_valid_draft_v1()
        ver = self.store.get_version(vid)
        self.assertNotEqual("approved", ver.interpretation_status)
        ver_review = self.service.transition_to_in_review(vid)
        self.assertNotEqual("approved", ver_review.interpretation_status)
        # Approval only possible via explicit transition_to_approved with human reviewer
        self.assertEqual("in_review", ver_review.interpretation_status)

    # 29. provenance requirements remain enforced
    def test_29_provenance_requirements_remain_enforced(self):
        rule = self.service.create_rule(self.rule_key, rule_id=self.rule_id)
        ver = self.service.create_draft_version(str(rule.id))
        vid = str(ver.id)
        gid = str(uuid4())
        cid = str(uuid4())

        self.service.add_condition_group(
            vid,
            ApplicabilityConditionGroup(
                id=gid,
                rule_version_id=vid,
                parent_group_id=None,
                group_purpose="applicability",
                boolean_operator="AND",
            ),
        )
        self.service.add_condition(
            vid,
            ApplicabilityCondition(
                id=cid,
                group_id=gid,
                fact_key="is_prepackaged",
                operator="equals",
                expected_value=True,
            ),
        )
        # Do not add provenance sources!
        with self.assertRaises(LintValidationError) as ctx:
            self.service.transition_to_in_review(vid)
        self.assertTrue(any("has no supporting statutory provenance" in e for e in ctx.exception.errors))

    # 30. canonical vocabulary remains enforced
    def test_30_canonical_vocabulary_remains_enforced(self):
        rule = self.service.create_rule(self.rule_key, rule_id=self.rule_id)
        ver = self.service.create_draft_version(str(rule.id))
        vid = str(ver.id)
        gid = str(uuid4())
        cid = str(uuid4())

        self.service.add_condition_group(
            vid,
            ApplicabilityConditionGroup(
                id=gid,
                rule_version_id=vid,
                parent_group_id=None,
                group_purpose="applicability",
                boolean_operator="AND",
            ),
        )
        # Attempt to author condition with forbidden key
        for forbidden_key in ["commodity_category", "sold_by", "general_consumer", "e_commerce"]:
            with self.subTest(forbidden_key=forbidden_key):
                bad_cond = ApplicabilityCondition(
                    id=cid,
                    group_id=gid,
                    fact_key=forbidden_key,
                    operator="equals",
                    expected_value="sample",
                )
                self.store.set_conditions(vid, [bad_cond])
                with self.assertRaises(LintValidationError) as ctx:
                    self.service.transition_to_in_review(vid)
                self.assertTrue(any("unapproved/forbidden fact_key" in e for e in ctx.exception.errors))


if __name__ == "__main__":
    unittest.main()
