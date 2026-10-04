"""Application service orchestration for applicability evaluation runs."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from backend.app.services.applicability.evaluator import evaluate_rule
from backend.app.services.applicability.gating import (
    filter_approved_versions,
    select_temporal_version,
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
)
from backend.app.services.applicability.provenance import create_decision


class ApplicabilityService:
    """Orchestrates applicability evaluations over inspection runs and rule sets."""

    @classmethod
    def evaluate_run(
        cls,
        run: ApplicabilityRun,
        facts: Sequence[InspectionFact],
        rules: Sequence[ApplicabilityRule],
        rule_versions: Sequence[ApplicabilityRuleVersion],
        groups: Sequence[ApplicabilityConditionGroup],
        conditions: Sequence[ApplicabilityCondition],
        sources: Sequence[ApplicabilityRuleSource] = (),
    ) -> list[tuple[ApplicabilityDecision, list[ApplicabilityDecisionEvidence]]]:
        """Evaluate an inspection run against candidate applicability rules.

        Pure execution: does not execute database queries or mutations.
        """
        results: list[tuple[ApplicabilityDecision, list[ApplicabilityDecisionEvidence]]] = []

        # Index versions, groups, conditions, and sources by rule / version
        versions_by_rule: dict[str, list[ApplicabilityRuleVersion]] = {}
        for v in rule_versions:
            versions_by_rule.setdefault(str(v.rule_id), []).append(v)

        groups_by_version: dict[str, list[ApplicabilityConditionGroup]] = {}
        for g in groups:
            groups_by_version.setdefault(str(g.rule_version_id), []).append(g)

        conditions_by_group: dict[str, list[ApplicabilityCondition]] = {}
        for c in conditions:
            conditions_by_group.setdefault(str(c.group_id), []).append(c)

        sources_by_version: dict[str, list[ApplicabilityRuleSource]] = {}
        for s in sources:
            sources_by_version.setdefault(str(s.rule_version_id), []).append(s)

        for rule in rules:
            rule_id_str = str(rule.id)
            cand_versions = versions_by_rule.get(rule_id_str, [])

            # 1. Approved Version Gate
            approved_versions = filter_approved_versions(cand_versions)

            # 2. Temporal Selection Gate
            selected_version, temporal_err = select_temporal_version(
                approved_versions, run.inspection_date
            )

            if temporal_err is not None or selected_version is None:
                # If no approved version matched or ambiguous, emit decision
                # Use first version ID if available for provenance or a placeholder
                fallback_version_id = (
                    selected_version.id
                    if selected_version
                    else (cand_versions[0].id if cand_versions else rule.id)
                )
                err_decision = create_decision(
                    run_id=run.id,
                    rule_version_id=fallback_version_id,
                    result="unknown",
                    reason=temporal_err or "no approved rule version matches inspection date",
                )
                results.append((err_decision, []))
                continue

            # 3. Gather components for selected version
            v_id_str = str(selected_version.id)
            v_groups = groups_by_version.get(v_id_str, [])
            v_group_ids = {str(g.id) for g in v_groups}
            v_conditions = [
                c for g_id in v_group_ids for c in conditions_by_group.get(g_id, [])
            ]
            v_sources = sources_by_version.get(v_id_str, [])

            # 4. Pure evaluation
            decision, evidence_list = evaluate_rule(
                rule_version=selected_version,
                groups=v_groups,
                conditions=v_conditions,
                sources=v_sources,
                facts=facts,
                inspection_date=run.inspection_date,
                run_id=run.id,
            )
            results.append((decision, evidence_list))

        return results

