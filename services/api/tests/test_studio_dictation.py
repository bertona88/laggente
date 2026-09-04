from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app import database
from app.main import UPLOAD_SLOT_WAIT_SECONDS
from app.models import Event, Space, utcnow
from app.routes import studio as studio_routes


WAV = b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 24


def test_studio_dictation_requires_a_professional_session(client):
    response = client.post(
        "/api/v1/studio/dictation",
        files={"file": ("dettatura.wav", WAV, "audio/wav")},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Accesso richiesto"


def test_studio_dictation_returns_editable_text_without_creating_a_message(
    professional_client, app
):
    messages_before = professional_client.get("/api/v1/studio/messages").json()["messages"]
    studio_calls_before = len(app.state.assistant_service.studio_calls)

    response = professional_client.post(
        "/api/v1/studio/dictation",
        files={"file": ("dettatura.wav", WAV, "audio/wav")},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"transcript": "Vorrei parlare di una casa ereditata."}
    assert len(app.state.audio_transcriber.seen_paths) == 1
    assert not app.state.audio_transcriber.seen_paths[0].exists()
    assert len(app.state.assistant_service.studio_calls) == studio_calls_before
    assert (
        professional_client.get("/api/v1/studio/messages").json()["messages"]
        == messages_before
    )
    with database.SessionLocal() as db:
        studio_events = list(
            db.scalars(
                select(Event).where(
                    Event.event_type.in_(
                        {"audio_transcription_started", "studio_dictation_transcribed"}
                    )
                )
            ).all()
        )
        assert {event.event_type for event in studio_events} == {
            "audio_transcription_started",
            "studio_dictation_transcribed",
        }
        event_by_type = {event.event_type: event for event in studio_events}
        assert event_by_type["audio_transcription_started"].actor_type == "professional"
        assert event_by_type["audio_transcription_started"].payload["surface"] == "studio"
        assert event_by_type["studio_dictation_transcribed"].payload["raw_audio_deleted"] is True


def test_studio_dictation_rejects_non_audio_and_invalid_audio(professional_client):
    non_audio = professional_client.post(
        "/api/v1/studio/dictation",
        files={"file": ("casa.png", PNG, "image/png")},
    )
    invalid_audio = professional_client.post(
        "/api/v1/studio/dictation",
        files={"file": ("finta.wav", b"not-a-wave", "audio/wav")},
    )

    assert non_audio.status_code == 415
    assert non_audio.json()["detail"] == "Serve un file audio per la dettatura"
    assert invalid_audio.status_code == 415
    assert invalid_audio.json()["detail"] == "Contenuto audio non valido"


def test_studio_dictation_failure_deletes_audio_and_keeps_a_content_free_event(
    professional_client, app
):
    class FailingTranscriber:
        def __init__(self):
            self.path: Path | None = None

        async def transcribe(self, path, _media_type):
            self.path = Path(path)
            raise RuntimeError("provider unavailable")

    transcriber = FailingTranscriber()
    app.state.audio_transcriber = transcriber

    response = professional_client.post(
        "/api/v1/studio/dictation",
        files={"file": ("dettatura.wav", WAV, "audio/wav")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Trascrizione non disponibile. Riprova più tardi."
    assert transcriber.path is not None
    assert not transcriber.path.exists()
    with database.SessionLocal() as db:
        failed = db.scalar(
            select(Event).where(
                Event.event_type == "audio_transcription_failed",
            )
        )
        assert failed is not None
        assert failed.conversation_id is None
        assert failed.payload == {
            "surface": "studio",
            "error_type": "RuntimeError",
        }


def test_studio_dictation_uses_the_account_wide_transcription_ceiling(
    professional_client, app, monkeypatch
):
    monkeypatch.setattr(studio_routes, "MAX_ACCOUNT_AUDIO_TRANSCRIPTIONS_PER_HOUR", 1)
    session = professional_client.get("/api/v1/auth/session").json()
    account_id = session["member"]["account_id"]
    with database.SessionLocal() as db:
        space = db.scalar(select(Space).where(Space.account_id == account_id))
        assert space is not None
        db.add(
            Event(
                account_id=account_id,
                space_id=space.id,
                actor_type="system",
                event_type="audio_transcription_started",
                created_at=utcnow() - timedelta(minutes=1),
                payload={"surface": "public"},
            )
        )
        db.commit()
    calls_before = len(app.state.audio_transcriber.seen_paths)

    response = professional_client.post(
        "/api/v1/studio/dictation",
        files={"file": ("dettatura.wav", WAV, "audio/wav")},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Limite temporaneo delle trascrizioni raggiunto. Riprova più tardi."
    )
    assert len(app.state.audio_transcriber.seen_paths) == calls_before


def test_studio_dictation_obeys_the_global_multipart_slot(
    professional_client, app, monkeypatch
):
    from app import main as app_main

    monkeypatch.setattr(app_main, "UPLOAD_SLOT_WAIT_SECONDS", 0.001)
    app.state.upload_slots = asyncio.Semaphore(0)

    response = professional_client.post(
        "/api/v1/studio/dictation",
        files={"file": ("dettatura.wav", WAV, "audio/wav")},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "0.001"
    assert float(response.headers["Retry-After"]) < UPLOAD_SLOT_WAIT_SECONDS
