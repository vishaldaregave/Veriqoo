"""Domain models and data contracts for Phase U8 — Voice AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any


class VoiceIntent(str, Enum):
    """Categorical classification of user voice utterance intent."""
    GREETING = "GREETING"
    EXPLAIN_RESULT = "EXPLAIN_RESULT"
    EXPLAIN_FINDING = "EXPLAIN_FINDING"
    EXPLAIN_SCORE = "EXPLAIN_SCORE"
    EXPLAIN_RISK = "EXPLAIN_RISK"
    EXPLAIN_PRODUCT = "EXPLAIN_PRODUCT"
    EXPLAIN_LEGAL_REFERENCE = "EXPLAIN_LEGAL_REFERENCE"
    CONSUMER_RIGHTS = "CONSUMER_RIGHTS"
    INSPECTION_SUMMARY = "INSPECTION_SUMMARY"
    INSPECTION_VIOLATIONS = "INSPECTION_VIOLATIONS"
    TRANSLATE_RESULT = "TRANSLATE_RESULT"
    GENERAL_VERIQOO_HELP = "GENERAL_VERIQOO_HELP"
    UNKNOWN = "UNKNOWN"


class VoiceSessionStatus(str, Enum):
    """Lifecycle status of a conversational voice interaction session."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


@dataclass
class STTResult:
    """Normalized output from a Speech-to-Text provider."""
    transcript: str
    confidence: float | None = None
    detected_language: str | None = None
    duration_seconds: float | None = None
    provider_name: str = "deepgram"
    provider_request_id: str | None = None


@dataclass
class TTSResult:
    """Normalized output from a Text-to-Speech provider."""
    audio_bytes: bytes
    content_type: str = "audio/wav"
    duration_seconds: float | None = None
    provider_name: str = "cartesia"
    provider_request_id: str | None = None


@dataclass
class VoiceReasoningContext:
    """Sanitized, authoritative Veriqoo compliance context provided to reasoning model."""
    has_inspection: bool = False
    inspection_id: str | None = None
    overall_status: str | None = None
    compliance_score: float | None = None
    rating: str | None = None
    risk_signal: str | None = None
    product_summary: dict[str, Any] = field(default_factory=dict)
    findings_summary: list[dict[str, Any]] = field(default_factory=list)
    consumer_actions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    user_role: str = "consumer"  # consumer, inspector, public
    legal_references: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format context deterministically for voice reasoning prompt."""
        if not self.has_inspection:
            return "No specific package inspection is currently selected. Provide general Veriqoo help or ask the user to select/scan a package."

        lines = [
            f"Active Inspection ID: {self.inspection_id}",
            f"Canonical Overall Status: {self.overall_status}",
        ]
        if self.compliance_score is not None:
            lines.append(f"Compliance Score: {self.compliance_score}% ({self.rating})")
        if self.risk_signal:
            lines.append(f"Consumer Risk Signal: {self.risk_signal}")

        if self.product_summary:
            p_lines = [f"{k}: {v}" for k, v in self.product_summary.items() if v]
            if p_lines:
                lines.append("Product Identity: " + ", ".join(p_lines))

        if self.findings_summary:
            lines.append("Statutory Findings:")
            for f in self.findings_summary:
                req = f.get("requirement_id", "Unknown")
                status = f.get("status", "")
                title = f.get("title", req)
                exp = f.get("explanation", "")
                lines.append(f"  - [{status}] {title} ({req}): {exp}")

        if self.consumer_actions:
            lines.append("Recommended Consumer Actions: " + ", ".join(self.consumer_actions))

        if self.limitations:
            lines.append("Evidence Limitations: " + ", ".join(self.limitations))

        return "\n".join(lines)


@dataclass
class VoiceReasoningResult:
    """Structured response from the voice reasoning provider."""
    response_text: str
    language: str
    intent: VoiceIntent
    references: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_name: str = "gemini"


@dataclass
class VoiceSession:
    """Lightweight session container managing conversational voice context."""
    voice_session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    language: str = "en"
    current_inspection_id: str | None = None
    last_intent: VoiceIntent = VoiceIntent.UNKNOWN
    history: list[dict[str, str]] = field(default_factory=list)
    status: VoiceSessionStatus = VoiceSessionStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    max_history_turns: int = 5

    def add_turn(self, user_transcript: str, assistant_response: str, intent: VoiceIntent) -> None:
        """Append a conversation turn while enforcing bounded history window."""
        self.history.append({
            "user": user_transcript,
            "assistant": assistant_response,
            "intent": intent.value,
        })
        if len(self.history) > self.max_history_turns:
            self.history = self.history[-self.max_history_turns:]
        self.last_intent = intent
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "voice_session_id": self.voice_session_id,
            "user_id": self.user_id,
            "language": self.language,
            "current_inspection_id": self.current_inspection_id,
            "last_intent": self.last_intent.value,
            "status": self.status.value,
            "history_length": len(self.history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class VoiceResponse:
    """Authoritative output of the Voice AI orchestration pipeline."""
    voice_session_id: str
    transcript: str
    language: str
    intent: str
    response_text: str
    speech_audio_base64: str | None = None
    audio_content_type: str | None = None
    canonical_status: str | None = None
    inspection_id: str | None = None
    score: float | None = None
    risk_signal: str | None = None
    references: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "voice_session_id": self.voice_session_id,
            "transcript": self.transcript,
            "language": self.language,
            "intent": self.intent,
            "response_text": self.response_text,
            "speech_audio_base64": self.speech_audio_base64,
            "audio_content_type": self.audio_content_type,
            "canonical_status": self.canonical_status,
            "inspection_id": self.inspection_id,
            "score": self.score,
            "risk_signal": self.risk_signal,
            "references": list(self.references),
            "warnings": list(self.warnings),
            "provider_metadata": dict(self.provider_metadata),
            "generated_at": self.generated_at,
        }
