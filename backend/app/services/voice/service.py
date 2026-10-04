"""Orchestrator coordinator for Phase U8 — Voice AI."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import threading
from typing import Any
import uuid

from backend.app.localization.service import LocalizationService, SupportedLanguage, get_localization_service
from backend.app.services.voice.context import VoiceContextResolver
from backend.app.services.voice.errors import (
    VoiceAudioTooLargeError,
    VoiceAudioValidationError,
    VoiceInvalidLanguageError,
    VoiceSessionNotFoundError,
    VoiceUnsupportedAudioError,
)
from backend.app.services.voice.intent import VoiceIntentClassifier
from backend.app.services.voice.models import (
    VoiceIntent,
    VoiceReasoningContext,
    VoiceResponse,
    VoiceSession,
    VoiceSessionStatus,
)
from backend.app.services.voice.providers.reasoning import (
    FakeVoiceReasoningProvider,
    GeminiVoiceReasoningProvider,
    VoiceReasoningProvider,
)
from backend.app.services.voice.providers.stt import (
    DeepgramSpeechToTextProvider,
    FakeSpeechToTextProvider,
    SpeechToTextProvider,
)
from backend.app.services.voice.providers.tts import (
    CartesiaTextToSpeechProvider,
    FakeTextToSpeechProvider,
    TextToSpeechProvider,
)


MAX_AUDIO_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_TRANSCRIPT_CHARS = 1000

SUPPORTED_AUDIO_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp3",
    "audio/mpeg",
    "audio/ogg",
    "audio/webm",
    "audio/m4a",
    "audio/x-m4a",
    "audio/flac",
}


class VoiceAssistantService:
    """Orchestrates end-to-end Voice AI interactions across STT, Reasoning, Context, and TTS."""

    def __init__(
        self,
        stt_provider: SpeechToTextProvider | None = None,
        tts_provider: TextToSpeechProvider | None = None,
        reasoning_provider: VoiceReasoningProvider | None = None,
        context_resolver: VoiceContextResolver | None = None,
        localization: LocalizationService | None = None,
    ) -> None:
        self._stt = stt_provider or FakeSpeechToTextProvider()
        self._tts = tts_provider or FakeTextToSpeechProvider()
        self._reasoning = reasoning_provider or FakeVoiceReasoningProvider()
        self._context_resolver = context_resolver or VoiceContextResolver()
        self._localization = localization or get_localization_service()
        self._sessions: dict[str, VoiceSession] = {}
        self._lock = threading.RLock()

    def get_or_create_session(
        self,
        session_id: str | None = None,
        user_id: str | None = None,
        language: str = "en",
        inspection_id: str | None = None,
    ) -> VoiceSession:
        """Retrieve existing voice session or initialize a new one."""
        with self._lock:
            if session_id and session_id in self._sessions:
                sess = self._sessions[session_id]
                if sess.status == VoiceSessionStatus.ACTIVE:
                    if inspection_id:
                        sess.current_inspection_id = inspection_id
                    if language:
                        sess.language = language
                    return sess

            new_session = VoiceSession(
                voice_session_id=session_id or str(uuid.uuid4()),
                user_id=user_id,
                language=language or "en",
                current_inspection_id=inspection_id,
                status=VoiceSessionStatus.ACTIVE,
            )
            self._sessions[new_session.voice_session_id] = new_session
            return new_session

    def resolve_language(
        self,
        explicit_language: str | None = None,
        session_language: str | None = None,
        stt_detected_language: str | None = None,
    ) -> str:
        """Resolve authoritative language code using strict precedence."""
        for candidate in (explicit_language, session_language, stt_detected_language):
            if candidate and candidate.strip():
                clean = candidate.strip().lower()
                if clean in ("en", "english"):
                    return "en"
                elif clean in ("hi", "hindi"):
                    return "hi"
                elif clean in ("mr", "marathi"):
                    return "mr"
        return "en"

    def process_audio_query(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/wav",
        language: str | None = None,
        inspection_id: str | None = None,
        voice_session_id: str | None = None,
        user_id: str | None = None,
        user_role: str = "consumer",
        synthesize_speech: bool = True,
    ) -> VoiceResponse:
        """Execute full voice pipeline: Audio -> STT -> Intent -> Context -> Reasoning -> TTS."""
        # 1. Validate Audio Payload
        if not audio_bytes or len(audio_bytes) == 0:
            raise VoiceAudioValidationError("Audio upload cannot be empty.")

        if len(audio_bytes) > MAX_AUDIO_PAYLOAD_BYTES:
            raise VoiceAudioTooLargeError(
                f"Audio payload size ({len(audio_bytes)} bytes) exceeds maximum limit of {MAX_AUDIO_PAYLOAD_BYTES} bytes.",
                details={"size_bytes": len(audio_bytes), "max_bytes": MAX_AUDIO_PAYLOAD_BYTES},
            )

        clean_content_type = content_type.split(";")[0].strip().lower()
        if clean_content_type and clean_content_type not in SUPPORTED_AUDIO_CONTENT_TYPES:
            raise VoiceUnsupportedAudioError(
                f"Unsupported audio content type '{clean_content_type}'.",
                details={"content_type": clean_content_type, "supported": list(SUPPORTED_AUDIO_CONTENT_TYPES)},
            )

        # 2. Session initialization
        session = self.get_or_create_session(
            session_id=voice_session_id,
            user_id=user_id,
            language=language or "en",
            inspection_id=inspection_id,
        )

        # 3. Speech-to-Text
        stt_result = self._stt.transcribe(
            audio_bytes=audio_bytes,
            content_type=clean_content_type or "audio/wav",
            language_hint=language or session.language,
        )

        transcript = (stt_result.transcript or "").strip()
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            transcript = transcript[:MAX_TRANSCRIPT_CHARS]

        # 4. Language resolution
        resolved_lang = self.resolve_language(
            explicit_language=language,
            session_language=session.language,
            stt_detected_language=stt_result.detected_language,
        )
        session.language = resolved_lang

        # 5. Intent Classification
        intent = VoiceIntentClassifier.classify(transcript)

        # 6. Context Resolution
        target_inspection = inspection_id or session.current_inspection_id
        context = self._context_resolver.resolve_context(
            inspection_id=target_inspection,
            user_id=user_id,
            user_role=user_role,
            language=resolved_lang,
        )

        # 7. Voice Reasoning
        reasoning_res = self._reasoning.reason(
            transcript=transcript,
            context=context,
            language=resolved_lang,
            intent=intent,
        )

        # 8. Text-to-Speech Synthesis
        speech_base64: str | None = None
        tts_content_type: str | None = None
        tts_provider_id: str | None = None

        if synthesize_speech and reasoning_res.response_text:
            tts_res = self._tts.synthesize(
                text=reasoning_res.response_text,
                language=resolved_lang,
            )
            speech_base64 = base64.b64encode(tts_res.audio_bytes).decode("utf-8")
            tts_content_type = tts_res.content_type
            tts_provider_id = tts_res.provider_request_id

        # 9. Update Session history
        session.add_turn(
            user_transcript=transcript,
            assistant_response=reasoning_res.response_text,
            intent=intent,
        )

        return VoiceResponse(
            voice_session_id=session.voice_session_id,
            transcript=transcript,
            language=resolved_lang,
            intent=intent.value,
            response_text=reasoning_res.response_text,
            speech_audio_base64=speech_base64,
            audio_content_type=tts_content_type,
            canonical_status=context.overall_status,
            inspection_id=context.inspection_id,
            score=context.compliance_score,
            risk_signal=context.risk_signal,
            references=reasoning_res.references,
            warnings=reasoning_res.warnings,
            provider_metadata={
                "stt_provider": stt_result.provider_name,
                "stt_request_id": stt_result.provider_request_id,
                "reasoning_provider": reasoning_res.provider_name,
                "tts_provider": tts_provider_id,
            },
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def process_text_query(
        self,
        text: str,
        language: str | None = None,
        inspection_id: str | None = None,
        voice_session_id: str | None = None,
        user_id: str | None = None,
        user_role: str = "consumer",
        synthesize_speech: bool = False,
    ) -> VoiceResponse:
        """Execute text-based voice assistant path (low-latency / integration testing)."""
        clean_text = (text or "").strip()
        if not clean_text:
            raise VoiceAudioValidationError("Query text cannot be empty.")

        if len(clean_text) > MAX_TRANSCRIPT_CHARS:
            clean_text = clean_text[:MAX_TRANSCRIPT_CHARS]

        session = self.get_or_create_session(
            session_id=voice_session_id,
            user_id=user_id,
            language=language or "en",
            inspection_id=inspection_id,
        )

        resolved_lang = self.resolve_language(
            explicit_language=language,
            session_language=session.language,
        )
        session.language = resolved_lang

        intent = VoiceIntentClassifier.classify(clean_text)

        target_inspection = inspection_id or session.current_inspection_id
        context = self._context_resolver.resolve_context(
            inspection_id=target_inspection,
            user_id=user_id,
            user_role=user_role,
            language=resolved_lang,
        )

        reasoning_res = self._reasoning.reason(
            transcript=clean_text,
            context=context,
            language=resolved_lang,
            intent=intent,
        )

        speech_base64: str | None = None
        tts_content_type: str | None = None
        if synthesize_speech and reasoning_res.response_text:
            tts_res = self._tts.synthesize(
                text=reasoning_res.response_text,
                language=resolved_lang,
            )
            speech_base64 = base64.b64encode(tts_res.audio_bytes).decode("utf-8")
            tts_content_type = tts_res.content_type

        session.add_turn(
            user_transcript=clean_text,
            assistant_response=reasoning_res.response_text,
            intent=intent,
        )

        return VoiceResponse(
            voice_session_id=session.voice_session_id,
            transcript=clean_text,
            language=resolved_lang,
            intent=intent.value,
            response_text=reasoning_res.response_text,
            speech_audio_base64=speech_base64,
            audio_content_type=tts_content_type,
            canonical_status=context.overall_status,
            inspection_id=context.inspection_id,
            score=context.compliance_score,
            risk_signal=context.risk_signal,
            references=reasoning_res.references,
            warnings=reasoning_res.warnings,
            provider_metadata={
                "reasoning_provider": reasoning_res.provider_name,
            },
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
