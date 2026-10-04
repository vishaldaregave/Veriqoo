"""Localization package for LegalMetrologyAI (Phase U3)."""

from backend.app.localization.service import (
    LocalizationService,
    Persona,
    SupportedLanguage,
    get_localization_service,
)

__all__ = [
    "LocalizationService",
    "Persona",
    "SupportedLanguage",
    "get_localization_service",
]
