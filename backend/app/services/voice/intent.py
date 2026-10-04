"""Deterministic voice intent classifier for Phase U8."""

from __future__ import annotations

import re
from backend.app.services.voice.models import VoiceIntent


# Keyword and regex pattern matchers for multi-lingual natural intent detection
INTENT_PATTERNS: list[tuple[VoiceIntent, list[str]]] = [
    (
        VoiceIntent.GREETING,
        [
            r"\b(hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening)\b",
            r"(नमस्ते|नमस्कार|प्रणाम|हाय|हॅलो)",
        ],
    ),
    (
        VoiceIntent.TRANSLATE_RESULT,
        [
            r"\b(in\s+marathi|in\s+hindi|in\s+english|translate\s+to\s+marathi|translate\s+to\s+hindi)\b",
            r"(मराठीत\s+सांगा|मराठीमध्ये|हिंदी\s+में\s+बताओ|हिंदी\s+में\s+समझाओ|मराठीत\s+अनुवाद)",
        ],
    ),
    (
        VoiceIntent.EXPLAIN_SCORE,
        [
            r"\b(score|compliance\s+score|points|percentage|rating|how\s+many\s+marks)\b",
            r"(स्कोर|गुण|रेटिंग|किती\s+गुण|कितने\s+प्रतिशत|प्रतिशत)",
        ],
    ),
    (
        VoiceIntent.EXPLAIN_RISK,
        [
            r"\b(risk|is\s+it\s+safe|is\s+it\s+fake|danger|hazard|suspicious)\b",
            r"(धोका|धोकादायक|जोखिम|खतरा|सुरक्षित\s+आहे\s+का|नकली)",
        ],
    ),
    (
        VoiceIntent.CONSUMER_RIGHTS,
        [
            r"\b(consumer\s+rights?|my\s+rights?|legal\s+rights?|what\s+are\s+the\s+rules|act|regulations)\b",
            r"(ग्राहक\s+हक्क|हक्क|अधिकार|ग्राहकांचे\s+अधिकार|कायदे|नियम)",
        ],
    ),
    (
        VoiceIntent.INSPECTION_VIOLATIONS,
        [
            r"\b(all\s+violations|list\s+violations|what\s+failed|failed\s+requirements|missing\s+declarations)\b",
            r"(उल्लंघन|काय\s+चुकले|कोणते\s+नियम\s+मोडले|सर्व\s+त्रुटी|गंभीर\s+उल्लंघन)",
        ],
    ),
    (
        VoiceIntent.INSPECTION_SUMMARY,
        [
            r"\b(summary|short\s+summary|quick\s+overview|give\s+me\s+a\s+summary|read\s+summary)\b",
            r"(सारांश|थोडक्यात\s+सांगा|थोडक्यात\s+माहिती|संक्षेप\s+में)",
        ],
    ),
    (
        VoiceIntent.EXPLAIN_FINDING,
        [
            r"\b(what\s+is\s+wrong|why\s+did\s+.*\s*fail|why\s+fail|why\s+failed|what\s+is\s+the\s+problem|why\s+marked\s+problem|explain\s+finding)\b",
            r"(काय\s+अडचण\s+आहे|का\s+फेल\s+झाले|काय\s+चूक\s+आहे|क्या\s+गलती\s+है|क्यों\s+फेल\s+हुआ|क्या\s+समस्या\s+है)",
        ],
    ),

    (
        VoiceIntent.EXPLAIN_PRODUCT,
        [
            r"\b(mrp|price|manufacturer|net\s+quantity|weight|volume|batch|expiry|date|packer)\b",
            r"(किंमत|एमआरपी|वजन|उत्पादक|तारीख|पॅकर|नेट\s+क्वांटिटी)",
        ],
    ),
    (
        VoiceIntent.GENERAL_VERIQOO_HELP,
        [
            r"\b(help|how\s+to\s+use|what\s+can\s+you\s+do|who\s+are\s+you|veriqoo)\b",
            r"(मदत|कसा\s+वापरायचा|काय\s+करू\s+शकतो|सहायता|मदद)",
        ],
    ),
    (
        VoiceIntent.EXPLAIN_RESULT,
        [
            r"\b(is\s+it\s+compliant|is\s+it\s+legal|is\s+this\s+okay|explain\s+result|status)\b",
            r"(हे\s+योग्य\s+आहे\s+का|तपासणीचा\s+निकाल|परिणाम\s+सांगा|स्थिति)",
        ],
    ),
]


class VoiceIntentClassifier:
    """Deterministic natural language utterance intent classifier."""

    @classmethod
    def classify(cls, transcript: str) -> VoiceIntent:
        """Classify user utterance into a canonical VoiceIntent."""
        if not transcript or not transcript.strip():
            return VoiceIntent.UNKNOWN

        clean_text = transcript.strip().lower()

        for intent, patterns in INTENT_PATTERNS:
            for pat in patterns:
                if re.search(pat, clean_text, re.IGNORECASE):
                    return intent

        return VoiceIntent.UNKNOWN
