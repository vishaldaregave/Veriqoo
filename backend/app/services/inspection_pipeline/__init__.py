"""Phase 7 — Unified End-to-End Inspection Pipeline Module.

Orchestrates the 10-step inspection workflow connecting image ingestion, OCR,
evidence normalization, applicability gating, Legal RAG, Gemini reasoning, and safety verification.
"""

from backend.app.services.inspection_pipeline.errors import (
    ApplicabilityPipelineError,
    GeminiPipelineError,
    InvalidPipelineInputError,
    OCRPipelineError,
    PipelineError,
    PipelineExecutionError,
    RAGPipelineError,
    VerificationPipelineError,
)
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineContext,
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import (
    InspectionReport,
    compute_overall_status,
)

__all__ = [
    "OverallInspectionStatus",
    "InspectionPipelineRequest",
    "InspectionPipelineContext",
    "InspectionReport",
    "compute_overall_status",
    "InspectionPipelineOrchestrator",
    "PipelineError",
    "InvalidPipelineInputError",
    "PipelineExecutionError",
    "OCRPipelineError",
    "ApplicabilityPipelineError",
    "RAGPipelineError",
    "GeminiPipelineError",
    "VerificationPipelineError",
]

