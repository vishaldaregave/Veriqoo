"""Pure, deterministic evaluation engine implementing Strong Kleene 3VL and Phase 3B semantics."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Sequence
from uuid import UUID

from backend.app.services.applicability.gating import (
    select_temporal_version,
    validate_group_hierarchy,
)
from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityDecision,
    ApplicabilityDecisionEvidence,
    ApplicabilityRuleSource,
    ApplicabilityRuleVersion,
    InspectionFact,
    TriState,
)
from backend.app.services.applicability.operators import evaluate_condition
from backend.app.services.applicability.provenance import create_decision, create_evidence
from backend.app.services.applicability.units import normalize_unit, to_decimal


def _deduplicate_facts(
    facts: Sequence[InspectionFact],
) -> tuple[dict[str, InspectionFact], dict[str, str]]:
    """Index facts by fact_key, deduplicating identicals and flagging conflicts.

    Returns:
        (fact_map, conflict_map)
        where conflict_map maps fact_key -> conflict_reason
    """
    grouped: dict[str, list[InspectionFact]] = {}
    for f in facts:
        grouped.setdefault(f.fact_key, []).append(f)

    fact_map: dict[str, InspectionFact] = {}
    conflict_map: dict[str, str] = {}

    for key, fact_list in grouped.items():
        if len(fact_list) == 1:
            fact_map[key] = fact_list[0]
            continue

        # Check if all facts in fact_list are identical
        first = fact_list[0]
        identical = True
        for other in fact_list[1:]:
            if other.fact_status != first.fact_status:
                identical = False
                break
            if normalize_unit(other.unit) != normalize_unit(first.unit):
                identical = False
                break
            # Compare values
            dec_first = to_decimal(first.value)
            dec_other = to_decimal(other.value)
            if dec_first is not None and dec_other is not None:
                if dec_first != dec_other:
                    identical = False
                    break
            elif other.value != first.value:
                identical = False
                break

        if identical:
            # Safely deduplicate
            fact_map[key] = first
        else:
            conflict_map[key] = "Conflicting inspection facts observed"
            # Create a conflict marker fact
            fact_map[key] = InspectionFact(
                id=str(uuid.uuid4()),
                run_id=first.run_id,
                fact_key=key,
                fact_status="unknown",
                value=None,
                unit=None,
            )

    return fact_map, conflict_map


class RuleTreeEvaluator:
    """Evaluates a single rule version's condition hierarchy against indexed facts."""

    def __init__(
        self,
        decision_id: str | UUID,
        groups: Sequence[ApplicabilityConditionGroup],
        conditions: Sequence[ApplicabilityCondition],
        sources: Sequence[ApplicabilityRuleSource],
        fact_map: dict[str, InspectionFact],
        conflict_map: dict[str, str],
    ):
        self.decision_id = decision_id
        self.groups = groups
        self.conditions = conditions
        self.sources = sources
        self.fact_map = fact_map
        self.conflict_map = conflict_map

        self.evidence_records: list[ApplicabilityDecisionEvidence] = []
        self.critical_unknown_fact_keys: set[str] = set()

        # Indexes for fast hierarchy navigation
        self.group_map = {str(g.id): g for g in groups}
        self.child_groups: dict[str, list[ApplicabilityConditionGroup]] = {}
        for g in groups:
            if g.parent_group_id is not None:
                self.child_groups.setdefault(str(g.parent_group_id), []).append(g)

        # Sort child groups by sequence
        for p_id in self.child_groups:
            self.child_groups[p_id].sort(key=lambda x: x.sequence)

        self.conditions_by_group: dict[str, list[ApplicabilityCondition]] = {}
        for c in conditions:
            self.conditions_by_group.setdefault(str(c.group_id), []).append(c)

        # Sort conditions by sequence
        for g_id in self.conditions_by_group:
            self.conditions_by_group[g_id].sort(key=lambda x: x.sequence)

        # Map condition_id -> source_link_id
        self.source_by_condition: dict[str, str | UUID] = {}
        for s in sources:
            if s.condition_id is not None:
                self.source_by_condition[str(s.condition_id)] = s.id

    def evaluate_group(self, group: ApplicabilityConditionGroup) -> tuple[TriState, set[str]]:
        """Evaluate a condition group and its children recursively using Strong Kleene logic.

        Returns:
            (TriState_outcome, set_of_relevant_unknown_fact_keys)
        """
        g_id = str(group.id)
        sub_groups = self.child_groups.get(g_id, [])
        leaf_conds = self.conditions_by_group.get(g_id, [])
        op = group.boolean_operator.upper()

        child_results: list[tuple[TriState, set[str]]] = []
        short_circuited = False
        group_state = TriState.TRUE if op == "AND" else TriState.FALSE
        all_unknown_keys: set[str] = set()

        # Helper to process child evaluation with short-circuiting
        def process_child(eval_state: TriState, unknown_keys: set[str]) -> bool:
            nonlocal group_state, short_circuited
            child_results.append((eval_state, unknown_keys))
            if op == "AND":
                group_state = TriState.kleene_and(group_state, eval_state)
                if group_state == TriState.FALSE:
                    short_circuited = True
                    return True
            else:  # OR
                group_state = TriState.kleene_or(group_state, eval_state)
                if group_state == TriState.TRUE:
                    short_circuited = True
                    return True
            return False

        # 1. Evaluate child groups
        remaining_sub_groups = list(sub_groups)
        while remaining_sub_groups:
            cg = remaining_sub_groups.pop(0)
            if short_circuited:
                self._mark_group_short_circuited(cg)
                continue
            c_res, c_unkeys = self.evaluate_group(cg)
            if process_child(c_res, c_unkeys):
                # Short-circuit triggered
                for rem_g in remaining_sub_groups:
                    self._mark_group_short_circuited(rem_g)
                break

        # 2. Evaluate leaf conditions
        remaining_leaf_conds = list(leaf_conds)
        while remaining_leaf_conds:
            cond = remaining_leaf_conds.pop(0)
            if short_circuited:
                self._mark_condition_short_circuited(cond)
                continue

            # Evaluate this leaf condition
            fact = self.fact_map.get(cond.fact_key)
            if cond.fact_key in self.conflict_map:
                eval_res = TriState.UNKNOWN
                reason = self.conflict_map[cond.fact_key]
            else:
                eval_res, reason = evaluate_condition(cond, fact)

            source_id = self.source_by_condition.get(str(cond.id))
            fact_id = fact.id if fact else None

            self.evidence_records.append(
                create_evidence(
                    decision_id=self.decision_id,
                    condition_id=cond.id,
                    fact_id=fact_id,
                    source_link_id=source_id,
                    evaluation=eval_res,
                    reason=reason,
                )
            )

            cond_unknowns = {cond.fact_key} if eval_res == TriState.UNKNOWN else set()
            if process_child(eval_res, cond_unknowns):
                for rem_c in remaining_leaf_conds:
                    self._mark_condition_short_circuited(rem_c)
                break

        # Compute relevant unknown keys that actually contributed to UNKNOWN
        relevant_unknowns: set[str] = set()
        if group_state == TriState.UNKNOWN:
            for c_state, c_keys in child_results:
                if c_state == TriState.UNKNOWN:
                    relevant_unknowns.update(c_keys)

        return group_state, relevant_unknowns

    def _mark_condition_short_circuited(self, condition: ApplicabilityCondition) -> None:
        source_id = self.source_by_condition.get(str(condition.id))
        self.evidence_records.append(
            create_evidence(
                decision_id=self.decision_id,
                condition_id=condition.id,
                fact_id=None,
                source_link_id=source_id,
                evaluation=TriState.NOT_EVALUATED,
                reason="Branch short-circuited by prior evaluation",
            )
        )

    def _mark_group_short_circuited(self, group: ApplicabilityConditionGroup) -> None:
        # Mark all nested conditions in this group as not_evaluated
        g_id = str(group.id)
        for cond in self.conditions_by_group.get(g_id, []):
            self._mark_condition_short_circuited(cond)
        for cg in self.child_groups.get(g_id, []):
            self._mark_group_short_circuited(cg)


