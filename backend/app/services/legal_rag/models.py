"""Data models and value objects for the Legal RAG retrieval contract (Phase 4A).

Defines formal types for:
- Legal entities (requirements, provisions, schedule entries, tables, amendments)
- Retrieval queries and modes
- Legal provenance and source references
- Ranking metadata and provisional thresholds
- Deterministic search results
- Completeness and coverage tracking
- Temporal status and validity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID


class LegalEntityType(str, Enum):
    """The five canonical legal entities in the Veriqoo legal corpus."""

    REQUIREMENT = "requirement"
    PROVISION = "provision"
    SCHEDULE_ENTRY = "schedule_entry"
    TABLE = "table"
    AMENDMENT = "amendment"


class RetrievalMode(str, Enum):
    """Retrieval operational modes defining retrieval intent and strategy."""

    SEMANTIC_CONTEXT = "semantic_context"
    REQUIREMENT_CONTEXT = "requirement_context"
    APPLICABILITY_CONTEXT = "applicability_context"


class RetrievalMethod(str, Enum):
    """Specific mechanism used to retrieve a legal result."""

    EXACT_ID = "exact_id"
    REQUIREMENT_LOOKUP = "requirement_lookup"
    SEMANTIC_VECTOR = "semantic_vector"
    LEXICAL_SEARCH = "lexical_search"
    HIERARCHICAL_TRAVERSAL = "hierarchical_traversal"
    PROVENANCE_EXPANSION = "provenance_expansion"


class TemporalStatus(str, Enum):
    """Temporal validity status of a legal entity."""

    CURRENT = "current"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class CompletenessStatus(str, Enum):
    """Completeness evaluation state for applicable requirement coverage."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"


@dataclass(frozen=True)
class LegalProvenance:
    """Rigorous statutory provenance linking a retrieved entity to the authoritative corpus."""

    source_identifier: str
    document_id: int | str
    provision_id: int | None = None
    rule_number: str | None = None
    sub_rule_number: str | None = None
    clause: str | None = None
    schedule_id: str | None = None
    schedule_number: str | None = None
    schedule_entry_id: str | None = None
    table_id: str | None = None
    amendment_id: str | None = None
    source_page: int | None = None
    source_page_end: int | None = None
    source_line_start: int | None = None
    source_line_end: int | None = None
    source_quote: str = ""
    source_reference: dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Verify that provenance is genuine and grounded in the source corpus."""
        if not self.source_identifier or not str(self.source_identifier).strip():
            return False
        if not self.source_quote or not self.source_quote.strip():
            return False
        quote_lower = self.source_quote.lower()
        if "gemini" in quote_lower or "synthetic" in quote_lower or "[paraphrased]" in quote_lower:
            return False
        if "vector search" in quote_lower or "model inferred" in quote_lower:
            return False
        return True


@dataclass(frozen=True)
class RankingMetadata:
    """Deterministic ranking signals and relevance metadata."""

    score: float = 0.0
    lexical_score: float | None = None
    semantic_similarity: float | None = None
    provenance_specificity: float = 1.0
    requirement_priority: int = 1
    is_provisional_threshold: bool = True
    matched_terms: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class LegalSearchResult:
    """A single retrieved legal entity with complete statutory context and provenance."""

    entity_type: LegalEntityType
    entity_id: str
    source_identifier: str
    title: str | None = None
    relevant_text: str = ""
    normalized_requirement: str | None = None
    source_quote: str = ""
    source_reference: dict[str, Any] = field(default_factory=dict)
    provenance: LegalProvenance | None = None
    ranking: RankingMetadata = field(default_factory=RankingMetadata)
    retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID
    parent_entity_id: str | None = None
    parent_entity_type: LegalEntityType | None = None
    linked_entity_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    temporal_status: TemporalStatus = TemporalStatus.UNKNOWN
    effective_from: date | None = None
    effective_to: date | None = None

    # Structured details for Schedule Entries & Tables
    commodity_text: str | None = None
    quantity_text: str | None = None
    raw_cells: list[dict[str, Any]] = field(default_factory=list)
    table_headers: list[str] = field(default_factory=list)

    def format_for_context(self) -> str:
        """Produce clean, structured context for verification prompts."""
        lines = [
            f"[{self.entity_type.value.upper()}] ID: {self.entity_id}",
        ]
        if self.title:
            lines.append(f"Title: {self.title}")
        if self.normalized_requirement:
            lines.append(f"Normalized Obligation: {self.normalized_requirement}")
        if self.relevant_text:
            lines.append(f"Text: {self.relevant_text}")
        if self.commodity_text:
            lines.append(f"Commodity: {self.commodity_text}")
        if self.quantity_text:
            lines.append(f"Prescribed Quantity: {self.quantity_text}")
        if self.source_quote:
            lines.append(f"Statutory Quote: \"{self.source_quote}\"")
        if self.provenance and self.provenance.rule_number:
            prov_str = f"Rule {self.provenance.rule_number}"
            if self.provenance.sub_rule_number:
                prov_str += f"({self.provenance.sub_rule_number})"
            if self.provenance.clause:
                prov_str += f"({self.provenance.clause})"
            lines.append(f"Legal Reference: {prov_str}")
        lines.append(f"Retrieval Method: {self.retrieval_method.value}")
        return "\n".join(lines)


@dataclass(frozen=True)
class RetrievalCompleteness:
    """Formal completeness contract verifying coverage of applicable requirements."""

    status: CompletenessStatus
    requested_requirement_ids: frozenset[str]
    retrieved_requirement_ids: frozenset[str]
    missing_requirement_ids: frozenset[str]
    is_complete: bool
    semantic_top_k_count: int
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class LegalRetrievalQuery:
    """Formal retrieval request object."""

    query_text: str = ""
    requirement_ids: list[str] = field(default_factory=list)
    provision_ids: list[int] = field(default_factory=list)
    schedule_ids: list[str] = field(default_factory=list)
    schedule_entry_ids: list[str] = field(default_factory=list)
    table_ids: list[str] = field(default_factory=list)
    amendment_ids: list[str] = field(default_factory=list)
    mode: RetrievalMode = RetrievalMode.REQUIREMENT_CONTEXT
    context_filters: dict[str, Any] = field(default_factory=dict)
    as_of_date: date | None = None
    allow_temporal_unknown: bool = True
    limit: int = 50
    min_similarity_threshold: float = 0.65  # Provisional threshold, configuration-driven


@dataclass
class LegalRetrievalResponse:
    """Formal retrieval response object containing retrieved legal entities, completeness, and metadata."""

    results: list[LegalSearchResult] = field(default_factory=list)
    completeness: RetrievalCompleteness | None = None
    query: LegalRetrievalQuery | None = None
    total_found: int = 0
    execution_time_ms: float = 0.0
    no_result_reason: str | None = None

    @property
    def formatted_context(self) -> str:
        """Formatted legal context for downstream Gemini compliance verification."""
        if not self.results:
            return "No applicable legal provisions retrieved."
        sections = [res.format_for_context() for res in self.results]
        return "\n\n---\n\n".join(sections)


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for Legal RAG retrieval services."""

    provisional_vector_threshold: float = 0.65
    enable_provenance_expansion: bool = True
    deduplication_strategy: str = "preserve_hierarchical_provenance"
    max_results: int = 50
    allow_unknown_temporal: bool = True

