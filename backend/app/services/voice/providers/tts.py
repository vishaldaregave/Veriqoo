"""Text-to-Speech provider abstraction and Cartesia integration for Phase U8."""

from __future__ import annotations

import abc
import time
from typing import Any

import httpx

from backend.app.services.voice.errors import (
    VoiceProviderError,
    VoiceProviderNotConfiguredError,
    VoiceProviderTimeoutError,
    VoiceTTSError,
)
from backend.app.services.voice.models import TTSResult


# Default voice IDs for Cartesia multilingual models
DEFAULT_VOICE_IDS: dict[str, str] = {
    "en": "79a125e8-cd45-4c13-8a67-188112f4dd22",  # Natural English
    "hi": "bf99159f-89bc-47e2-97fa-4a6c6e7c7a52",  # Natural Hindi
    "mr": "bf99159f-89bc-47e2-97fa-4a6c6e7c7a52",  # Multilingual Indic / Marathi
}


class TextToSpeechProvider(abc.ABC):
    """Abstract interface for Text-to-Speech providers."""

    @abc.abstractmethod
    def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
    ) -> TTSResult:
        """Synthesize speech audio from text."""
        raise NotImplementedError


class CartesiaTextToSpeechProvider(TextToSpeechProvider):
    """Production Text-to-Speech provider calling Cartesia API via HTTP."""

    CARTESIA_API_URL = "https://api.cartesia.ai/tts/bytes"

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str = "sonic-multilingual",
        default_voice_id: str | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model_id = model_id
        self.default_voice_id = default_voice_id
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
    ) -> TTSResult:
        """Submit text to Cartesia TTS API with bounded retries."""
        if not self.api_key:
            raise VoiceProviderNotConfiguredError(
                "CARTESIA_API_KEY is not configured.",
                details={"provider": "cartesia"},
            )

        clean_text = (text or "").strip()
        if not clean_text:
            raise VoiceTTSError("TTS input text cannot be empty.")

        lang_code = language.lower()
        target_voice = voice_id or self.default_voice_id or DEFAULT_VOICE_IDS.get(lang_code, DEFAULT_VOICE_IDS["en"])

        payload = {
            "model_id": self.model_id,
            "transcript": clean_text,
            "voice": {
                "mode": "id",
                "id": target_voice,
            },
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": 24000,
            },
            "language": lang_code if lang_code in ("en", "hi", "mr") else "en",
        }

        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": "2024-06-10",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        max_attempts = max(1, self.max_retries + 1)

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        self.CARTESIA_API_URL,
                        headers=headers,
                        json=payload,
                    )

                if response.status_code == 200:
                    audio_bytes = response.content
                    req_id = response.headers.get("x-request-id")
                    return TTSResult(
                        audio_bytes=audio_bytes,
                        content_type="audio/wav",
                        duration_seconds=None,
                        provider_name="cartesia",
                        provider_request_id=req_id,
                    )
                elif response.status_code in (401, 403):
                    raise VoiceProviderNotConfiguredError(
                        "Cartesia authentication failed. Check CARTESIA_API_KEY.",
                        details={"status_code": response.status_code},
                    )
                else:
                    if attempt < max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                    raise VoiceProviderError(
                        f"Cartesia TTS API returned HTTP {response.status_code}: {response.text[:200]}",
                        details={"status_code": response.status_code},
                    )

            except httpx.TimeoutException as err:
                last_error = err
                if attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise VoiceProviderTimeoutError(
                    f"Cartesia TTS call timed out after {self.timeout_seconds}s.",
                    details={"timeout": self.timeout_seconds},
                ) from err
            except Exception as err:
                last_error = err
                if isinstance(err, (VoiceProviderNotConfiguredError, VoiceProviderTimeoutError, VoiceTTSError)):
                    raise err
                if attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise VoiceProviderError(f"Cartesia TTS request failed: {err}") from err

        raise VoiceProviderError(f"Cartesia TTS failed after {max_attempts} attempts: {last_error}")


class FakeTextToSpeechProvider(TextToSpeechProvider):
    """Deterministic mock TTS provider for offline testing."""

    # Minimal synthetic valid WAV header (44 bytes standard PCM)
    SYNTHETIC_WAV_BYTES = (
        b"RIFF\x2c\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x08\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
    )

    def __init__(
        self,
        mock_audio_bytes: bytes | None = None,
        exception_to_raise: Exception | None = None,
    ) -> None:
        self.mock_audio_bytes = mock_audio_bytes or self.SYNTHETIC_WAV_BYTES
        self.exception_to_raise = exception_to_raise
        self.call_history: list[dict[str, Any]] = []

    def synthesize(
        self,
        text: str,
        language: str = "en",
        voice_id: str | None = None,
    ) -> TTSResult:
        self.call_history.append({
            "text": text,
            "language": language,
            "voice_id": voice_id,
        })

        if self.exception_to_raise:
            raise self.exception_to_raise

        if not text or not text.strip():
            raise VoiceTTSError("TTS input text cannot be empty.")

        return TTSResult(
            audio_bytes=self.mock_audio_bytes,
            content_type="audio/wav",
            duration_seconds=1.8,
            provider_name="fake_tts",
            provider_request_id="fake-tts-req-67890",
        )
