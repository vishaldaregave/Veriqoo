"""Configuration for Phase 6 Gemini Evidence Reasoning Engine."""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class GeminiConfig:
    """Strongly-typed runtime configuration for Gemini evidence reasoning."""

    api_key: str | None = None
    model: str = "gemini-3.6-flash"
    temperature: float = 0.0
    timeout_seconds: float = 15.0
    max_retries: int = 2
    prompt_version: str = "phase6-v1"

    @classmethod
    def from_env(cls) -> GeminiConfig:
        """Construct configuration from environment variables and backend .env."""
        # Try loading from app settings or environment variables
        api_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
        if not api_key:
            try:
                from app.config import get_settings
                settings = get_settings()
                if settings.gemini_api_key:
                    api_key = settings.gemini_api_key.strip()
            except Exception:
                pass

        model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
        timeout_str = os.environ.get("GEMINI_TIMEOUT_SECONDS", "15.0").strip()
        retries_str = os.environ.get("GEMINI_MAX_RETRIES", "2").strip()

        try:
            timeout_seconds = float(timeout_str)
        except ValueError:
            timeout_seconds = 15.0

        try:
            max_retries = min(int(retries_str), 2)  # Bounded to maximum 2 retries
        except ValueError:
            max_retries = 2

        return cls(
            api_key=api_key,
            model=model,
            temperature=0.0,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            prompt_version="phase6-v1",
        )

    def __repr__(self) -> str:
        """Ensure API key is never exposed in logs or string representations."""
        has_key = bool(self.api_key and self.api_key.strip())
        return (
            f"GeminiConfig(model='{self.model}', temperature={self.temperature}, "
            f"timeout_seconds={self.timeout_seconds}, max_retries={self.max_retries}, "
            f"prompt_version='{self.prompt_version}', has_api_key={has_key})"
        )
