"""Error hierarchy for Phase 7 Unified End-to-End Inspection Pipeline."""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all inspection pipeline errors."""
    pass


class InvalidPipelineInputError(PipelineError):
    """Raised when inspection request or its artifacts fail validation."""
    pass


class PipelineExecutionError(PipelineError):
    """Raised when an unrecoverable internal pipeline failure occurs."""
    pass


class OCRPipelineError(PipelineError):
    """Raised when OCR execution encounters a critical unhandled failure."""
    pass


class ApplicabilityPipelineError(PipelineError):
    """Raised when applicability evaluation fails critically."""
    pass


class RAGPipelineError(PipelineError):
    """Raised when Legal RAG retrieval encounters a critical error."""
    pass


class GeminiPipelineError(PipelineError):
    """Raised when Gemini reasoning encounters a critical pipeline failure."""
    pass


class VerificationPipelineError(PipelineError):
    """Raised when verification gate execution encounters an unexpected failure."""
    pass

