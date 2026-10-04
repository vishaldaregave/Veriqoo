"""Error hierarchy for Phase 6 Gemini Evidence Reasoning Engine."""

from __future__ import annotations


class GeminiError(Exception):
    """Base exception for all Gemini evidence reasoning errors."""
    pass


class GeminiConfigError(GeminiError):
    """Raised when Gemini configuration (API key, model, timeouts) is missing or invalid."""
    pass


class GeminiAuthenticationError(GeminiError):
    """Raised when Gemini API authentication fails (401/403)."""
    pass


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini API rate limits (HTTP 429 / resource exhausted) are encountered."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when a Gemini reasoning call exceeds the configured execution deadline."""
    pass


class GeminiInvalidResponseError(GeminiError):
    """Raised when Gemini returns unparseable or malformed non-JSON output."""
    pass


class GeminiValidationError(GeminiError):
    """Raised when Gemini output fails schema, requirement matching, or evidence ID validation."""
    pass


class GeminiProviderError(GeminiError):
    """Raised when the upstream Gemini API provider encounters an internal or network failure."""
    pass
