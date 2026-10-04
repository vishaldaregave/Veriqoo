# Phase U8 — Voice AI Architecture
Deepgram STT + Veriqoo Context/Intent + Gemini Voice Reasoning + Cartesia TTS

## 1. Overview & Purpose
Phase U8 establishes the backend voice capability for Veriqoo, enabling natural conversational voice interactions for consumers and inspectors across English, Hindi, and Marathi.

```
Audio Input (WAV/MP3/WebM/OGG)
        ↓
Deepgram STT (Speech-to-Text)
        ↓
Normalized User Transcript
        ↓
Voice Intent Classification & Language Precedence
        ↓
Veriqoo Context Resolver (Authoritative U1 / U5 / U6 Canonical Outputs)
        ↓
Gemini Voice Reasoning (Constrained Explanation Layer)
        ↓
Cartesia TTS (Text-to-Speech)
        ↓
Synthesized Speech Audio (Base64 WAV) + Structured VoiceResponse
```

---

## 2. Core Architectural Principle
> [!IMPORTANT]
> **VOICE MUST NOT BECOME A SECOND COMPLIANCE ENGINE.**
> - The Voice AI assistant is strictly an **explanation layer** over canonical Veriqoo verification results.
> - Voice explanations **do not** invent legal requirements, determine statutory applicability, or override canonical statuses (`PASS`, `FAIL`, `REVIEW_REQUIRED`, `NOT_VISIBLE`, `NOT_APPLICABLE`).
> - The reasoning prompt strictly bounds the model to verified context supplied from U1 compliance score, U5 consumer scan intelligence, and U6 consumer compliance results.

---

## 3. Provider Abstraction Architecture
All voice operations depend on abstract provider interfaces, allowing deterministic offline testing via fakes:

### 1. `SpeechToTextProvider`
- `transcribe(audio_bytes, content_type, language_hint) -> STTResult`
- **Implementations**:
  - `DeepgramSpeechToTextProvider`: Production HTTP client calling Deepgram Nova-3 API.
  - `FakeSpeechToTextProvider`: Deterministic mock provider for tests.

### 2. `TextToSpeechProvider`
- `synthesize(text, language, voice_id) -> TTSResult`
- **Implementations**:
  - `CartesiaTextToSpeechProvider`: Production HTTP client calling Cartesia Sonic-Multilingual API.
  - `FakeTextToSpeechProvider`: Deterministic mock provider generating valid PCM WAV bytes.

### 3. `VoiceReasoningProvider`
- `reason(transcript, context, language, intent) -> VoiceReasoningResult`
- **Implementations**:
  - `GeminiVoiceReasoningProvider`: Dedicated Gemini 2.5 client with prompt injection protection.
  - `FakeVoiceReasoningProvider`: Deterministic mock reasoning provider.

---

## 4. Intent & Context Model

### Intent Taxonomy
- `GREETING`: Welcome and voice assistance initiation.
- `EXPLAIN_RESULT`: General explanation of verification outcome.
- `EXPLAIN_FINDING`: Statutory defect explanations (e.g. missing MRP prefix, vague manufacturer).
- `EXPLAIN_SCORE`: U1 compliance score and rating explanation.
- `EXPLAIN_RISK`: U5 consumer risk signal explanation.
- `EXPLAIN_PRODUCT`: Commodity attributes (brand, net quantity, manufacturer, batch).
- `EXPLAIN_LEGAL_REFERENCE`: Statutory Legal Metrology (Packaged Commodities) Rules citations.
- `CONSUMER_RIGHTS`: Explanations of mandatory consumer protections.
- `INSPECTION_SUMMARY`: Quick overview of inspection findings.
- `INSPECTION_VIOLATIONS`: Detailed breakdown of all detected failures.
- `TRANSLATE_RESULT`: Switch output language to Hindi, Marathi, or English.
- `GENERAL_VERIQOO_HELP`: Guidance on how to use Veriqoo.
- `UNKNOWN`: Fallback conversational handling.

### Inspection Context Resolution
- Inspection context is retrieved via `VoiceContextResolver`.
- **Security Guard**: Cross-user inspection access triggers a safe `404 INSPECTION_NOT_FOUND` (anti-enumeration).
- Unauthenticated access to private inspection context is rejected with `401 AUTHENTICATION_REQUIRED`.

---

## 5. Multilingual Support
Voice AI natively supports the three official Veriqoo languages:
- `en` (English)
- `hi` (Hindi — हिन्दी)
- `mr` (Marathi — मराठी)

Language precedence hierarchy:
1. Explicit request/query parameter.
2. Active voice session preference.
3. STT detected language.
4. Default fallback to English (`en`).

---

## 6. Prompt Injection Defense & Audio Security
- **Transcript Isolation**: User speech transcripts are treated as untrusted user input wrapped within `<user_transcript>` tags. System instructions forbid interpreting transcript contents as developer overrides.
- **Audio Validation**: Maximum audio payload size is strictly capped at **10 MB**.
- **Audio Content Types**: Supported audio containers include `audio/wav`, `audio/mp3`, `audio/ogg`, `audio/webm`, `audio/m4a`, `audio/flac`.
- **Zero Raw Storage**: Raw user audio bytes are **never** persisted to disk or logged in server telemetry.
- **Credential Protection**: Upstream API keys are never exposed to client responses.

---

## 7. API Specification

### Endpoint 1: Audio Query
`POST /api/v1/voice/query` (Multipart Form Data)
- **Parameters**:
  - `audio`: Audio file stream (Required)
  - `language`: `en` | `hi` | `mr` (Optional)
  - `inspection_id`: Target inspection UUID (Optional)
  - `voice_session_id`: Session UUID (Optional)
  - `synthesize_speech`: Boolean (Default: `true`)
- **Response**: `VoiceQueryResponse`

### Endpoint 2: Text Mode (Integration / Low-Latency)
`POST /api/v1/voice/text` (JSON Payload)
- **Payload**: `VoiceTextQueryRequest` (`text`, `language`, `inspection_id`, `voice_session_id`, `synthesize_speech`)
- **Response**: `VoiceQueryResponse`

---

## 8. Realtime Transport & LiveKit
LiveKit is documented as the future realtime WebRTC transport layer. For Phase U8, HTTP query endpoints provide provider-abstracted audio/text processing with sub-second turnaround without adding unnecessary runtime infrastructure.
