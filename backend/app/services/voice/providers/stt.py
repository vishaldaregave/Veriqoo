"""Speech-to-Text provider abstraction and Deepgram integration for Phase U8."""

from __future__ import annotations

import abc
import time
from typing import Any

import httpx

from backend.app.services.voice.errors import (
    VoiceAudioValidationError,
    VoiceProviderError,
    VoiceProviderNotConfiguredError,
    VoiceProviderTimeoutError,
    VoiceTranscriptionError,
)
from backend.app.services.voice.models import STTResult


class SpeechToTextProvider(abc.ABC):
    """Abstract interface for Speech-to-Text providers."""

    @abc.abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language_hint: str | None = None,
    ) -> STTResult:
        """Transcribe input audio bytes to text."""
        raise NotImplementedError


class DeepgramSpeechToTextProvider(SpeechToTextProvider):
    """Production Speech-to-Text provider calling Deepgram API via HTTP."""

    DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "nova-3",
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language_hint: str | None = None,
    ) -> STTResult:
        """Submit audio bytes to Deepgram API with bounded retries."""
        if not self.api_key:
            raise VoiceProviderNotConfiguredError(
                "DEEPGRAM_API_KEY is not configured.",
                details={"provider": "deepgram"},
            )

        if not audio_bytes or len(audio_bytes) == 0:
            raise VoiceAudioValidationError("Audio bytes payload is empty.")

        # Map language hint: en -> en, hi -> hi, mr -> mr
        lang_param = (language_hint or "en").lower()
        if lang_param not in ("en", "hi", "mr"):
            lang_param = "en"

        params = {
            "model": self.model,
            "smart_format": "true",
            "language": lang_param,
        }

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": content_type or "audio/wav",
        }

        last_error: Exception | None = None
        max_attempts = max(1, self.max_retries + 1)

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        self.DEEPGRAM_API_URL,
                        params=params,
                        headers=headers,
                        content=audio_bytes,
                    )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", {})
                    channels = results.get("channels", [])
                    if not channels:
                        raise VoiceTranscriptionError("Deepgram returned empty channel results.")

                    alternatives = channels[0].get("alternatives", [])
                    if not alternatives:
                        raise VoiceTranscriptionError("Deepgram returned no transcript alternatives.")

                    top_alt = alternatives[0]
                    transcript = top_alt.get("transcript", "").strip()
                    confidence = top_alt.get("confidence", 1.0)
                    detected_lang = top_alt.get("detected_language") or lang_param

                    req_id = data.get("metadata", {}).get("request_id")
                    duration = data.get("metadata", {}).get("duration")

                    return STTResult(
                        transcript=transcript,
                        confidence=confidence,
                        detected_language=detected_lang,
                        duration_seconds=duration,
                        provider_name="deepgram",
                        provider_request_id=req_id,
                    )

                elif response.status_code in (401, 403):
                    raise VoiceProviderNotConfiguredError(
                        "Deepgram authentication failed. Check DEEPGRAM_API_KEY.",
                        details={"status_code": response.status_code},
                    )
                else:
                    if attempt < max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                    raise VoiceProviderError(
                        f"Deepgram STT API returned HTTP {response.status_code}: {response.text[:200]}",
                        details={"status_code": response.status_code},
                    )

            except httpx.TimeoutException as err:
                last_error = err
                if attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise VoiceProviderTimeoutError(
                    f"Deepgram STT call timed out after {self.timeout_seconds}s.",
                    details={"timeout": self.timeout_seconds},
                ) from err
            except Exception as err:
                last_error = err
                if isinstance(err, (VoiceProviderNotConfiguredError, VoiceProviderTimeoutError, VoiceTranscriptionError)):
                    raise err
                if attempt < max_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise VoiceProviderError(f"Deepgram STT request failed: {err}") from err

        raise VoiceProviderError(f"Deepgram STT failed after {max_attempts} attempts: {last_error}")


class FakeSpeechToTextProvider(SpeechToTextProvider):
    """Deterministic mock STT provider for offline testing."""

    def __init__(
        self,
        default_transcript: str = "What is wrong with this product?",
        exception_to_raise: Exception | None = None,
        language: str = "en",
        confidence: float = 0.98,
    ) -> None:
        self.default_transcript = default_transcript
        self.exception_to_raise = exception_to_raise
        self.language = language
        self.confidence = confidence
        self.call_history: list[dict[str, Any]] = []

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language_hint: str | None = None,
    ) -> STTResult:
        self.call_history.append({
            "byte_length": len(audio_bytes),
            "content_type": content_type,
            "language_hint": language_hint,
        })

        if self.exception_to_raise:
            raise self.exception_to_raise

        if not audio_bytes or len(audio_bytes) == 0:
            raise VoiceAudioValidationError("Audio bytes payload is empty.")

        return STTResult(
            transcript=self.default_transcript,
            confidence=self.confidence,
            detected_language=language_hint or self.language,
            duration_seconds=2.5,
            provider_name="fake_stt",
            provider_request_id="fake-stt-req-12345",
        )