def evaluate_rule(
    rule_version: ApplicabilityRuleVersion,
    groups: Sequence[ApplicabilityConditionGroup],
    conditions: Sequence[ApplicabilityCondition],
    sources: Sequence[ApplicabilityRuleSource],
    facts: Sequence[InspectionFact],
    inspection_date: date | None = None,
    run_id: str | UUID | None = None,
) -> tuple[ApplicabilityDecision, list[ApplicabilityDecisionEvidence]]:
    """Pure, deterministic evaluation of an applicability rule version.

    Enforces:
    1. Approved Version Gate: reject draft/in_review/rejected/retired.
    2. Temporal Validity: verify version validity on inspection_date.
    3. Hierarchy Invariants: exactly 1 root applicability group, >= 0 root exception groups, acyclic.
    4. Strong Kleene 3VL evaluation with safe duplicate handling and exception synthesis.
    """
    actual_run_id = run_id or str(uuid.uuid4())
    decision_id = str(uuid.uuid4())

    # 1. Approved Version Gate
    if rule_version.interpretation_status != "approved":
        decision = create_decision(
            run_id=actual_run_id,
            rule_version_id=rule_version.id,
            result="unknown",
            reason=f"Rule version status is '{rule_version.interpretation_status}', not 'approved'",
        )
        return decision, []

    # 2. Temporal Gating for this specific version
    temporal_match, temporal_err = select_temporal_version([rule_version], inspection_date)
    if temporal_err is not None:
        decision = create_decision(
            run_id=actual_run_id,
            rule_version_id=rule_version.id,
            result="unknown",
            reason=temporal_err,
        )
        return decision, []

    # 3. Root Group & Hierarchy Validation
    is_valid, diag, root_app, root_excs = validate_group_hierarchy(groups)
    if not is_valid or root_app is None:
        decision = create_decision(
            run_id=actual_run_id,
            rule_version_id=rule_version.id,
            result="unknown",
            reason=diag or "Malformed rule hierarchy",
        )
        return decision, []

    # 4. Ingest and deduplicate facts
    fact_map, conflict_map = _deduplicate_facts(facts)

    # 5. Core 3VL Evaluation
    evaluator = RuleTreeEvaluator(
        decision_id=decision_id,
        groups=groups,
        conditions=conditions,
        sources=sources,
        fact_map=fact_map,
        conflict_map=conflict_map,
    )

    # Evaluate Root Applicability Group (A)
    res_a, unkeys_a = evaluator.evaluate_group(root_app)

    # Evaluate Root Exception Groups (E)
    # If 0 root exception groups: E = FALSE
    # If >= 1 root exception groups: E = OR(E_i)
    if not root_excs:
        res_e = TriState.FALSE
        unkeys_e: set[str] = set()
    else:
        res_e = TriState.FALSE
        unkeys_e = set()
        for eg in root_excs:
            sub_res, sub_keys = evaluator.evaluate_group(eg)
            res_e = TriState.kleene_or(res_e, sub_res)
            if sub_res == TriState.UNKNOWN:
                unkeys_e.update(sub_keys)

    # 6. Synthesize Final Applicability Decision using Approved Exception Semantics
    # A FALSE + E FALSE   -> not_applicable
    # A FALSE + E TRUE    -> not_applicable
    # A FALSE + E UNKNOWN -> not_applicable
    # A TRUE  + E FALSE   -> applicable
    # A TRUE  + E TRUE    -> not_applicable
    # A TRUE  + E UNKNOWN -> unknown
    # A UNKNOWN + E FALSE   -> unknown
    # A UNKNOWN + E TRUE    -> not_applicable
    # A UNKNOWN + E UNKNOWN -> unknown

    evidence_needed: list[str] = []

    if res_a == TriState.FALSE:
        final_result = "not_applicable"
        final_reason = "Core applicability criteria not met"
    elif res_a == TriState.TRUE:
        if res_e == TriState.TRUE:
            final_result = "not_applicable"
            final_reason = "Exempted by statutory exception"
        elif res_e == TriState.FALSE:
            final_result = "applicable"
            final_reason = "Core applicability criteria satisfied and no statutory exception applies"
        else:  # res_e == TriState.UNKNOWN
            final_result = "unknown"
            final_reason = "Core criteria satisfied but statutory exception unresolved"
            evidence_needed = list(unkeys_e)
    else:  # res_a == TriState.UNKNOWN
        if res_e == TriState.TRUE:
            final_result = "not_applicable"
            final_reason = "Exempted by statutory exception regardless of core applicability"
        else:  # res_e in (FALSE, UNKNOWN)
            final_result = "unknown"
            final_reason = "Core applicability criteria unresolved"
            evidence_needed = list(unkeys_a)

    decision = create_decision(
        run_id=actual_run_id,
        rule_version_id=rule_version.id,
        result=final_result,
        reason=final_reason,
        evidence_needed=evidence_needed,
    )
    decision.id = decision_id

    return decision, evaluator.evidence_records

