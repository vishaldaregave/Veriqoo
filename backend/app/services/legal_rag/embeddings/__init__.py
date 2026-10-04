"""Legal corpus embedding layer for Veriqoo Legal RAG (Phase 4B).

Provides:
- EntityEmbeddingRecord, EmbeddingBatchResult, EmbeddingProviderConfig
- Deterministic text builders for all 5 legal entities
- EmbeddingClient, GeminiEmbeddingClient, MockEmbeddingClient
- EmbeddingStore, InMemoryEmbeddingStore, SupabaseEmbeddingStore
- LegalEmbeddingGenerator
"""

from backend.app.services.legal_rag.embeddings.client import (
    EmbeddingClient,
    EmbeddingGenerationError,
    GeminiEmbeddingClient,
    MockEmbeddingClient,
)
from backend.app.services.legal_rag.embeddings.generator import LegalEmbeddingGenerator
from backend.app.services.legal_rag.embeddings.models import (
    EmbeddingBatchResult,
    EmbeddingProviderConfig,
    EntityEmbeddingRecord,
)
from backend.app.services.legal_rag.embeddings.store import (
    EmbeddingStore,
    InMemoryEmbeddingStore,
    SupabaseEmbeddingStore,
)
from backend.app.services.legal_rag.embeddings.text_builder import (
    build_amendment_embedding_text,
    build_provision_embedding_text,
    build_requirement_embedding_text,
    build_schedule_entry_embedding_text,
    build_table_embedding_text,
    compute_embedding_text_hash,
)

__all__ = [
    "EmbeddingBatchResult",
    "EmbeddingClient",
    "EmbeddingGenerationError",
    "EmbeddingProviderConfig",
    "EntityEmbeddingRecord",
    "EmbeddingStore",
    "GeminiEmbeddingClient",
    "InMemoryEmbeddingStore",
    "LegalEmbeddingGenerator",
    "MockEmbeddingClient",
    "SupabaseEmbeddingStore",
    "build_amendment_embedding_text",
    "build_provision_embedding_text",
    "build_requirement_embedding_text",
    "build_schedule_entry_embedding_text",
    "build_table_embedding_text",
    "compute_embedding_text_hash",
]
