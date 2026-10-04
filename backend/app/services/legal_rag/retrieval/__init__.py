"""Legal Retrieval Architecture package (Phase 4C).

Exports canonical retrieval models, resolvers, expanders, deduplicators,
rankers, completeness checkers, repositories, and the LegalRetrievalService.
"""

from __future__ import annotations

from backend.app.services.legal_rag.retrieval.completeness import CompletenessChecker
from backend.app.services.legal_rag.retrieval.coverage import (
    EXPECTED_LEGAL_ENTITY_COUNTS,
    CoverageReport,
    EmbeddingCoverageChecker,
)
from backend.app.services.legal_rag.retrieval.deduplication import DeterministicDeduplicator
from backend.app.services.legal_rag.retrieval.direct import DirectLookupResolver
from backend.app.services.legal_rag.retrieval.expansion import StatutoryRelationshipExpander
from backend.app.services.legal_rag.retrieval.models import (
    CoverageReport,
    LegalContextPackage,
    RetrievalRequest,
    RetrievedEntityContext,
)
from backend.app.services.legal_rag.retrieval.ranking import DeterministicRanker
from backend.app.services.legal_rag.retrieval.repository import (
    InMemoryLegalCorpusRepository,
    LegalCorpusRepository,
    SupabaseLegalCorpusRepository,
)
from backend.app.services.legal_rag.retrieval.semantic import SemanticSearchResolver
from backend.app.services.legal_rag.retrieval.service import LegalRetrievalService

__all__ = [
    "CompletenessChecker",
    "CoverageReport",
    "DeterministicDeduplicator",
    "DeterministicRanker",
    "DirectLookupResolver",
    "EmbeddingCoverageChecker",
    "EXPECTED_LEGAL_ENTITY_COUNTS",
    "InMemoryLegalCorpusRepository",
    "LegalContextPackage",
    "LegalCorpusRepository",
    "LegalRetrievalService",
    "RetrievalRequest",
    "RetrievedEntityContext",
    "SemanticSearchResolver",
    "StatutoryRelationshipExpander",
    "SupabaseLegalCorpusRepository",
]

