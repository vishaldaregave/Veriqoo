"""Error definitions and error classification for Phase U8 — Voice AI."""

from __future__ import annotations

from typing import Any


class VoiceError(Exception):
    """Base error for all Voice AI subsystem exceptions."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VoiceAudioValidationError(VoiceError):
    """Raised when uploaded audio is invalid, empty, or unparseable."""
    pass


class VoiceAudioTooLargeError(VoiceError):
    """Raised when uploaded audio exceeds configured size limit."""
    pass


class VoiceUnsupportedAudioError(VoiceError):
    """Raised when audio content type or format is unsupported."""
    pass


class VoiceProviderNotConfiguredError(VoiceError):
    """Raised when a required voice provider (Deepgram, Cartesia, Gemini) is not configured."""
    pass


class VoiceProviderTimeoutError(VoiceError):
    """Raised when a provider API call times out."""
    pass


class VoiceProviderError(VoiceError):
    """Raised when an upstream voice provider returns an error."""
    pass


class VoiceSessionNotFoundError(VoiceError):
    """Raised when a referenced voice session ID does not exist."""
    pass


class VoiceContextNotFoundError(VoiceError):
    """Raised when a referenced inspection context does not exist or is unauthorized."""
    pass


class VoiceTranscriptionError(VoiceError):
    """Raised when STT transcription fails or produces unparseable output."""
    pass


class VoiceReasoningError(VoiceError):
    """Raised when reasoning generation fails."""
    pass


class VoiceTTSError(VoiceError):
    """Raised when text-to-speech synthesis fails."""
    pass


class VoiceInvalidLanguageError(VoiceError):
    """Raised when requested language is unsupported."""
    pass
