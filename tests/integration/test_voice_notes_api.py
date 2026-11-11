"""Tests for the voice notes endpoint (Groq is always simulated)."""

from sqlalchemy import func, select

from crm import models as m
from crm.services import transcription
from crm.services.errors import TranscriptionError

from tests.utils.factories import make_company

AUDIO = b"\x1aE\xdf\xa3 fake webm bytes"


def upload(client, content=AUDIO, content_type="audio/webm;codecs=opus", **data):
    """POST an audio file to the voice notes endpoint."""
    return client.post("/api/voice-notes", files={"audio": ("nota.webm", content, content_type)}, data=data)


def count_interactions(session) -> int:
    """Return how many interactions the database holds."""
    return session.scalar(select(func.count()).select_from(m.Interaction))


class TestVoiceNotes:
    """Tests for POST /api/voice-notes."""

    def test_0_success_creates_pending_interaction(self, client, session, fake_transcription):
        """The transcript is stored in a pending, unassigned voice-note interaction."""
        response = upload(client)
        assert response.status_code == 201
        body = response.json()
        assert body["transcript"] == "Pide tres kilos de boletus para mañana"
        assert body["processing_status"] == "pendiente"
        assert body["source"] == "nota_de_voz"
        assert body["type"] == "Otro"
        assert body["company"] is None
        assert body["created_by"] == "laura@example.com"
        assert fake_transcription == [(AUDIO, "audio/webm")]  # parameters stripped from the MIME type

    def test_1_optional_links_are_saved(self, client, session, fake_transcription):
        """Company and type chosen by the user are kept."""
        company = make_company(session)
        response = upload(client, company_id=str(company.id), type="Llamada")
        assert response.status_code == 201
        assert response.json()["company"]["name"] == company.name
        assert response.json()["type"] == "Llamada"

    def test_2_groq_failure_returns_502_and_creates_nothing(self, client, session, monkeypatch):
        """If the transcription fails no interaction is created, so the client can retry."""
        def boom(data, mime_type):
            raise TranscriptionError("fallo")

        monkeypatch.setattr(transcription, "transcribe_audio", boom)
        assert upload(client).status_code == 502
        assert count_interactions(session) == 0

    def test_3_disallowed_mime_type(self, client, session, fake_transcription):
        """Files that are not audio are rejected with 415 before calling Groq."""
        assert upload(client, content_type="application/pdf").status_code == 415
        assert fake_transcription == []
        assert count_interactions(session) == 0

    def test_4_too_large(self, client, session, fake_transcription, monkeypatch):
        """Audio over voice_notes.max_size_mb is rejected with 413."""
        from crm.config import settings
        monkeypatch.setitem(settings.voice_notes.as_dict(), "max_size_mb", 0.001)
        assert upload(client, content=b"x" * 2000).status_code == 413
        assert fake_transcription == []

    def test_5_empty_file(self, client, fake_transcription):
        """An empty upload is rejected with 422."""
        assert upload(client, content=b"").status_code == 422

    def test_6_empty_transcript(self, client, session, monkeypatch):
        """Audio without speech does not create an empty note."""
        monkeypatch.setattr(transcription, "transcribe_audio", lambda data, mime: "")
        assert upload(client).status_code == 422
        assert count_interactions(session) == 0

    def test_7_requires_authentication(self, anonymous_client, fake_transcription):
        """Uploading without a token gets 401."""
        assert upload(anonymous_client).status_code == 401

    def test_8_unknown_company_is_404(self, client, session, fake_transcription):
        """A company id that does not exist is rejected and nothing is created."""
        import uuid
        assert upload(client, company_id=str(uuid.uuid4())).status_code == 404
        assert count_interactions(session) == 0


class TestTranscribeAudio:
    """Tests for the Groq wrapper."""

    def test_0_missing_key_raises(self, monkeypatch):
        """Without TRANSCRIPTION_GROQ_API_KEY a clear TranscriptionError is raised."""
        from crm.config import settings
        monkeypatch.setitem(settings.transcription.as_dict(), "groq_api_key", "")
        try:
            transcription.transcribe_audio(AUDIO, "audio/webm")
        except TranscriptionError as exc:
            assert "TRANSCRIPTION_GROQ_API_KEY" in str(exc)
        else:
            raise AssertionError("TranscriptionError not raised")

    def test_1_sends_audio_to_groq_whisper(self, monkeypatch):
        """The clip is sent to the configured Whisper model with a matching file name and language."""
        from crm.config import settings
        monkeypatch.setitem(settings.transcription.as_dict(), "groq_api_key", "test-key")
        sent = {}

        class FakeTranscriptions:
            def create(self, **kwargs):
                sent.update(kwargs)
                return "  hola mundo \n"

        class FakeGroq:
            def __init__(self, **kwargs):
                self.audio = type("Audio", (), {"transcriptions": FakeTranscriptions()})()

        monkeypatch.setattr(transcription, "Groq", FakeGroq)
        assert transcription.transcribe_audio(AUDIO, "audio/mp4") == "hola mundo"
        assert sent["file"] == ("audio.mp4", AUDIO)
        assert sent["model"] == settings.transcription.model
        assert sent["language"] == settings.transcription.language

    def test_2_groq_error_is_wrapped(self, monkeypatch):
        """Any SDK failure becomes a TranscriptionError."""
        from crm.config import settings
        monkeypatch.setitem(settings.transcription.as_dict(), "groq_api_key", "test-key")

        class BrokenGroq:
            def __init__(self, **kwargs):
                raise RuntimeError("boom")

        monkeypatch.setattr(transcription, "Groq", BrokenGroq)
        try:
            transcription.transcribe_audio(AUDIO, "audio/webm")
        except TranscriptionError as exc:
            assert "boom" in str(exc)
        else:
            raise AssertionError("TranscriptionError not raised")
