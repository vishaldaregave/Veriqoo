"""Canonical data models for Phase 4C Legal Retrieval Architecture.

Defines:
- RetrievalRequest: Structured legal retrieval query contract.
- RetrievedEntityContext: Enriched retrieved entity with legal context and provenance.
- LegalContextPackage: Canonical retrieval result container preserving complete provenance.
- CoverageReport: Legal corpus embedding coverage tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from backend.app.services.legal_rag.models import (
    CompletenessStatus,
    LegalEntityType,
    LegalProvenance,
    RankingMetadata,
    RetrievalCompleteness,
    RetrievalConfig,
    RetrievalMethod,
    RetrievalMode,
    TemporalStatus,
)


@dataclass
class RetrievedEntityContext:
    """Enriched retrieved legal entity with full statutory context, provenance, and relationships."""

    entity_type: LegalEntityType
    entity_id: str
    source_identifier: str
    source_reference: dict[str, Any] = field(default_factory=dict)
    legal_text: str = ""
    source_quote: str = ""
    similarity_score: float | None = None
    retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID
    retrieval_methods: list[RetrievalMethod] = field(default_factory=list)
    provenance: LegalProvenance | None = None
    linked_requirement_ids: list[str] = field(default_factory=list)
    linked_provision_ids: list[int] = field(default_factory=list)
    linked_schedule_entry_ids: list[str] = field(default_factory=list)
    linked_table_ids: list[str] = field(default_factory=list)
    linked_amendment_ids: list[str] = field(default_factory=list)
    deduplicated: bool = False
    deduplication_notes: list[str] = field(default_factory=list)
    ranking_tier: int = 1  # 1: Direct Lookup, 2: Explicit Expansion, 3: Semantic Retrieval
    title: str | None = None
    commodity_text: str | None = None
    quantity_text: str | None = None
    temporal_status: TemporalStatus = TemporalStatus.UNKNOWN
    effective_from: date | None = None
    effective_to: date | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.retrieval_methods and self.retrieval_method:
            self.retrieval_methods = [self.retrieval_method]

    def format_for_context(self) -> str:
        """Produce structured statutory context for downstream inspection/verification."""
        lines = [
            f"[{self.entity_type.value.upper()}] ID: {self.entity_id}",
            f"Source Identifier: {self.source_identifier}",
        ]
        if self.title:
            lines.append(f"Title: {self.title}")
        if self.commodity_text:
            lines.append(f"Commodity: {self.commodity_text}")
        if self.quantity_text:
            lines.append(f"Prescribed Quantity: {self.quantity_text}")
        if self.legal_text:
            lines.append(f"Legal Text: {self.legal_text}")
        if self.source_quote:
            lines.append(f"Statutory Quote: \"{self.source_quote}\"")
        if self.provenance:
            ref_parts = []
            if self.provenance.rule_number:
                ref = f"Rule {self.provenance.rule_number}"
                if self.provenance.sub_rule_number:
                    ref += f"({self.provenance.sub_rule_number})"
                if self.provenance.clause:
                    ref += f"({self.provenance.clause})"
                ref_parts.append(ref)
            if self.provenance.schedule_id:
                ref_parts.append(f"Schedule: {self.provenance.schedule_id}")
            if self.provenance.table_id:
                ref_parts.append(f"Table: {self.provenance.table_id}")
            if self.provenance.amendment_id:
                ref_parts.append(f"Amendment: {self.provenance.amendment_id}")
            if ref_parts:
                lines.append(f"Statutory Grounding: {', '.join(ref_parts)}")
        methods_str = ", ".join(m.value for m in self.retrieval_methods) if self.retrieval_methods else self.retrieval_method.value
        lines.append(f"Retrieval Method(s): {methods_str}")
        if self.similarity_score is not None:
            lines.append(f"Similarity Score: {self.similarity_score:.4f}")
        return "\n".join(lines)


@dataclass
class RetrievalRequest:
    """Formal retrieval request model for legal context retrieval (Phase 4C)."""

    query_text: str = ""
    requirement_ids: list[str] = field(default_factory=list)
    provision_ids: list[int] = field(default_factory=list)
    schedule_entry_ids: list[str] = field(default_factory=list)
    table_ids: list[str] = field(default_factory=list)
    amendment_ids: list[str] = field(default_factory=list)
    rule_identifiers: list[str] = field(default_factory=list)
    applicability_output: Any | None = None
    entity_types: list[LegalEntityType] | None = None
    context_filters: dict[str, Any] = field(default_factory=dict)
    source_filters: dict[str, Any] = field(default_factory=dict)
    limit: int = 50
    min_similarity_threshold: float = 0.65
    mode: RetrievalMode = RetrievalMode.REQUIREMENT_CONTEXT
    as_of_date: date | None = None
    allow_temporal_unknown: bool = True
    expand_statutory_context: bool = True

    def __post_init__(self) -> None:
        # Extract applicable requirement IDs from applicability output if supplied
        if self.applicability_output is not None:
            extracted = self.extract_applicable_requirement_ids()
            for rid in extracted:
                if rid not in self.requirement_ids:
                    self.requirement_ids.append(rid)

    def extract_applicable_requirement_ids(self) -> list[str]:
        """Safely extract requirement IDs marked APPLICABLE from applicability output.

        Preserves UNKNOWN decisions without converting UNKNOWN to false or not_applicable.
        """
        if not self.applicability_output:
            return []

        applicable_ids: list[str] = []

        # If it's a dict
        if isinstance(self.applicability_output, dict):
            # Check if dict itself is a single decision
            self_decision = str(self.applicability_output.get("decision") or self.applicability_output.get("status") or "").lower()
            if self_decision == "applicable":
                rid = self.applicability_output.get("requirement_id") or self.applicability_output.get("rule_id") or self.applicability_output.get("id")
                if rid and str(rid) not in applicable_ids:
                    applicable_ids.append(str(rid))

            # Check decisions list
            decisions = self.applicability_output.get("decisions") or self.applicability_output.get("results") or []
            if isinstance(decisions, list):
                for dec in decisions:
                    if isinstance(dec, dict):
                        status = str(dec.get("decision") or dec.get("status") or "").lower()
                        if status == "applicable":
                            rid = dec.get("requirement_id") or dec.get("rule_id") or dec.get("id")
                            if rid:
                                applicable_ids.append(str(rid))
                    else:
                        status = str(getattr(dec, "decision", getattr(dec, "status", ""))).lower()
                        if status in ("applicable", "applicabilitydecisiontype.applicable"):
                            rid = getattr(dec, "requirement_id", getattr(dec, "rule_id", getattr(dec, "id", None)))
                            if rid:
                                applicable_ids.append(str(rid))
            # Also check direct applicable_requirement_ids field
            direct_rids = self.applicability_output.get("applicable_requirement_ids", [])
            for rid in direct_rids:
                if str(rid) not in applicable_ids:
                    applicable_ids.append(str(rid))

        # If it's an object with decisions or results attribute
        elif hasattr(self.applicability_output, "decisions") or hasattr(self.applicability_output, "results"):
            decisions = getattr(self.applicability_output, "decisions", getattr(self.applicability_output, "results", []))
            for dec in decisions:
                status = str(getattr(dec, "decision", getattr(dec, "status", ""))).lower()
                if "applicable" in status and "not_applicable" not in status:
                    rid = getattr(dec, "requirement_id", getattr(dec, "rule_id", getattr(dec, "id", None)))
                    if rid:
                        applicable_ids.append(str(rid))

        # If it's an iterable of decision objects
        elif isinstance(self.applicability_output, (list, tuple)):
            for dec in self.applicability_output:
                if isinstance(dec, dict):
                    status = str(dec.get("decision") or dec.get("status") or "").lower()
                    if status == "applicable":
                        rid = dec.get("requirement_id") or dec.get("id")
                        if rid:
                            applicable_ids.append(str(rid))
                else:
                    status = str(getattr(dec, "decision", getattr(dec, "status", ""))).lower()
                    if "applicable" in status and "not_applicable" not in status:
                        rid = getattr(dec, "requirement_id", getattr(dec, "id", None))
                        if rid:
                            applicable_ids.append(str(rid))

        return applicable_ids

    def validate(self) -> list[str]:
        """Validate request parameters against Phase 4C constraints."""
        errors: list[str] = []
        if self.limit <= 0:
            errors.append(f"Limit must be positive integer, got {self.limit}")
        if self.limit > 200:
            errors.append(f"Limit cannot exceed 200, got {self.limit}")
        if not (0.0 <= self.min_similarity_threshold <= 1.0):
            errors.append(f"Similarity threshold must be between 0.0 and 1.0, got {self.min_similarity_threshold}")

        has_query = bool(self.query_text and self.query_text.strip())
        has_reqs = bool(self.requirement_ids)
        has_provs = bool(self.provision_ids)
        has_scheds = bool(self.schedule_entry_ids)
        has_tbls = bool(self.table_ids)
        has_amends = bool(self.amendment_ids)
        has_rules = bool(self.rule_identifiers)
        has_applicability = bool(self.applicability_output)

        if not (has_query or has_reqs or has_provs or has_scheds or has_tbls or has_amends or has_rules or has_applicability):
            errors.append("Empty retrieval query: at least one lookup criterion or query_text must be provided")

        return errors


@dataclass
class LegalContextPackage:
    """Canonical, provenance-preserving container of retrieved legal entities (Phase 4C)."""

    request: RetrievalRequest
    entities: list[RetrievedEntityContext] = field(default_factory=list)
    completeness: RetrievalCompleteness | None = None
    total_retrieved: int = 0
    execution_time_ms: float = 0.0
    empty_reason: str | None = None

    @property
    def formatted_context(self) -> str:
        """Formatted legal context for downstream Gemini compliance verification."""
        if not self.entities:
            return self.empty_reason or "No applicable legal provisions retrieved."
        sections = [ent.format_for_context() for ent in self.entities]
        return "\n\n---\n\n".join(sections)

    def get_by_id(self, entity_id: str) -> RetrievedEntityContext | None:
        """Find a retrieved entity by its ID."""
        for ent in self.entities:
            if ent.entity_id == str(entity_id):
                return ent
        return None

    def requirements(self) -> list[RetrievedEntityContext]:
        """Return all retrieved legal requirements."""
        return [e for e in self.entities if e.entity_type == LegalEntityType.REQUIREMENT]

    def provisions(self) -> list[RetrievedEntityContext]:
        """Return all retrieved legal provisions."""
        return [e for e in self.entities if e.entity_type == LegalEntityType.PROVISION]

    def schedule_entries(self) -> list[RetrievedEntityContext]:
        """Return all retrieved schedule entries."""
        return [e for e in self.entities if e.entity_type == LegalEntityType.SCHEDULE_ENTRY]

    def tables(self) -> list[RetrievedEntityContext]:
        """Return all retrieved legal tables."""
        return [e for e in self.entities if e.entity_type == LegalEntityType.TABLE]

    def amendments(self) -> list[RetrievedEntityContext]:
        """Return all retrieved legal amendments."""
        return [e for e in self.entities if e.entity_type == LegalEntityType.AMENDMENT]


@dataclass(frozen=True)
class CoverageReport:
    """Audit report comparing expected vs actual embedding counts across the 5 legal entities."""

    expected_counts: dict[str, int]
    actual_counts: dict[str, int]
    missing_counts: dict[str, int]
    coverage_percentages: dict[str, float]
    total_expected: int
    total_actual: int
    is_fully_populated: bool

    def summary(self) -> str:
        lines = [
            f"Legal Corpus Embedding Coverage: {self.total_actual}/{self.total_expected} "
            f"({(self.total_actual / self.total_expected * 100):.1f}%)",
            f"Fully Populated: {self.is_fully_populated}",
        ]
        for etype in ["requirement", "provision", "schedule_entry", "table", "amendment"]:
            exp = self.expected_counts.get(etype, 0)
            act = self.actual_counts.get(etype, 0)
            pct = self.coverage_percentages.get(etype, 0.0)
            lines.append(f"  - {etype}: {act}/{exp} ({pct:.1f}%)")
        return "\n".join(lines)

