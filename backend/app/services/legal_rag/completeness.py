"""Completeness and coverage evaluation for Legal RAG (Phase 4A).

Explicitly separates:
- SEMANTIC RETRIEVAL ("What legal material is top-K relevant?")
from:
- COMPLETENESS ("Have all applicable requirements identified by the applicability engine been retrieved?")

A top-K vector search MUST NOT be treated as proof of legal completeness.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from backend.app.services.legal_rag.models import (
    CompletenessStatus,
    LegalEntityType,
    LegalSearchResult,
    RetrievalCompleteness,
)


def evaluate_completeness(
    requested_requirement_ids: Iterable[str],
    results: Sequence[LegalSearchResult],
    semantic_top_k_count: int = 0,
) -> RetrievalCompleteness:
    """Evaluate whether all required/applicable legal requirements have been resolved to legal context."""
    req_set = frozenset(str(rid).strip() for rid in requested_requirement_ids if str(rid).strip())

    # Find requirement IDs present in the retrieved results
    retrieved_set = frozenset(
        str(r.entity_id)
        for r in results
        if r.entity_type == LegalEntityType.REQUIREMENT and r.provenance and r.provenance.is_valid()
    )

    covered = req_set.intersection(retrieved_set)
    missing = req_set - retrieved_set

    notes: list[str] = []

    if not req_set:
        status = CompletenessStatus.COMPLETE if results else CompletenessStatus.EMPTY
        is_complete = True
        notes.append("No explicit requirement IDs were requested; semantic retrieval mode active.")
    elif not missing:
        status = CompletenessStatus.COMPLETE
        is_complete = True
        notes.append(
            f"All {len(req_set)} applicable statutory requirement(s) successfully resolved to legal context."
        )
    elif covered:
        status = CompletenessStatus.PARTIAL
        is_complete = False
        notes.append(
            f"PARTIAL COMPLETENESS: {len(covered)}/{len(req_set)} requirements resolved. "
            f"Missing {len(missing)} requirement(s): {sorted(list(missing))}."
        )
        notes.append(
            f"Semantic top-K search ({semantic_top_k_count} items) cannot substitute for "
            f"missing applicable statutory obligations."
        )
    else:
        status = CompletenessStatus.EMPTY
        is_complete = False
        notes.append(
            f"ZERO COMPLETENESS: None of the {len(req_set)} applicable requirements were resolved."
        )

    return RetrievalCompleteness(
        status=status,
        requested_requirement_ids=req_set,
        retrieved_requirement_ids=retrieved_set,
        missing_requirement_ids=missing,
        is_complete=is_complete,
        semantic_top_k_count=semantic_top_k_count,
        notes=tuple(notes),
    )

