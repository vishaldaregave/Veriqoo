"""Formal Retrieval Contract interface and query validation for Legal RAG (Phase 4A).

The legal RAG layer provides legal context and provenance for requirements that
have already been determined to be applicable by the Applicability Engine.
RAG does NOT determine applicability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.app.services.legal_rag.models import (
    LegalRetrievalQuery,
    LegalRetrievalResponse,
    RetrievalConfig,
    RetrievalMode,
)


class LegalRetrievalContract(ABC):
    """Formal contract for Veriqoo legal retrieval services."""

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self.config = config or RetrievalConfig()

    @abstractmethod
    def retrieve(self, query: LegalRetrievalQuery) -> LegalRetrievalResponse:
        """Execute a retrieval query according to the requested mode and filters."""
        raise NotImplementedError

    @abstractmethod
    def retrieve_for_applicable_requirements(
        self,
        requirement_ids: list[str],
        context_filters: dict[str, Any] | None = None,
    ) -> LegalRetrievalResponse:
        """Requirement-first retrieval: Retrieve complete legal context for requirements

        already established as applicable by the Applicability Engine.
        Guarantees completeness evaluation against the provided requirement IDs.
        """
        raise NotImplementedError

    def validate_query(self, query: LegalRetrievalQuery) -> list[str]:
        """Validate a retrieval query against statutory and architectural constraints.

        Returns a list of validation error messages. An empty list signifies a valid query.
        """
        errors: list[str] = []

        if not isinstance(query, LegalRetrievalQuery):
            return ["Query must be an instance of LegalRetrievalQuery"]

        # Limit checks
        if query.limit <= 0:
            errors.append(f"Query limit must be positive, got {query.limit}")
        elif query.limit > 500:
            errors.append(f"Query limit exceeds maximum allowed of 500, got {query.limit}")

        # Mode check
        if not isinstance(query.mode, RetrievalMode):
            try:
                RetrievalMode(query.mode)
            except (ValueError, TypeError):
                errors.append(f"Invalid retrieval mode '{query.mode}'")

        # Threshold check
        if query.min_similarity_threshold < 0.0 or query.min_similarity_threshold > 1.0:
            errors.append(
                f"Similarity threshold must be between 0.0 and 1.0, got {query.min_similarity_threshold}"
            )

        # Empty query signal check
        has_signal = (
            bool(query.query_text and query.query_text.strip())
            or bool(query.requirement_ids)
            or bool(query.provision_ids)
            or bool(query.schedule_ids)
            or bool(query.schedule_entry_ids)
            or bool(query.table_ids)
            or bool(query.amendment_ids)
        )
        if not has_signal:
            errors.append(
                "Query has no retrieval signals: query_text and all entity ID lists are empty"
            )

        # Requirement IDs validation
        for rid in query.requirement_ids:
            if not rid or not str(rid).strip():
                errors.append("Empty or blank requirement_id in query")

        # Provision IDs validation
        for pid in query.provision_ids:
            if not isinstance(pid, int) or pid <= 0:
                errors.append(f"provision_id must be a positive integer, got {pid}")

        # In Requirement Context mode, at least one entity ID or query text should be provided
        if query.mode == RetrievalMode.REQUIREMENT_CONTEXT and not (
            query.requirement_ids
            or query.provision_ids
            or query.schedule_entry_ids
            or query.table_ids
            or query.amendment_ids
            or (query.query_text and query.query_text.strip())
        ):
            errors.append(
                "REQUIREMENT_CONTEXT mode requires requirement_ids, entity IDs, or specific query_text"
            )

        return errors

