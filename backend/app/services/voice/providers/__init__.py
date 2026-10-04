"""Voice AI provider interfaces and implementations for Phase U8."""

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

__all__ = [
    "CartesiaTextToSpeechProvider",
    "DeepgramSpeechToTextProvider",
    "FakeSpeechToTextProvider",
    "FakeTextToSpeechProvider",
    "FakeVoiceReasoningProvider",
    "GeminiVoiceReasoningProvider",
    "SpeechToTextProvider",
    "TextToSpeechProvider",
    "VoiceReasoningProvider",
]
