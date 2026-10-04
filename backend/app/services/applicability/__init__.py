"""Phase 3B Applicability Evaluation Engine package."""

from backend.app.services.applicability.evaluator import evaluate_rule
from backend.app.services.applicability.gating import (
    filter_approved_versions,
    select_temporal_version,
    validate_group_hierarchy,
)
from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityDecision,
    ApplicabilityDecisionEvidence,
    ApplicabilityRule,
    ApplicabilityRuleSource,
    ApplicabilityRuleVersion,
    ApplicabilityRun,
    InspectionFact,
    TriState,
)
from backend.app.services.applicability.authoring import (
    AuthoringService,
    AuthoringValidationError,
    InMemoryAuthoringStore,
    LifecycleTransitionError,
    RulePackage,
    VersionSequencingError,
)
from backend.app.services.applicability.linter import (
    ApplicabilityLinter,
    CANONICAL_FACT_KEYS,
    ImmutabilityViolationError,
    LintResult,
    LintValidationError,
    lint_rule_version,
)
from backend.app.services.applicability.operators import evaluate_condition
from backend.app.services.applicability.pilot_candidates import (
    build_all_pilot_candidates,
    build_candidate_1_manufacturer_identity,
    build_candidate_2_importer_identity,
    build_candidate_3_rule_3_chapter_exemption,
    build_candidate_4_rule_26_a_small_package_exemption,
    build_candidate_5_mrp_declaration,
)
from backend.app.services.applicability.service import ApplicabilityService
from backend.app.services.applicability.units import (
    convert_quantity,
    get_unit_dimension,
    is_reviewed_unit,
    normalize_unit,
    to_decimal,
)

__all__ = [
    "ApplicabilityCondition",
    "ApplicabilityConditionGroup",
    "ApplicabilityDecision",
    "ApplicabilityDecisionEvidence",
    "ApplicabilityLinter",
    "ApplicabilityRule",
    "ApplicabilityRuleSource",
    "ApplicabilityRuleVersion",
    "ApplicabilityRun",
    "ApplicabilityService",
    "AuthoringService",
    "AuthoringValidationError",
    "CANONICAL_FACT_KEYS",
    "ImmutabilityViolationError",
    "InMemoryAuthoringStore",
    "LifecycleTransitionError",
    "LintResult",
    "LintValidationError",
    "RulePackage",
    "VersionSequencingError",
    "build_all_pilot_candidates",
    "build_candidate_1_manufacturer_identity",
    "build_candidate_2_importer_identity",
    "build_candidate_3_rule_3_chapter_exemption",
    "build_candidate_4_rule_26_a_small_package_exemption",
    "build_candidate_5_mrp_declaration",
    "lint_rule_version",
    "InspectionFact",
    "TriState",
    "convert_quantity",
    "evaluate_condition",
    "evaluate_rule",
    "filter_approved_versions",
    "get_unit_dimension",
    "is_reviewed_unit",
    "normalize_unit",
    "select_temporal_version",
    "to_decimal",
    "validate_group_hierarchy",
]

