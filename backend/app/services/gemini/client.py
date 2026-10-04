"""Gemini client interface and implementations with bounded execution and error classification."""

from __future__ import annotations

import abc
import time
from typing import Any

from backend.app.services.gemini.config import GeminiConfig
from backend.app.services.gemini.errors import (
    GeminiAuthenticationError,
    GeminiConfigError,
    GeminiError,
    GeminiProviderError,
    GeminiRateLimitError,
    GeminiTimeoutError,
)


class BaseGeminiClient(abc.ABC):
    """Abstract interface for Gemini reasoning interaction."""

    @abc.abstractmethod
    def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
        """Submit prompt and return raw text response from Gemini model."""
        raise NotImplementedError


class RealGeminiClient(BaseGeminiClient):
    """Production Gemini client using google.genai with bounded retries and timeouts."""

    def __init__(self, config: GeminiConfig | None = None) -> None:
        self.config = config or GeminiConfig.from_env()
        if not self.config.api_key:
            raise GeminiConfigError("GEMINI_API_KEY is not configured or is empty.")

        try:
            from google import genai
            self._client = genai.Client(api_key=self.config.api_key)
        except Exception as err:
            raise GeminiConfigError(f"Failed to initialize google.genai Client: {err}") from err

    def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
        """Call Gemini API with bounded retries and strict error classification."""
        from google.genai import types

        max_attempts = max(1, self.config.max_retries + 1)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                config_kwargs: dict[str, Any] = {
                    "temperature": self.config.temperature,
                }
                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction

                # Set response_mime_type to application/json for structured JSON responses
                config_kwargs["response_mime_type"] = "application/json"

                gen_config = types.GenerateContentConfig(**config_kwargs)

                response = self._client.models.generate_content(
                    model=self.config.model,
                    contents=prompt,
                    config=gen_config,
                )

                if not response or not response.text:
                    raise GeminiProviderError("Empty or null response received from Gemini model.")

                return response.text

            except Exception as err:
                last_error = err
                err_str = str(err).lower()

                # Classification of error
                if "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "api_key_invalid" in err_str:
                    raise GeminiAuthenticationError("Gemini API authentication failed. Verify GEMINI_API_KEY.") from err

                if "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
                    if attempt < max_attempts:
                        time.sleep(1.0 * attempt)
                        continue
                    raise GeminiRateLimitError("Gemini API rate limit exceeded or quota exhausted.") from err

                if "deadline" in err_str or "timeout" in err_str or "timed out" in err_str:
                    if attempt < max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                    raise GeminiTimeoutError(f"Gemini API call timed out after {self.config.timeout_seconds}s.") from err

                # For general transient provider errors
                if attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue

                raise GeminiProviderError(f"Gemini API call failed: {type(err).__name__}") from err

        if isinstance(last_error, GeminiError):
            raise last_error
        raise GeminiProviderError(f"Gemini execution failed after {max_attempts} attempts: {last_error}")


class FakeGeminiClient(BaseGeminiClient):
    """Configurable mock Gemini client for deterministic, offline testing."""

    def __init__(
        self,
        default_response: str | None = None,
        exception_to_raise: Exception | None = None,
        responses_queue: list[str] | None = None,
        response_handler: Any | None = None,
    ) -> None:
        self.default_response = default_response or "{}"
        self.exception_to_raise = exception_to_raise
        self.responses_queue = list(responses_queue or [])
        self.response_handler = response_handler
        self.call_history: list[dict[str, Any]] = []

    def generate_content(self, prompt: str, system_instruction: str | None = None) -> str:
        self.call_history.append({
            "prompt": prompt,
            "system_instruction": system_instruction,
            "timestamp": time.time(),
        })

        if self.exception_to_raise:
            raise self.exception_to_raise

        if self.response_handler:
            return self.response_handler(prompt)

        if self.responses_queue:
            return self.responses_queue.pop(0)

        return self.default_response
