"""Veriqoo Legal RAG Architecture, Retrieval Contract & Embeddings (Phase 4A & 4B).

Provides:
- LegalRetrievalContract & LegalRetrievalService
- LegalRetrievalQuery & LegalRetrievalResponse
- LegalSearchResult & LegalProvenance
- Completeness and coverage tracking
- Deterministic deduplication, ranking, and temporal validity
- EmbeddingClient, Store, TextBuilders, and Generator (Phase 4B)
"""

from backend.app.services.legal_rag.completeness import evaluate_completeness
from backend.app.services.legal_rag.contract import (
    LegalRetrievalContract,
)
from backend.app.services.legal_rag.deduplication import deduplicate_results
from backend.app.services.legal_rag.embeddings import (
    EmbeddingBatchResult,
    EmbeddingClient,
    EmbeddingGenerationError,
    EmbeddingProviderConfig,
    EntityEmbeddingRecord,
    EmbeddingStore,
    GeminiEmbeddingClient,
    InMemoryEmbeddingStore,
    LegalEmbeddingGenerator,
    MockEmbeddingClient,
    SupabaseEmbeddingStore,
    build_amendment_embedding_text,
    build_provision_embedding_text,
    build_requirement_embedding_text,
    build_schedule_entry_embedding_text,
    build_table_embedding_text,
    compute_embedding_text_hash,
)
from backend.app.services.legal_rag.models import (
    CompletenessStatus,
    LegalEntityType,
    LegalProvenance,
    LegalRetrievalQuery,
    LegalRetrievalResponse,
    LegalSearchResult,
    RankingMetadata,
    RetrievalCompleteness,
    RetrievalConfig,
    RetrievalMethod,
    RetrievalMode,
    TemporalStatus,
)
from backend.app.services.legal_rag.provenance import (
    ProvenanceValidationError,
    merge_provenance,
    validate_provenance,
)
from backend.app.services.legal_rag.ranking import (
    apply_provisional_threshold,
    rank_results,
)
from backend.app.services.legal_rag.retrieval import (
    CompletenessChecker,
    CoverageReport,
    DeterministicDeduplicator,
    DeterministicRanker,
    DirectLookupResolver,
    EmbeddingCoverageChecker,
    EXPECTED_LEGAL_ENTITY_COUNTS,
    InMemoryLegalCorpusRepository,
    LegalContextPackage,
    LegalCorpusRepository,
    RetrievalRequest,
    RetrievedEntityContext,
    SemanticSearchResolver,
    StatutoryRelationshipExpander,
    SupabaseLegalCorpusRepository,
)
from backend.app.services.legal_rag.schedule_table import (
    build_schedule_entry_result,
    build_table_result,
    format_schedule_entry_text,
)
from backend.app.services.legal_rag.service import LegalRetrievalService
from backend.app.services.legal_rag.temporal import resolve_temporal_status

__all__ = [
    "CompletenessChecker",
    "CompletenessStatus",
    "CoverageReport",
    "DeterministicDeduplicator",
    "DeterministicRanker",
    "DirectLookupResolver",
    "EmbeddingBatchResult",
    "EmbeddingClient",
    "EmbeddingCoverageChecker",
    "EmbeddingGenerationError",
    "EmbeddingProviderConfig",
    "EntityEmbeddingRecord",
    "EmbeddingStore",
    "EXPECTED_LEGAL_ENTITY_COUNTS",
    "GeminiEmbeddingClient",
    "InMemoryEmbeddingStore",
    "InMemoryLegalCorpusRepository",
    "LegalContextPackage",
    "LegalCorpusRepository",
    "LegalEmbeddingGenerator",
    "LegalEntityType",
    "LegalProvenance",
    "LegalRetrievalContract",
    "LegalRetrievalQuery",
    "LegalRetrievalResponse",
    "LegalRetrievalService",
    "LegalSearchResult",
    "MockEmbeddingClient",
    "ProvenanceValidationError",
    "RankingMetadata",
    "RetrievalCompleteness",
    "RetrievalConfig",
    "RetrievalMethod",
    "RetrievalMode",
    "RetrievalRequest",
    "RetrievedEntityContext",
    "SemanticSearchResolver",
    "StatutoryRelationshipExpander",
    "SupabaseEmbeddingStore",
    "SupabaseLegalCorpusRepository",
    "TemporalStatus",
    "apply_provisional_threshold",
    "build_amendment_embedding_text",
    "build_provision_embedding_text",
    "build_requirement_embedding_text",
    "build_schedule_entry_embedding_text",
    "build_table_embedding_text",
    "build_table_result",
    "build_schedule_entry_result",
    "compute_embedding_text_hash",
    "deduplicate_results",
    "evaluate_completeness",
    "format_schedule_entry_text",
    "merge_provenance",
    "rank_results",
    "resolve_temporal_status",
    "validate_provenance",
]

