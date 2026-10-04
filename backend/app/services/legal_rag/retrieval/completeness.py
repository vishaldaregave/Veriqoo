"""Retrieval completeness verification against requested requirements (Phase 4C).

Grounded in authoritative corpus:
- Explicitly compares requested requirement IDs vs retrieved requirement IDs.
- Detects missing requirements and reports them explicitly.
- Enforces statutory principle: retrieval_complete != semantic_top_k_complete.
"""

from __future__ import annotations

from typing import Sequence

from backend.app.services.legal_rag.models import (
    CompletenessStatus,
    LegalEntityType,
    RetrievalCompleteness,
)
from backend.app.services.legal_rag.retrieval.models import RetrievedEntityContext


class CompletenessChecker:
    """Evaluates coverage of requested requirements in retrieved legal context."""

    @staticmethod
    def evaluate(
        requested_requirement_ids: Sequence[str],
        entities: Sequence[RetrievedEntityContext],
    ) -> RetrievalCompleteness:
        """Verify whether all requested requirements were successfully retrieved."""
        req_set = frozenset(str(r).strip() for r in requested_requirement_ids if str(r).strip())

        # Collect retrieved requirement IDs
        retrieved_req_ids = frozenset(
            str(e.entity_id).strip()
            for e in entities
            if e.entity_type == LegalEntityType.REQUIREMENT
        )

        if not req_set:
            return RetrievalCompleteness(
                status=CompletenessStatus.COMPLETE,
                requested_requirement_ids=frozenset(),
                retrieved_requirement_ids=retrieved_req_ids,
                missing_requirement_ids=frozenset(),
                is_complete=True,
                semantic_top_k_count=len(entities),
                notes=("No specific requirement IDs were requested.",),
            )

        found_set = req_set.intersection(retrieved_req_ids)
        missing_set = req_set - found_set
        is_complete = len(missing_set) == 0

        notes: list[str] = []
        if is_complete:
            status = CompletenessStatus.COMPLETE
            notes.append(f"All {len(req_set)} requested legal requirements were successfully retrieved.")
        elif found_set:
            status = CompletenessStatus.PARTIAL
            missing_sorted = sorted(missing_set)
            notes.append(
                f"Partial legal coverage: {len(found_set)}/{len(req_set)} retrieved. "
                f"Missing {len(missing_set)} requirement(s): {', '.join(missing_sorted)}."
            )
        else:
            status = CompletenessStatus.EMPTY
            notes.append(
                f"Zero requested legal requirements retrieved. Missing all {len(req_set)} requirement(s)."
            )

        return RetrievalCompleteness(
            status=status,
            requested_requirement_ids=req_set,
            retrieved_requirement_ids=found_set,
            missing_requirement_ids=missing_set,
            is_complete=is_complete,
            semantic_top_k_count=len(entities),
            notes=tuple(notes),
        )

