"""Speech-to-text with Groq (Whisper). The audio only lives in memory: it is never stored."""

import logging

from groq import Groq

from ..config import settings
from .errors import TranscriptionError

logger = logging.getLogger(__name__)


def transcribe_audio(data: bytes, mime_type: str) -> str:
    """Return the literal transcription of `data` (an audio clip of type `mime_type`).

    Raises TranscriptionError when the key is missing or Groq fails.
    """
    cfg = settings.transcription
    api_key = cfg.groq_api_key
    if not api_key:
        raise TranscriptionError("Falta la clave de Groq (TRANSCRIPTION_GROQ_API_KEY)")
    # Groq infers the audio format from the file name, so it needs the right extension
    extension = cfg.file_extensions.as_dict().get(mime_type, cfg.default_extension)
    options = {"language": cfg.language, "temperature": cfg.temperature, "response_format": "text"}
    try:
        client = Groq(api_key=api_key, timeout=cfg.timeout_seconds)
        response = client.audio.transcriptions.create(
            file=(f"audio.{extension}", data),
            model=cfg.model,
            **options,
        )
        # With response_format="text" the SDK returns the plain string
        text = (response if isinstance(response, str) else response.text or "").strip()
        logger.info("Transcribed %s bytes of %s into %s characters", len(data), mime_type, len(text))
        return text
    except Exception as exc:  # the SDK raises many kinds of errors; the caller only needs one
        logger.warning("Transcription failed: %s", exc)
        raise TranscriptionError(f"Groq no pudo transcribir el audio: {exc}") from exc
