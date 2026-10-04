"""Embedding client interfaces and implementations for Phase 4B.

Provides:
- EmbeddingClient (abstract interface)
- GeminiEmbeddingClient (production client for gemini-embedding-001)
- MockEmbeddingClient (deterministic unit test client with zero external dependencies)
"""

from __future__ import annotations

import hashlib
import logging
import math
import struct
import time
from abc import ABC, abstractmethod
from typing import Sequence

import requests

logger = logging.getLogger(__name__)


class EmbeddingGenerationError(RuntimeError):
    """Raised when an embedding request fails or returns invalid dimensions."""
    pass


class EmbeddingClient(ABC):
    """Abstract interface for statutory legal embedding clients."""

    @property
    @abstractmethod
    def provider(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        """Generate embedding vector for a single text string."""
        raise NotImplementedError

    @abstractmethod
    def embed_batch(
        self,
        texts: Sequence[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 20,
    ) -> list[list[float]]:
        """Generate embeddings for a batch of text strings with safe chunking and retries."""
        raise NotImplementedError

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding vector for a retrieval query (task_type=RETRIEVAL_QUERY)."""
        return self.embed_text(query, task_type="RETRIEVAL_QUERY")


class GeminiEmbeddingClient(EmbeddingClient):
    """Production client using Google Gemini gemini-embedding-001 (3072 dimensions)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        dimension: int = 3072,
        max_retries: int = 2,
        base_retry_delay: float = 5.0,
        request_timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key.strip() if api_key else ""
        if not self.api_key:
            raise EmbeddingGenerationError("GEMINI_API_KEY must be configured for GeminiEmbeddingClient.")
        self._model = model
        self._dimension = dimension
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.request_timeout = request_timeout

    @property
    def provider(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        results = self.embed_batch([text], task_type=task_type, batch_size=1)
        if not results:
            raise EmbeddingGenerationError("Gemini returned empty embedding result.")
        return results[0]

    def embed_batch(
        self,
        texts: Sequence[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 20,
    ) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Process in chunks
        for i in range(0, len(texts), batch_size):
            chunk = list(texts[i : i + batch_size])
            chunk_embeddings = self._embed_chunk_with_retry(chunk, task_type=task_type)
            all_embeddings.extend(chunk_embeddings)

        return all_embeddings

    def _embed_chunk_with_retry(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:batchEmbedContents"
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        requests_payload = [
            {
                "model": f"models/{self._model}",
                "content": {"parts": [{"text": t}]},
                "taskType": task_type,
            }
            for t in texts
        ]

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    endpoint,
                    params=params,
                    headers=headers,
                    json={"requests": requests_payload},
                    timeout=self.request_timeout,
                )
                if response.ok:
                    body = response.json()
                    raw_embeddings = body.get("embeddings", [])
                    if len(raw_embeddings) != len(texts):
                        raise EmbeddingGenerationError(
                            f"Expected {len(texts)} embeddings, received {len(raw_embeddings)}"
                        )
                    results: list[list[float]] = []
                    for item in raw_embeddings:
                        vals = item.get("values", [])
                        if len(vals) != self._dimension:
                            raise EmbeddingGenerationError(
                                f"Expected dimension {self._dimension}, received {len(vals)}"
                            )
                        results.append([float(v) for v in vals])
                    return results

                # Handle HTTP errors
                error_msg = f"HTTP {response.status_code}: {response.text}"
                last_error = EmbeddingGenerationError(f"Gemini batch embedding failed: {error_msg}")

                # Retry on 429 (rate limit) or 5xx (server error)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    delay = self.base_retry_delay * attempt
                    if response.status_code == 429:
                        logger.warning(
                            "Gemini 429 rate limit encountered. Waiting %.1fs before retry %d/%d...",
                            delay, attempt + 1, self.max_retries
                        )
                        print(f"  [Rate Limit 429] Waiting {delay:.1f}s before retry {attempt + 1}/{self.max_retries}...")
                    time.sleep(delay)
                    continue

                raise last_error

            except (requests.RequestException, EmbeddingGenerationError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = self.base_retry_delay * attempt
                    time.sleep(delay)
                    continue
                raise EmbeddingGenerationError(f"Gemini batch embedding failed after {self.max_retries} attempts: {last_error}") from exc

        raise EmbeddingGenerationError(f"Gemini batch embedding failed: {last_error}")


class CachedEmbeddingClient(EmbeddingClient):
    """Wrapper around an EmbeddingClient that caches query and text embeddings."""

    def __init__(
        self,
        inner_client: EmbeddingClient,
        cache_file_path: str | None = None,
    ) -> None:
        self.inner_client = inner_client
        self.cache_file_path = cache_file_path
        self._cache: dict[str, list[float]] = {}
        self.load_cache()

    @property
    def provider(self) -> str:
        return self.inner_client.provider

    @property
    def model(self) -> str:
        return self.inner_client.model

    @property
    def dimension(self) -> int:
        return self.inner_client.dimension

    def _get_cache_key(self, text: str, task_type: str) -> str:
        norm = text.strip()
        key_str = f"{self.model}:{self.dimension}:{task_type}:{norm}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def load_cache(self) -> None:
        import os
        import json
        if self.cache_file_path and os.path.exists(self.cache_file_path):
            try:
                with open(self.cache_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache.update(data)
            except Exception as e:
                logger.warning("Failed to load cache from %s: %s", self.cache_file_path, e)

    def save_cache(self) -> None:
        import os
        import json
        if self.cache_file_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.cache_file_path)), exist_ok=True)
                with open(self.cache_file_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f)
            except Exception as e:
                logger.warning("Failed to save cache to %s: %s", self.cache_file_path, e)

    def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        key = self._get_cache_key(text, task_type)
        if key in self._cache:
            return self._cache[key]
        vector = self.inner_client.embed_text(text, task_type=task_type)
        self._cache[key] = vector
        self.save_cache()
        return vector

    def embed_batch(
        self,
        texts: Sequence[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 20,
    ) -> list[list[float]]:
        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []

        for idx, text in enumerate(texts):
            key = self._get_cache_key(text, task_type)
            if key in self._cache:
                results[idx] = self._cache[key]
            else:
                missing_indices.append(idx)
                missing_texts.append(text)

        if missing_texts:
            computed = self.inner_client.embed_batch(
                missing_texts, task_type=task_type, batch_size=batch_size
            )
            for idx, text, vec in zip(missing_indices, missing_texts, computed):
                key = self._get_cache_key(text, task_type)
                self._cache[key] = vec
                results[idx] = vec
            self.save_cache()

        return [r for r in results if r is not None]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_text(query, task_type="RETRIEVAL_QUERY")


class MockEmbeddingClient(EmbeddingClient):
    """Deterministic synthetic embedding client for unit tests.

    Produces mathematically consistent, unit-normalized 3072-dimensional vectors
    derived from text SHA-256 hashes without making network calls.
    """

    def __init__(
        self,
        dimension: int = 3072,
        model: str = "gemini-embedding-001",
        provider: str = "mock_gemini",
        failure_count: int = 0,
    ) -> None:
        self._dimension = dimension
        self._model = model
        self._provider = provider
        self.failure_count = failure_count
        self.call_count = 0

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        self.call_count += 1
        if self.failure_count > 0:
            self.failure_count -= 1
            raise EmbeddingGenerationError("Simulated mock embedding transient failure")

        return self._generate_vector(text)

    def embed_batch(
        self,
        texts: Sequence[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 20,
    ) -> list[list[float]]:
        if not texts:
            return []

        results: list[list[float]] = []
        for text in texts:
            results.append(self.embed_text(text, task_type=task_type))
        return results

    def _generate_vector(self, text: str) -> list[float]:
        """Generate a deterministic 3072-dim pseudo-vector from text hash."""
        seed_hash = hashlib.sha256(text.encode("utf-8")).digest()
        # Generate 3072 float values from hash expansion
        values: list[float] = []
        # Expand 32-byte hash using counter
        for idx in range(self._dimension):
            counter_bytes = idx.to_bytes(4, byteorder="big")
            sub_hash = hashlib.sha256(seed_hash + counter_bytes).digest()[:4]
            # Convert 4 bytes to an integer and scale to [-1.0, 1.0]
            int_val = struct.unpack(">i", sub_hash)[0]
            values.append(int_val / 2147483648.0)

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]
