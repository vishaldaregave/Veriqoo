"""Statutory Legal RAG Retrieval Service implementation (Phase 4C).

Orchestrates:
1. Request validation
2. Direct legal lookup for known authoritative IDs (takes precedence over semantic search)
3. Explicit statutory relationship expansion (Req -> Prov, Prov -> Schedule/Table, Entity -> Amendment)
4. Semantic vector search using legal_corpus_embeddings and EmbeddingClient
5. Deterministic metadata and entity-type filtering
6. Deterministic deduplication preserving best score, all methods, and combined provenance
7. Multi-tier deterministic ranking (Direct > Explicit Expansion > Semantic)
8. Completeness and coverage validation (identifies missing applicable requirement IDs)
9. Embedding coverage checking
"""

from __future__ import annotations

import time
from typing import Any

from backend.app.services.legal_rag.embeddings.client import EmbeddingClient
from backend.app.services.legal_rag.models import (
    LegalEntityType,
    RetrievalConfig,
)
from backend.app.services.legal_rag.retrieval.completeness import CompletenessChecker
from backend.app.services.legal_rag.retrieval.coverage import (
    CoverageReport,
    EmbeddingCoverageChecker,
)
from backend.app.services.legal_rag.retrieval.deduplication import DeterministicDeduplicator
from backend.app.services.legal_rag.retrieval.direct import DirectLookupResolver
from backend.app.services.legal_rag.retrieval.expansion import StatutoryRelationshipExpander
from backend.app.services.legal_rag.retrieval.models import (
    LegalContextPackage,
    RetrievalRequest,
    RetrievedEntityContext,
)
from backend.app.services.legal_rag.retrieval.ranking import DeterministicRanker
from backend.app.services.legal_rag.retrieval.repository import (
    InMemoryLegalCorpusRepository,
    LegalCorpusRepository,
)
from backend.app.services.legal_rag.retrieval.semantic import SemanticSearchResolver


class LegalRetrievalService:
    """Production Legal Retrieval Service operating under the Phase 4C retrieval architecture."""

    def __init__(
        self,
        repository: LegalCorpusRepository | None = None,
        embedding_client: EmbeddingClient | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.repository: LegalCorpusRepository = repository or InMemoryLegalCorpusRepository()
        self.embedding_client = embedding_client
        self.config = config or RetrievalConfig()

        self.direct_resolver = DirectLookupResolver(self.repository)
        self.expander = StatutoryRelationshipExpander(self.repository)
        self.semantic_resolver = SemanticSearchResolver(self.repository, self.embedding_client)
        self.coverage_checker = EmbeddingCoverageChecker(self.repository)

    def retrieve(self, request: RetrievalRequest) -> LegalContextPackage:
        """Execute complete, provenance-preserving statutory retrieval for a request."""
        start_time = time.perf_counter()

        # 1. Validate request
        errors = request.validate()
        if errors:
            return LegalContextPackage(
                request=request,
                entities=[],
                completeness=None,
                total_retrieved=0,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                empty_reason=f"Validation failed: {'; '.join(errors)}",
            )

        # 2. Direct legal lookup (Priority Tier 1)
        direct_entities = self.direct_resolver.resolve(request)

        # 3. Explicit statutory relationship expansion (Priority Tier 2)
        expanded_entities: list[RetrievedEntityContext] = []
        if request.expand_statutory_context and direct_entities:
            expanded_entities = self.expander.expand(
                direct_entities,
                expand_amendments=True,
                expand_schedules_and_tables=True,
            )

        # 4. Semantic vector search (Priority Tier 3)
        semantic_entities: list[RetrievedEntityContext] = []
        if request.query_text and request.query_text.strip():
            semantic_entities = self.semantic_resolver.search(request)

        # 5. Combine all candidates
        all_candidates = direct_entities + expanded_entities + semantic_entities

        # 6. Metadata and entity-type filtering
        filtered_candidates = self._apply_filters(all_candidates, request)

        # 7. Deterministic deduplication
        deduped = DeterministicDeduplicator.deduplicate(filtered_candidates)

        # 8. Deterministic ranking
        ranked = DeterministicRanker.rank(deduped)

        # Apply configurable limit
        final_entities = ranked[: request.limit]

        # 9. Completeness evaluation
        completeness = CompletenessChecker.evaluate(
            requested_requirement_ids=request.requirement_ids,
            entities=final_entities,
        )

        # 10. Reason determination if empty
        empty_reason = None
        if not final_entities:
            if request.requirement_ids:
                empty_reason = (
                    f"Requested legal requirement(s) {request.requirement_ids} could not be resolved from authoritative corpus."
                )
            elif request.query_text:
                empty_reason = "No legal provisions matched the query criteria above the minimum similarity threshold."
            else:
                empty_reason = "No matching authoritative legal provisions or requirements found."

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return LegalContextPackage(
            request=request,
            entities=final_entities,
            completeness=completeness,
            total_retrieved=len(final_entities),
            execution_time_ms=elapsed_ms,
            empty_reason=empty_reason,
        )

    def retrieve_for_applicability(
        self,
        applicability_output: Any,
        context_filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> LegalContextPackage:
        """Requirement-First Retrieval: Consume Applicability Engine output directly.

        Preserves UNKNOWN decisions without converting UNKNOWN to false or not_applicable.
        """
        request = RetrievalRequest(
            applicability_output=applicability_output,
            context_filters=context_filters or {},
            limit=limit,
        )
        return self.retrieve(request)

    def check_embedding_coverage(self) -> CoverageReport:
        """Audit embedding population across the five legal corpus entities."""
        return self.coverage_checker.check_coverage()

    def _apply_filters(
        self,
        candidates: list[RetrievedEntityContext],
        request: RetrievalRequest,
    ) -> list[RetrievedEntityContext]:
        """Apply deterministic filters matching existing database fields."""
        if not candidates:
            return []

        filtered = candidates

        # Entity type filter
        if request.entity_types:
            allowed_types = set(request.entity_types)
            filtered = [c for c in filtered if c.entity_type in allowed_types]

        # Context filters
        if request.context_filters:
            rule_filter = request.context_filters.get("rule_number")
            if rule_filter is not None:
                filtered = [
                    c for c in filtered
                    if (c.provenance and str(c.provenance.rule_number) == str(rule_filter))
                    or str(c.metadata.get("rule_number")) == str(rule_filter)
                ]

            sched_filter = request.context_filters.get("schedule_id")
            if sched_filter is not None:
                filtered = [
                    c for c in filtered
                    if (c.provenance and str(c.provenance.schedule_id) == str(sched_filter))
                    or str(c.metadata.get("schedule_id")) == str(sched_filter)
                ]

            table_filter = request.context_filters.get("table_id")
            if table_filter is not None:
                filtered = [
                    c for c in filtered
                    if (c.provenance and str(c.provenance.table_id) == str(table_filter))
                    or str(c.entity_id) == str(table_filter)
                ]

        # Source filters
        if request.source_filters:
            src_id_filter = request.source_filters.get("source_identifier")
            if src_id_filter:
                filtered = [c for c in filtered if c.source_identifier == src_id_filter]

        return filtered

