"""Phase 6 — Gemini Evidence Reasoning Engine.

Provides constrained, prompt-injection defended evidence reasoning connecting
legal metrology requirements with structured evidence candidates.
"""

from backend.app.services.gemini.client import (
    BaseGeminiClient,
    FakeGeminiClient,
    RealGeminiClient,
)
from backend.app.services.gemini.config import GeminiConfig
from backend.app.services.gemini.errors import (
    GeminiAuthenticationError,
    GeminiConfigError,
    GeminiError,
    GeminiInvalidResponseError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiValidationError,
)
from backend.app.services.gemini.models import (
    EvidenceSufficiency,
    GeminiEvidenceAssessment,
    GeminiRecommendation,
    GeminiVerificationRequest,
)
from backend.app.services.gemini.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    format_evidence_reasoning_prompt,
)
from backend.app.services.gemini.service import GeminiEvidenceService

__all__ = [
    "GeminiConfig",
    "GeminiVerificationRequest",
    "GeminiEvidenceAssessment",
    "GeminiRecommendation",
    "EvidenceSufficiency",
    "BaseGeminiClient",
    "RealGeminiClient",
    "FakeGeminiClient",
    "GeminiEvidenceService",
    "PROMPT_VERSION",
    "SYSTEM_INSTRUCTION",
    "format_evidence_reasoning_prompt",
    "GeminiError",
    "GeminiConfigError",
    "GeminiAuthenticationError",
    "GeminiRateLimitError",
    "GeminiTimeoutError",
    "GeminiInvalidResponseError",
    "GeminiValidationError",
    "GeminiProviderError",
]
