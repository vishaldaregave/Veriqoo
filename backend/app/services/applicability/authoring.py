"""Phase 3C Authoring & Lifecycle Service for Legal Applicability Rules.

Provides governance infrastructure to:
1. Create and manage versioned applicability rules.
2. Enforce the strict 5-state lifecycle: draft -> in_review -> approved -> retired (with rejected).
3. Gate all lifecycle transitions through the Stage 1 ApplicabilityLinter.
4. Enforce strict immutability on approved, rejected, and retired versions.
5. Enforce monotonic, non-reusable version sequencing (1, 2, 3...).
6. Enforce human accreditation for approval and strictly reject AI/system identities.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

from backend.app.services.applicability.linter import (
    AI_REVIEWER_IDENTIFIERS,
    CANONICAL_FACT_KEYS,
    ApplicabilityLinter,
    ImmutabilityViolationError,
    LintResult,
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


VALID_LIFECYCLE_STATES: frozenset[str] = frozenset(
    {"draft", "in_review", "approved", "rejected", "retired"}
)

ALLOWED_LIFECYCLE_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "draft": frozenset({"in_review", "rejected"}),
    "in_review": frozenset({"approved", "rejected"}),
    "approved": frozenset({"retired"}),
    "rejected": frozenset(),
    "retired": frozenset(),
}

IMMUTABLE_LIFECYCLE_STATES: frozenset[str] = frozenset(
    {"approved", "rejected", "retired"}
)


class LifecycleTransitionError(ValueError):
    """Raised when an illegal lifecycle state transition is attempted."""


class VersionSequencingError(ValueError):
    """Raised when version sequencing invariants are violated."""


class AuthoringValidationError(ValueError):
    """Raised when authoring data fails basic structural or domain validation."""


@dataclass
class RulePackage:
    """An authored rule version bundle containing the rule and its AST tree."""

    rule: ApplicabilityRule
    version: ApplicabilityRuleVersion
    groups: list[ApplicabilityConditionGroup] = field(default_factory=list)
    conditions: list[ApplicabilityCondition] = field(default_factory=list)
    sources: list[ApplicabilityRuleSource] = field(default_factory=list)

    @property
    def version_id(self) -> str:
        return str(self.version.id)

    @property
    def rule_id(self) -> str:
        return str(self.rule.id)

    @property
    def status(self) -> str:
        return self.version.interpretation_status


class InMemoryAuthoringStore:
    """In-memory store providing persistence abstraction for authoring workflows."""

    def __init__(self):
        self._rules: dict[str, ApplicabilityRule] = {}
        self._rules_by_key: dict[str, str] = {}
        self._versions: dict[str, ApplicabilityRuleVersion] = {}
        self._versions_by_rule: dict[str, list[str]] = {}
        self._groups: dict[str, list[ApplicabilityConditionGroup]] = {}
        self._conditions: dict[str, list[ApplicabilityCondition]] = {}
        self._sources: dict[str, list[ApplicabilityRuleSource]] = {}

    def save_rule(self, rule: ApplicabilityRule) -> None:
        rid = str(rule.id)
        self._rules[rid] = rule
        self._rules_by_key[rule.rule_key] = rid

    def get_rule(self, rule_id_or_key: str) -> ApplicabilityRule | None:
        if rule_id_or_key in self._rules:
            return self._rules[rule_id_or_key]
        if rule_id_or_key in self._rules_by_key:
            return self._rules[self._rules_by_key[rule_id_or_key]]
        return None

    def save_version(self, version: ApplicabilityRuleVersion) -> None:
        vid = str(version.id)
        rid = str(version.rule_id)
        self._versions[vid] = version
        v_list = self._versions_by_rule.setdefault(rid, [])
        if vid not in v_list:
            v_list.append(vid)

    def get_version(self, version_id: str) -> ApplicabilityRuleVersion | None:
        return self._versions.get(str(version_id))

    def get_versions_for_rule(self, rule_id: str) -> list[ApplicabilityRuleVersion]:
        v_ids = self._versions_by_rule.get(str(rule_id), [])
        return [self._versions[vid] for vid in v_ids]

    def set_groups(self, version_id: str, groups: list[ApplicabilityConditionGroup]) -> None:
        self._groups[str(version_id)] = list(groups)

    def get_groups(self, version_id: str) -> list[ApplicabilityConditionGroup]:
        return list(self._groups.get(str(version_id), []))

    def set_conditions(self, version_id: str, conditions: list[ApplicabilityCondition]) -> None:
        self._conditions[str(version_id)] = list(conditions)

    def get_conditions(self, version_id: str) -> list[ApplicabilityCondition]:
        return list(self._conditions.get(str(version_id), []))

    def set_sources(self, version_id: str, sources: list[ApplicabilityRuleSource]) -> None:
        self._sources[str(version_id)] = list(sources)

    def get_sources(self, version_id: str) -> list[ApplicabilityRuleSource]:
        return list(self._sources.get(str(version_id), []))

    def get_package(self, version_id: str) -> RulePackage | None:
        ver = self.get_version(version_id)
        if ver is None:
            return None
        rule = self.get_rule(str(ver.rule_id))
        if rule is None:
            return None
        groups = self.get_groups(version_id)
        conditions = self.get_conditions(version_id)
        sources = self.get_sources(version_id)
        return RulePackage(
            rule=rule,
            version=ver,
            groups=groups,
            conditions=conditions,
            sources=sources,
        )


class AuthoringService:
    """Orchestrates authoring lifecycle transitions and governance invariants."""

    def __init__(
        self,
        store: InMemoryAuthoringStore | None = None,
        linter: ApplicabilityLinter | None = None,
    ):
        self.store = store or InMemoryAuthoringStore()
        self.linter = linter or ApplicabilityLinter()

    # -----------------------------------------------------------------
    # Rule and Draft Version Creation
    # -----------------------------------------------------------------
    def create_rule(
        self,
        rule_key: str,
        created_by: str | None = None,
        rule_id: str | None = None,
    ) -> ApplicabilityRule:
        """Create a new applicability rule entity."""
        clean_key = (rule_key or "").strip()
        existing = self.store.get_rule(clean_key)
        if existing is not None:
            raise AuthoringValidationError(
                f"Rule with key '{clean_key}' already exists (id={existing.id})"
            )

        rule = ApplicabilityRule(
            id=rule_id or str(uuid4()),
            rule_key=clean_key,
            created_at=datetime.now(),
            created_by=created_by,
        )
        self.store.save_rule(rule)
        return rule

    def create_draft_version(
        self,
        rule_id: str,
        valid_from: date | None = None,
        valid_to: date | None = None,
        amendment_id: str | None = None,
        created_by: str | None = None,
        version_id: str | None = None,
        version_number: int | None = None,
    ) -> ApplicabilityRuleVersion:
        """Create the initial version (Version 1) for a rule in draft status."""
        rule = self.store.get_rule(rule_id)
        if rule is None:
            raise AuthoringValidationError(f"Rule '{rule_id}' does not exist")

        existing_versions = self.store.get_versions_for_rule(str(rule.id))
        if existing_versions:
            expected_next = max(v.version_number for v in existing_versions) + 1
            if version_number is not None and version_number != expected_next:
                raise VersionSequencingError(
                    f"Invalid version_number {version_number} for rule '{rule.rule_key}': "
                    f"expected next version {expected_next}"
                )
            assigned_number = expected_next
        else:
            if version_number is not None and version_number != 1:
                raise VersionSequencingError(
                    f"Initial version for rule '{rule.rule_key}' must be 1 (got {version_number})"
                )
            assigned_number = 1

        version = ApplicabilityRuleVersion(
            id=version_id or str(uuid4()),
            rule_id=rule.id,
            version_number=assigned_number,
            interpretation_status="draft",
            valid_from=valid_from,
            valid_to=valid_to,
            amendment_id=amendment_id,
            created_at=datetime.now(),
            created_by=created_by,
        )
        self.store.save_version(version)
        return version

    def create_next_version(
        self,
        rule_id: str,
        created_by: str | None = None,
        copy_from_version_id: str | None = None,
        valid_from: date | None = None,
        valid_to: date | None = None,
        amendment_id: str | None = None,
        new_version_id: str | None = None,
    ) -> RulePackage:
        """Create the next sequential version (N+1) as draft, optionally cloning logic."""
        rule = self.store.get_rule(rule_id)
        if rule is None:
            raise AuthoringValidationError(f"Rule '{rule_id}' does not exist")

        existing_versions = self.store.get_versions_for_rule(str(rule.id))
        if not existing_versions:
            raise VersionSequencingError(
                f"Cannot create next version for rule '{rule.rule_key}': no prior version exists. Use create_draft_version."
            )

        highest_version = max(v.version_number for v in existing_versions)
        next_version_num = highest_version + 1

        new_vid = new_version_id or str(uuid4())

        groups_to_save: list[ApplicabilityConditionGroup] = []
        conditions_to_save: list[ApplicabilityCondition] = []
        sources_to_save: list[ApplicabilityRuleSource] = []

        if copy_from_version_id is not None:
            prior_pkg = self.store.get_package(copy_from_version_id)
            if prior_pkg is None:
                raise AuthoringValidationError(
                    f"Source version '{copy_from_version_id}' to copy from does not exist"
                )

            # Map old group IDs to new group IDs
            group_id_map: dict[str, str] = {}
            for g in prior_pkg.groups:
                new_gid = str(uuid4())
                group_id_map[str(g.id)] = new_gid

            for g in prior_pkg.groups:
                new_parent = group_id_map.get(str(g.parent_group_id)) if g.parent_group_id else None
                groups_to_save.append(
                    ApplicabilityConditionGroup(
                        id=group_id_map[str(g.id)],
                        rule_version_id=new_vid,
                        parent_group_id=new_parent,
                        group_purpose=g.group_purpose,
                        boolean_operator=g.boolean_operator,
                        sequence=g.sequence,
                        review_status="draft",
                    )
                )

            cond_id_map: dict[str, str] = {}
            for c in prior_pkg.conditions:
                new_cid = str(uuid4())
                cond_id_map[str(c.id)] = new_cid
                new_target_gid = group_id_map.get(str(c.group_id), str(c.group_id))
                conditions_to_save.append(
                    ApplicabilityCondition(
                        id=new_cid,
                        group_id=new_target_gid,
                        fact_key=c.fact_key,
                        operator=c.operator,
                        expected_value=c.expected_value,
                        expected_unit=c.expected_unit,
                        sequence=c.sequence,
                        review_status="draft",
                    )
                )

            for s in prior_pkg.sources:
                new_sid = str(uuid4())
                target_gid = group_id_map.get(str(s.condition_group_id)) if s.condition_group_id else None
                target_cid = cond_id_map.get(str(s.condition_id)) if s.condition_id else None
                sources_to_save.append(
                    ApplicabilityRuleSource(
                        id=new_sid,
                        rule_version_id=new_vid,
                        requirement_id=s.requirement_id,
                        provision_id=s.provision_id,
                        schedule_id=s.schedule_id,
                        schedule_entry_id=s.schedule_entry_id,
                        table_id=s.table_id,
                        amendment_id=amendment_id or s.amendment_id,
                        condition_group_id=target_gid,
                        condition_id=target_cid,
                        source_role=s.source_role,
                        source_quote=s.source_quote,
                        source_reference=copy.deepcopy(s.source_reference),
                        review_status="draft",
                    )
                )

        new_version = ApplicabilityRuleVersion(
            id=new_vid,
            rule_id=rule.id,
            version_number=next_version_num,
            interpretation_status="draft",
            valid_from=valid_from,
            valid_to=valid_to,
            amendment_id=amendment_id,
            created_at=datetime.now(),
            created_by=created_by,
        )

        self.store.save_version(new_version)
        self.store.set_groups(new_vid, groups_to_save)
        self.store.set_conditions(new_vid, conditions_to_save)
        self.store.set_sources(new_vid, sources_to_save)

        return RulePackage(
            rule=rule,
            version=new_version,
            groups=groups_to_save,
            conditions=conditions_to_save,
            sources=sources_to_save,
        )

    # -----------------------------------------------------------------
    # Draft AST Mutation Guard (Only permitted on draft)
    # -----------------------------------------------------------------
    def add_condition_group(
        self,
        version_id: str,
        group: ApplicabilityConditionGroup,
    ) -> None:
        """Add a condition group to a draft rule version."""
        self._assert_version_mutable(version_id)
        current = self.store.get_groups(version_id)
        current.append(group)
        self.store.set_groups(version_id, current)

    def add_condition(
        self,
        version_id: str,
        condition: ApplicabilityCondition,
    ) -> None:
        """Add an atomic condition to a draft rule version."""
        self._assert_version_mutable(version_id)
        current = self.store.get_conditions(version_id)
        current.append(condition)
        self.store.set_conditions(version_id, current)

    def add_rule_source(
        self,
        version_id: str,
        source: ApplicabilityRuleSource,
    ) -> None:
        """Add a provenance source link to a draft rule version."""
        self._assert_version_mutable(version_id)
        current = self.store.get_sources(version_id)
        current.append(source)
        self.store.set_sources(version_id, current)

    def update_draft_version(
        self,
        version_id: str,
        valid_from: date | None = None,
        valid_to: date | None = None,
        amendment_id: str | None = None,
    ) -> ApplicabilityRuleVersion:
        """Update temporal/amendment fields of an editable draft version."""
        ver = self._assert_version_mutable(version_id)
        updated = replace(
            ver,
            valid_from=valid_from if valid_from is not None else ver.valid_from,
            valid_to=valid_to if valid_to is not None else ver.valid_to,
            amendment_id=amendment_id if amendment_id is not None else ver.amendment_id,
        )
        self.store.save_version(updated)
        return updated

    def _assert_version_mutable(self, version_id: str) -> ApplicabilityRuleVersion:
        ver = self.store.get_version(version_id)
        if ver is None:
            raise AuthoringValidationError(f"Rule version '{version_id}' does not exist")
        if ver.interpretation_status in IMMUTABLE_LIFECYCLE_STATES:
            raise ImmutabilityViolationError(
                f"Immutability violation: Version {ver.version_number} is '{ver.interpretation_status}' and cannot be modified. "
                f"Corrections or amendments must be authored as Version {ver.version_number + 1} in 'draft' status."
            )
        if ver.interpretation_status != "draft":
            raise ImmutabilityViolationError(
                f"Rule version is in '{ver.interpretation_status}' status. Only 'draft' versions can be modified."
            )
        return ver

    # -----------------------------------------------------------------
    # Lifecycle Transitions & Linter Validation Gating
    # -----------------------------------------------------------------
    def validate_package(self, package: RulePackage) -> LintResult:
        """Run the Stage 1 ApplicabilityLinter on a rule package."""
        return self.linter.lint(
            rule=package.rule,
            version=package.version,
            groups=package.groups,
            conditions=package.conditions,
            sources=package.sources,
        )

    def transition_to_in_review(self, version_id: str) -> ApplicabilityRuleVersion:
        """Transition a rule version from draft -> in_review.
        
        Requires full linter validation pass before state transition is allowed.
        """
        pkg = self._get_package_or_raise(version_id)
        current_status = pkg.version.interpretation_status

        self._check_transition_allowed(current_status, "in_review", pkg.version.version_number)

        # Candidate version in 'in_review' status for linting
        candidate_version = replace(pkg.version, interpretation_status="in_review")
        lint_res = self.linter.lint(
            rule=pkg.rule,
            version=candidate_version,
            groups=pkg.groups,
            conditions=pkg.conditions,
            sources=pkg.sources,
            previous_version=pkg.version,
        )
        if not lint_res.is_valid:
            lint_res.raise_if_invalid()

        # Update and save
        updated_version = candidate_version
        self.store.save_version(updated_version)
        return updated_version

    def transition_to_approved(
        self,
        version_id: str,
        reviewed_by: str,
        reviewed_at: datetime | None = None,
        review_note: str | None = None,
    ) -> ApplicabilityRuleVersion:
        """Transition a rule version from in_review -> approved.
        
        Strict human accreditation:
        - reviewed_by must be non-empty and must NOT represent an AI/system identity.
        - reviewed_at must be provided (or defaults to datetime.now()).
        - full linter validation must pass.
        """
        pkg = self._get_package_or_raise(version_id)
        current_status = pkg.version.interpretation_status

        self._check_transition_allowed(current_status, "approved", pkg.version.version_number)

        # Human Reviewer Invariant
        if not reviewed_by or not str(reviewed_by).strip():
            raise AuthoringValidationError(
                "Rule version cannot be approved without an identified human reviewer (reviewed_by)"
            )
        clean_reviewer = str(reviewed_by).strip()
        if clean_reviewer.lower() in AI_REVIEWER_IDENTIFIERS:
            raise AuthoringValidationError(
                f"AI/automated reviewer '{clean_reviewer}' cannot approve rule versions. Human legal review is strictly required"
            )

        review_time = reviewed_at or datetime.now()

        candidate_version = replace(
            pkg.version,
            interpretation_status="approved",
            reviewed_by=clean_reviewer,
            reviewed_at=review_time,
            review_note=review_note or pkg.version.review_note,
        )

        lint_res = self.linter.lint(
            rule=pkg.rule,
            version=candidate_version,
            groups=pkg.groups,
            conditions=pkg.conditions,
            sources=pkg.sources,
            previous_version=pkg.version,
        )
        if not lint_res.is_valid:
            lint_res.raise_if_invalid()

        self.store.save_version(candidate_version)
        return candidate_version

    def transition_to_rejected(
        self,
        version_id: str,
        reviewed_by: str | None = None,
        rejection_reason: str = "",
        reviewed_at: datetime | None = None,
    ) -> ApplicabilityRuleVersion:
        """Transition a rule version to rejected (terminal and immutable)."""
        pkg = self._get_package_or_raise(version_id)
        current_status = pkg.version.interpretation_status

        self._check_transition_allowed(current_status, "rejected", pkg.version.version_number)

        rejected_version = replace(
            pkg.version,
            interpretation_status="rejected",
            reviewed_by=reviewed_by or pkg.version.reviewed_by,
            reviewed_at=reviewed_at or datetime.now(),
            review_note=rejection_reason or "Rejected during authoring review",
        )
        self.store.save_version(rejected_version)
        return rejected_version

    def transition_to_retired(
        self,
        version_id: str,
        retired_by: str | None = None,
        retire_reason: str | None = None,
    ) -> ApplicabilityRuleVersion:
        """Transition an approved rule version to retired (terminal and immutable)."""
        pkg = self._get_package_or_raise(version_id)
        current_status = pkg.version.interpretation_status

        self._check_transition_allowed(current_status, "retired", pkg.version.version_number)

        retired_version = replace(
            pkg.version,
            interpretation_status="retired",
            review_note=(
                f"{pkg.version.review_note or ''} [Retired: {retire_reason}]".strip()
                if retire_reason
                else pkg.version.review_note
            ),
        )
        self.store.save_version(retired_version)
        return retired_version

    def _get_package_or_raise(self, version_id: str) -> RulePackage:
        pkg = self.store.get_package(version_id)
        if pkg is None:
            raise AuthoringValidationError(f"Rule version '{version_id}' does not exist")
        return pkg

    def _check_transition_allowed(
        self, current_status: str, target_status: str, version_number: int
    ) -> None:
        if current_status in IMMUTABLE_LIFECYCLE_STATES and current_status != "approved":
            raise ImmutabilityViolationError(
                f"Immutability violation: Version {version_number} is in terminal '{current_status}' status "
                f"and cannot be transitioned to '{target_status}'. Create a new version instead."
            )
        allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(current_status, frozenset())
        if target_status not in allowed:
            raise LifecycleTransitionError(
                f"Invalid lifecycle transition: '{current_status}' -> '{target_status}' is strictly forbidden."
            )
