"""Endpoint to upload a voice note: it is transcribed and saved as a pending interaction."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ... import enums as e
from ... import schemas as s
from ...config import settings
from ...services import interactions as interactions_svc
from ...services import transcription
from ...services.errors import TranscriptionError
from ...utils import normalize_mime_type
from ..auth import AuthUser, current_user
from ..deps import get_db

router = APIRouter(prefix="/voice-notes", tags=["voice-notes"])


@router.post("", response_model=s.InteractionOut, status_code=status.HTTP_201_CREATED)
def upload_voice_note(
    audio: UploadFile = File(...),
    company_id: uuid.UUID | None = Form(None),
    contact_id: uuid.UUID | None = Form(None),
    type: e.InteractionType = Form(e.InteractionType(settings.voice_notes.default_interaction_type)),
    occurred_at: datetime | None = Form(None),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(current_user),
):
    """Transcribe the audio with Groq and store the transcript as a pending interaction.

    The audio is never written to disk or to the database. If the transcription fails nothing
    is created (502), so the client can keep the recording and retry.
    """
    cfg = settings.voice_notes
    mime_type = normalize_mime_type(audio.content_type)
    if mime_type not in cfg.allowed_mime_types:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Formato de audio no admitido: {mime_type or '?'}"
        )
    max_bytes = int(cfg.max_size_mb * 1024 * 1024)
    data = audio.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"El audio supera {cfg.max_size_mb} MB"
        )
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El audio está vacío")

    try:
        text = transcription.transcribe_audio(data, mime_type)
    except TranscriptionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No se detectó voz en el audio")

    return interactions_svc.create_voice_note(
        db, transcript=text, created_by=user.email, company_id=company_id,
        contact_id=contact_id, type=type, occurred_at=occurred_at,
    )
