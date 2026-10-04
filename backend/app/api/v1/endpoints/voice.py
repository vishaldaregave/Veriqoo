"""FastAPI router for Phase U8 — Voice AI Assistant."""

from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Header,
    Request,
    UploadFile,
    status,
)


from backend.app.api.dependencies import get_app_settings, get_session_store, get_voice_service
from backend.app.api.errors import ErrorCode, create_error_response
from backend.app.api.schemas import VoiceQueryResponse, VoiceTextQueryRequest
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser
from backend.app.auth.jwt import validate_supabase_jwt
from backend.app.config import Settings
from backend.app.services.voice import VoiceAssistantService
from backend.app.services.voice.errors import (
    VoiceAudioTooLargeError,
    VoiceAudioValidationError,
    VoiceContextNotFoundError,
    VoiceError,
    VoiceProviderNotConfiguredError,
    VoiceProviderTimeoutError,
    VoiceUnsupportedAudioError,
)


router = APIRouter(prefix="/voice", tags=["Voice AI Assistant"])


def get_optional_authenticated_user(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> AuthenticatedUser | None:
    """Resolve optional user from Authorization header if present."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        try:
            return validate_supabase_jwt(token=parts[1], settings=settings)
        except Exception:
            return None
    return None


def _verify_voice_inspection_access(
    store: InMemoryInspectionStore,
    inspection_id: str | None,
    current_user: AuthenticatedUser | None,
) -> tuple[str | None, str | None]:
    """Verify inspection access policy for voice queries.


    Rules:
    - If no inspection_id: allowed anonymously.
    - If inspection_id is supplied:
      - If unauthenticated: raises 401 AUTHENTICATION_REQUIRED.
      - If inspection missing or owned by another user: raises 404 INSPECTION_NOT_FOUND (anti-enumeration).
    """
    if not inspection_id or not inspection_id.strip():
        user_id = current_user.user_id if current_user else None
        role = current_user.role if current_user else "consumer"
        return user_id, role

    clean_id = inspection_id.strip()

    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": ErrorCode.AUTHENTICATION_REQUIRED.value,
                "message": "Authentication required to query inspection results via voice.",
                "details": {"inspection_id": clean_id},
            },
        )

    try:
        session = store.get_session(clean_id)
        insp = session.inspection
        if insp.owner_id and insp.owner_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                    "message": f"Inspection with ID '{clean_id}' not found.",
                    "details": {"inspection_id": clean_id},
                },
            )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": f"Inspection with ID '{clean_id}' not found.",
                "details": {"inspection_id": clean_id},
            },
        ) from err

    return current_user.user_id, current_user.role


@router.post("/query", response_model=VoiceQueryResponse)
async def voice_query(
    audio: UploadFile = File(..., description="Audio recording of user utterance"),
    language: str | None = Form(default=None, description="Optional language hint (en, hi, mr)"),
    inspection_id: str | None = Form(default=None, description="Optional active inspection session ID"),
    voice_session_id: str | None = Form(default=None, description="Optional conversational voice session ID"),
    synthesize_speech: bool = Form(default=True, description="Whether to return synthesized audio (TTS)"),
    voice_service: VoiceAssistantService = Depends(get_voice_service),
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser | None = Depends(get_optional_authenticated_user),
) -> VoiceQueryResponse:
    """Process an audio voice query using Deepgram STT, Veriqoo Context Reasoning, and Cartesia TTS.

    Guarantees:
    - Zero permanent raw audio storage or raw audio logging.
    - Strict prompt injection isolation.
    - Owner-only inspection access returning 404 on cross-user probing.
    - Clean structured response with optional Base64 synthesized audio.
    """
    user_id, user_role = _verify_voice_inspection_access(store, inspection_id, current_user)

    try:
        audio_bytes = await audio.read()
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VOICE_INVALID_AUDIO",
                "message": f"Failed to read uploaded audio stream: {err}",
            },
        )

    content_type = audio.content_type or "audio/wav"

    try:
        response = voice_service.process_audio_query(
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=language,
            inspection_id=inspection_id,
            voice_session_id=voice_session_id,
            user_id=user_id,
            user_role=user_role or "consumer",
            synthesize_speech=synthesize_speech,
        )
        return VoiceQueryResponse(**response.to_dict())

    except VoiceAudioTooLargeError as err:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "VOICE_AUDIO_TOO_LARGE", "message": err.message, "details": err.details},
        )
    except VoiceUnsupportedAudioError as err:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": "VOICE_UNSUPPORTED_AUDIO", "message": err.message, "details": err.details},
        )
    except VoiceAudioValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VOICE_INVALID_AUDIO", "message": err.message, "details": err.details},
        )
    except VoiceProviderNotConfiguredError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "VOICE_PROVIDER_NOT_CONFIGURED", "message": err.message, "details": err.details},
        )
    except VoiceProviderTimeoutError as err:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "VOICE_PROVIDER_TIMEOUT", "message": err.message, "details": err.details},
        )
    except VoiceContextNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.INSPECTION_NOT_FOUND.value, "message": err.message, "details": err.details},
        )
    except VoiceError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "VOICE_PROVIDER_ERROR", "message": err.message, "details": err.details},
        )


@router.post("/text", response_model=VoiceQueryResponse)
def voice_text_query(
    payload: VoiceTextQueryRequest,
    voice_service: VoiceAssistantService = Depends(get_voice_service),
    store: InMemoryInspectionStore = Depends(get_session_store),
    current_user: AuthenticatedUser | None = Depends(get_optional_authenticated_user),
) -> VoiceQueryResponse:
    """Process a text-based voice assistant query (deterministic integration testing / low-latency text mode).

    Executes full Intent, Context Resolution, and Gemini Reasoning without requiring STT.
    """
    user_id, user_role = _verify_voice_inspection_access(store, payload.inspection_id, current_user)

    try:
        response = voice_service.process_text_query(
            text=payload.text,
            language=payload.language,
            inspection_id=payload.inspection_id,
            voice_session_id=payload.voice_session_id,
            user_id=user_id,
            user_role=user_role or "consumer",
            synthesize_speech=payload.synthesize_speech,
        )
        return VoiceQueryResponse(**response.to_dict())

    except VoiceAudioValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VOICE_INVALID_REQUEST", "message": err.message, "details": err.details},
        )
    except VoiceProviderNotConfiguredError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "VOICE_PROVIDER_NOT_CONFIGURED", "message": err.message, "details": err.details},
        )
    except VoiceProviderTimeoutError as err:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "VOICE_PROVIDER_TIMEOUT", "message": err.message, "details": err.details},
        )
    except VoiceContextNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.INSPECTION_NOT_FOUND.value, "message": err.message, "details": err.details},
        )
    except VoiceError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "VOICE_PROVIDER_ERROR", "message": err.message, "details": err.details},
        )
