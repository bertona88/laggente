from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from threading import Event as ThreadEvent

import pytest
from sqlalchemy import func, select
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.formparsers import MultiPartParser

from app import database
from app import main as app_main
from app.models import Attachment, ConfigRevision, Conversation, Event, Space, utcnow
from app.retention import STALE_UNBOUND_ATTACHMENT_TTL, discard_stale_unbound_attachments
from app.routes import attachments as attachment_routes


PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 24
WAV = b"RIFF" + b"0000" + b"WAVE" + b"a" * 24


def test_private_image_upload_authorized_content_and_message_binding(client, public_conversation):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("casa.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert uploaded.status_code == 201, uploaded.text
    data = uploaded.json()
    attachment_id = data["attachment"]["id"]
    assert data["download_url"] == f"/api/v1/attachments/{attachment_id}/content"
    download = client.get(data["download_url"])
    assert download.status_code == 200
    assert download.content == PNG
    assert "attachment" not in download.headers.get("content-disposition", "").lower()
    assert client.get(data["download_url"] + "x").status_code in {404, 422}
    # TestClient still has the scoped visitor cookie, so use an explicitly wrong header (header wins).
    denied = client.get(
        data["download_url"],
        headers={"X-Conversation-Token": "wrong"},
    )
    assert denied.status_code == 404
    assert client.get(f"/api/v1/attachments/{attachment_id}/access", headers=headers).status_code == 404
    assert client.get(
        f"/api/v1/attachments/{attachment_id}/download?token=never-log-bearers"
    ).status_code == 404
    bound = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "",
            "attachment_id": attachment_id,
            "client_message_id": "photo-attempt-1",
        },
    )
    assert bound.status_code == 200, bound.text
    bound_body = bound.json()
    assert "fotografia" in bound_body["messages"][0]["content"]
    projection = bound_body["messages"][0]["attachment"]
    assert projection == {
        "id": attachment_id,
        "kind": "image",
        "name": "casa.png",
        "url": data["download_url"],
    }
    assert "storage_key" not in bound.text
    model_call = client.app.state.assistant_service.public_calls[-1]
    assert len(model_call["image_inputs"]) == 1
    image_input = model_call["image_inputs"][0]
    assert image_input.message_id == bound_body["messages"][0]["id"]
    assert image_input.media_type == "image/png"
    assert image_input.size_bytes == len(PNG)
    assert image_input.storage_key
    assert image_input.sha256

    reloaded = client.get(
        f"/api/v1/public/conversations/{conversation_id}",
        headers=headers,
    )
    reloaded_message = next(
        item for item in reloaded.json()["messages"] if item["id"] == bound_body["messages"][0]["id"]
    )
    assert reloaded_message["attachment"] == projection
    assert client.get(reloaded_message["attachment"]["url"], headers=headers).content == PNG

    login = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert login.status_code == 200
    client.cookies.delete("laggente_visitor")
    studio = client.get(f"/api/v1/studio/conversations/{conversation_id}")
    studio_message = next(
        item for item in studio.json()["messages"] if item["id"] == bound_body["messages"][0]["id"]
    )
    assert studio_message["attachment"] == projection
    assert client.get(studio_message["attachment"]["url"]).content == PNG
    replay = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "",
            "attachment_id": attachment_id,
            "client_message_id": "photo-attempt-1",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["messages"][0]["id"] == bound_body["messages"][0]["id"]
    assert replay.json()["automatic_reply_generated"] is False
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        target = Path(client.app.state.settings.upload_dir) / attachment.storage_key
        assert target.stat().st_mode & 0o777 == 0o600
        assert target.parent.stat().st_mode & 0o777 == 0o700
        assert attachment.message_id == bound_body["messages"][0]["id"]


def test_cookie_authorized_content_is_conversation_bound(client, public_conversation):
    conversation_id, token = public_conversation
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers={"X-Conversation-Token": token},
        files={"file": ("casa.png", PNG, "image/png")},
        data={"kind": "image"},
    ).json()
    attachment_id = uploaded["attachment"]["id"]
    other = client.post("/api/v1/public/mauro/conversations", json={}).json()
    denied = client.get(
        uploaded["download_url"],
        headers={"X-Conversation-Token": other["continuation_token"]},
    )
    assert denied.status_code == 404
    allowed = client.get(
        uploaded["download_url"],
        headers={"X-Conversation-Token": token},
    )
    assert allowed.status_code == 200
    assert allowed.content == PNG


def test_active_configuration_deterministically_controls_media_capabilities(
    client, public_conversation
):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    with database.SessionLocal() as db:
        space = db.scalar(select(Space).where(Space.slug == "mauro"))
        revision = db.get(ConfigRevision, space.active_revision_id)
        document = deepcopy(revision.document)
        document["capabilities"]["photographs"] = False
        revision.document = document
        db.commit()
    denied_image = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("casa.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert denied_image.status_code == 403

    with database.SessionLocal() as db:
        space = db.scalar(select(Space).where(Space.slug == "mauro"))
        revision = db.get(ConfigRevision, space.active_revision_id)
        document = deepcopy(revision.document)
        document["capabilities"]["photographs"] = True
        document["capabilities"]["voice_notes"] = False
        revision.document = document
        db.commit()
    denied_audio = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("nota.wav", WAV, "audio/wav")},
        data={"kind": "audio"},
    )
    assert denied_audio.status_code == 403


def test_audio_is_transcribed_and_raw_file_deleted(client, public_conversation):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("nota.wav", WAV, "audio/wav")},
        data={"kind": "audio"},
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["transcript"] == "Vorrei parlare di una casa ereditata."
    assert body["attachment"]["status"] == "transcribed"
    assert body["download_url"] is None
    raw_path = client.app.state.audio_transcriber.seen_paths[-1]
    assert raw_path.parent == Path("/tmp")
    assert not raw_path.exists()
    assert not raw_path.resolve().is_relative_to(
        Path(client.app.state.settings.upload_dir).resolve()
    )
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, body["attachment"]["id"])
        assert not (Path(client.app.state.settings.upload_dir) / attachment.storage_key).exists()
    sent = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "Vorrei parlare di una casa ereditata, ma senza fretta.",
            "attachment_id": body["attachment"]["id"],
        },
    )
    assert sent.status_code == 200
    visitor_message = sent.json()["messages"][0]
    assert visitor_message["content_type"] == "audio_transcript"
    assert visitor_message["attachment"] is None
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, body["attachment"]["id"])
        assert attachment.message_id == visitor_message["id"]
        assert attachment.transcript == "Vorrei parlare di una casa ereditata, ma senza fretta."


def test_mime_magic_size_and_cross_conversation_controls(client, public_conversation):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    mismatch = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("fake.png", b"not a png", "image/png")},
        data={"kind": "image"},
    )
    assert mismatch.status_code == 415
    too_large = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("large.png", b"\x89PNG\r\n\x1a\n" + b"x" * 200, "image/png")},
        data={"kind": "image"},
    )
    assert too_large.status_code == 413
    other = client.post("/api/v1/public/mauro/conversations", json={}).json()
    upload = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("casa.png", PNG, "image/png")},
        data={"kind": "image"},
    ).json()
    cross_bind = client.post(
        f"/api/v1/public/conversations/{other['conversation']['id']}/messages",
        headers={"X-Conversation-Token": other["continuation_token"]},
        json={"content": "", "attachment_id": upload["attachment"]["id"]},
    )
    assert cross_bind.status_code == 404


def test_durable_image_conversation_quota_is_enforced_atomically(
    client, public_conversation, monkeypatch
):
    monkeypatch.setattr(
        attachment_routes, "MAX_DURABLE_CONVERSATION_UPLOAD_BYTES", len(PNG)
    )
    monkeypatch.setattr(
        attachment_routes, "MAX_DURABLE_ACCOUNT_UPLOAD_BYTES", len(PNG) * 10
    )
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}

    first = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("prima.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    limited = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("seconda.png", PNG, "image/png")},
        data={"kind": "image"},
    )

    assert first.status_code == 201
    assert limited.status_code == 409
    assert limited.json()["detail"] == "Limite spazio allegati della conversazione raggiunto"
    with database.SessionLocal() as db:
        attachments = db.scalars(
            select(Attachment).where(Attachment.conversation_id == conversation_id)
        ).all()
        assert [attachment.id for attachment in attachments] == [
            first.json()["attachment"]["id"]
        ]


def test_durable_image_account_quota_spans_conversations(
    client, public_conversation, monkeypatch
):
    monkeypatch.setattr(attachment_routes, "MAX_DURABLE_ACCOUNT_UPLOAD_BYTES", len(PNG))
    monkeypatch.setattr(
        attachment_routes, "MAX_DURABLE_CONVERSATION_UPLOAD_BYTES", len(PNG) * 10
    )
    first_id, first_token = public_conversation
    second = client.post("/api/v1/public/mauro/conversations", json={}).json()

    accepted = client.post(
        f"/api/v1/public/conversations/{first_id}/attachments",
        headers={"X-Conversation-Token": first_token},
        files={"file": ("prima.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    limited = client.post(
        f"/api/v1/public/conversations/{second['conversation']['id']}/attachments",
        headers={"X-Conversation-Token": second["continuation_token"]},
        files={"file": ("seconda.png", PNG, "image/png")},
        data={"kind": "image"},
    )

    assert accepted.status_code == 201
    assert limited.status_code == 409
    assert limited.json()["detail"] == "Spazio disponibile per gli allegati esaurito"
    with database.SessionLocal() as db:
        attachments = db.scalars(select(Attachment)).all()
        assert [attachment.id for attachment in attachments] == [
            accepted.json()["attachment"]["id"]
        ]


def test_audio_transcription_hourly_account_limit_spans_conversations(
    client, public_conversation, monkeypatch
):
    monkeypatch.setattr(attachment_routes, "MAX_ACCOUNT_AUDIO_TRANSCRIPTIONS_PER_HOUR", 1)
    first_id, first_token = public_conversation
    second = client.post("/api/v1/public/mauro/conversations", json={}).json()

    accepted = client.post(
        f"/api/v1/public/conversations/{first_id}/attachments",
        headers={"X-Conversation-Token": first_token},
        files={"file": ("prima.wav", WAV, "audio/wav")},
        data={"kind": "audio"},
    )
    limited = client.post(
        f"/api/v1/public/conversations/{second['conversation']['id']}/attachments",
        headers={"X-Conversation-Token": second["continuation_token"]},
        files={"file": ("seconda.wav", WAV, "audio/wav")},
        data={"kind": "audio"},
    )

    assert accepted.status_code == 201
    assert limited.status_code == 429
    assert limited.json()["detail"] == (
        "Limite temporaneo delle trascrizioni raggiunto. Riprova più tardi."
    )
    assert len(client.app.state.audio_transcriber.seen_paths) == 1


def test_failed_audio_transcription_releases_attachment_slot_but_keeps_spend_event(
    client, public_conversation
):
    class FailingTranscriber:
        def __init__(self):
            self.seen_path: Path | None = None

        async def transcribe(self, path, _media_type):
            self.seen_path = Path(path)
            raise RuntimeError("upstream unavailable")

    transcriber = FailingTranscriber()
    client.app.state.audio_transcriber = transcriber
    conversation_id, token = public_conversation

    response = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers={"X-Conversation-Token": token},
        files={"file": ("nota.wav", WAV, "audio/wav")},
        data={"kind": "audio"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Trascrizione non disponibile. Riprova più tardi."
    assert transcriber.seen_path is not None
    assert not transcriber.seen_path.exists()
    with database.SessionLocal() as db:
        assert db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.conversation_id == conversation_id
            )
        ) == 0
        spend_events = list(
            db.scalars(
                select(Event).where(
                    Event.event_type == "audio_transcription_started",
                    Event.account_id.is_not(None),
                )
            ).all()
        )
        assert len(spend_events) == 1
        assert spend_events[0].conversation_id is None
        assert db.scalar(
            select(func.count(Event.id)).where(
                Event.conversation_id == conversation_id,
                Event.event_type == "audio_transcription_failed",
            )
        ) == 1


def test_cancelled_audio_transcription_releases_attachment_slot(client, public_conversation):
    class CancelledTranscriber:
        async def transcribe(self, _path, _media_type):
            raise asyncio.CancelledError()

    client.app.state.audio_transcriber = CancelledTranscriber()
    conversation_id, token = public_conversation

    # BaseHTTPMiddleware turns a deliberately cancelled endpoint into this transport-level error;
    # the lifecycle assertion below is the behavior under test.
    with pytest.raises(RuntimeError, match="No response returned"):
        client.post(
            f"/api/v1/public/conversations/{conversation_id}/attachments",
            headers={"X-Conversation-Token": token},
            files={"file": ("nota.wav", WAV, "audio/wav")},
            data={"kind": "audio"},
        )

    with database.SessionLocal() as db:
        assert db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.conversation_id == conversation_id
            )
        ) == 0
        spend_event = db.scalar(
            select(Event).where(Event.event_type == "audio_transcription_started")
        )
        assert spend_event is not None
        assert spend_event.conversation_id is None


def test_conversation_deleted_during_transcription_has_no_dangling_finalization_event(
    client, public_conversation
):
    transcription_started = ThreadEvent()
    allow_transcription = ThreadEvent()

    class SlowTranscriber:
        async def transcribe(self, _path, _media_type):
            transcription_started.set()
            await asyncio.to_thread(allow_transcription.wait, 5)
            return "Trascrizione arrivata dopo la cancellazione."

    client.app.state.audio_transcriber = SlowTranscriber()
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}

    def upload():
        return client.post(
            f"/api/v1/public/conversations/{conversation_id}/attachments",
            headers=headers,
            files={"file": ("nota.wav", WAV, "audio/wav")},
            data={"kind": "audio"},
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(upload)
        assert transcription_started.wait(timeout=5)
        deleted = client.delete(
            f"/api/v1/public/conversations/{conversation_id}", headers=headers
        )
        assert deleted.status_code == 204
        allow_transcription.set()
        response = pending.result(timeout=10)

    assert response.status_code == 410
    assert response.json()["detail"] == "Conversazione eliminata durante la trascrizione"
    with database.SessionLocal() as db:
        assert db.get(Conversation, conversation_id) is None
        assert db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.conversation_id == conversation_id
            )
        ) == 0
        assert db.scalar(
            select(func.count(Event.id)).where(
                Event.conversation_id == conversation_id,
                Event.event_type == "audio_transcription_failed",
            )
        ) == 0
        assert db.scalar(
            select(Event).where(
                Event.conversation_id.is_(None),
                Event.event_type == "conversation_deletion_completed",
            )
        ) is not None


def test_stale_unbound_image_in_never_engaged_conversation_is_reclaimed_on_next_upload(
    client, public_conversation, monkeypatch
):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    first = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("abbandonata.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert first.status_code == 201
    first_id = first.json()["attachment"]["id"]
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, first_id)
        first_path = Path(client.app.state.settings.upload_dir) / attachment.storage_key
        attachment.created_at = utcnow() - STALE_UNBOUND_ATTACHMENT_TTL - timedelta(seconds=1)
        db.commit()
    assert first_path.is_file()

    # Force the new upload to fail after cleanup. The abandoned file/row deletion must already be
    # committed rather than being rolled back with the rejected replacement.
    monkeypatch.setattr(attachment_routes, "MAX_DURABLE_CONVERSATION_UPLOAD_BYTES", 0)

    second = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("corrente.png", PNG, "image/png")},
        data={"kind": "image"},
    )

    assert second.status_code == 409
    with database.SessionLocal() as db:
        assert db.get(Attachment, first_id) is None
        assert db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.conversation_id == conversation_id
            )
        ) == 0
    assert not first_path.exists()


def test_retention_cleanup_reclaims_never_engaged_unbound_image(
    client, public_conversation
):
    conversation_id, token = public_conversation
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers={"X-Conversation-Token": token},
        files={"file": ("bot-abbandonata.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["attachment"]["id"]
    cleanup_now = utcnow()
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        private_path = Path(client.app.state.settings.upload_dir) / attachment.storage_key
        attachment.created_at = cleanup_now - STALE_UNBOUND_ATTACHMENT_TTL - timedelta(seconds=1)
        db.commit()

    with database.SessionLocal() as db:
        deleted = discard_stale_unbound_attachments(
            db,
            client.app.state.settings,
            now=cleanup_now,
        )

    assert deleted == 1
    assert not private_path.exists()
    with database.SessionLocal() as db:
        assert db.get(Attachment, attachment_id) is None


def test_retention_cleanup_discards_stale_unbound_audio_but_keeps_spend_event(
    client, public_conversation
):
    conversation_id, token = public_conversation
    headers = {"X-Conversation-Token": token}
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("abbandonata.wav", WAV, "audio/wav")},
        data={"kind": "audio"},
    )
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["attachment"]["id"]
    cleanup_now = utcnow()
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        attachment.created_at = cleanup_now - STALE_UNBOUND_ATTACHMENT_TTL - timedelta(seconds=1)
        db.commit()
    with database.SessionLocal() as db:
        deleted = discard_stale_unbound_attachments(
            db,
            client.app.state.settings,
            now=cleanup_now,
        )

    assert deleted == 1
    with database.SessionLocal() as db:
        assert db.get(Attachment, attachment_id) is None
        spend_event = db.scalar(
            select(Event).where(Event.event_type == "audio_transcription_started")
        )
        assert spend_event is not None
        assert spend_event.conversation_id is None


def test_saturated_global_upload_slot_rejects_before_multipart_parsing(
    client, public_conversation, monkeypatch
):
    parsed = False
    original_parse = MultiPartParser.parse

    async def observed_parse(parser):
        nonlocal parsed
        parsed = True
        return await original_parse(parser)

    monkeypatch.setattr(MultiPartParser, "parse", observed_parse)
    monkeypatch.setattr(app_main, "UPLOAD_SLOT_WAIT_SECONDS", 0.001)
    client.app.state.upload_slots = asyncio.Semaphore(0)
    conversation_id, token = public_conversation

    response = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers={"X-Conversation-Token": token},
        files={"file": ("mai-letto.png", PNG, "image/png")},
        data={"kind": "image"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "0.001"
    assert parsed is False


def test_request_body_read_does_not_retain_a_database_connection(
    client, public_conversation, monkeypatch
):
    body_read_started = ThreadEvent()
    allow_body_read = ThreadEvent()
    original_read = StarletteUploadFile.read
    blocked_once = False

    async def observed_read(upload, size=-1):
        nonlocal blocked_once
        if not blocked_once:
            blocked_once = True
            body_read_started.set()
            await asyncio.to_thread(allow_body_read.wait, 5)
        return await original_read(upload, size)

    monkeypatch.setattr(StarletteUploadFile, "read", observed_read)
    conversation_id, token = public_conversation

    def upload():
        return client.post(
            f"/api/v1/public/conversations/{conversation_id}/attachments",
            headers={"X-Conversation-Token": token},
            files={"file": ("casa.png", PNG, "image/png")},
            data={"kind": "image"},
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(upload)
        assert body_read_started.wait(timeout=5)
        assert database.engine.pool.checkedout() == 0
        allow_body_read.set()
        response = pending.result(timeout=10)

    assert response.status_code == 201, response.text


def test_slow_transcription_and_serialized_upload_wait_release_database_connections(
    client, public_conversation, monkeypatch
):
    transcription_started = ThreadEvent()
    allow_transcription = ThreadEvent()
    second_upload_waiting = ThreadEvent()

    class SlowFirstTranscriber:
        def __init__(self):
            self.calls = 0

        async def transcribe(self, _path, _media_type):
            self.calls += 1
            if self.calls == 1:
                transcription_started.set()
                await asyncio.to_thread(allow_transcription.wait, 5)
            return "Trascrizione controllata."

    class ObservedLock:
        def __init__(self):
            self.lock: asyncio.Lock | None = None
            self.attempts = 0

        async def __aenter__(self):
            if self.lock is None:
                self.lock = asyncio.Lock()
            self.attempts += 1
            if self.attempts == 2:
                second_upload_waiting.set()
            await self.lock.acquire()
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            assert self.lock is not None
            self.lock.release()

    transcriber = SlowFirstTranscriber()
    observed_lock = ObservedLock()
    client.app.state.audio_transcriber = transcriber
    monkeypatch.setattr(attachment_routes, "_upload_lock", lambda _account_id: observed_lock)
    first_id, first_token = public_conversation
    second = client.post("/api/v1/public/mauro/conversations", json={}).json()

    def upload(conversation_id, token, filename):
        return client.post(
            f"/api/v1/public/conversations/{conversation_id}/attachments",
            headers={"X-Conversation-Token": token},
            files={"file": (filename, WAV, "audio/wav")},
            data={"kind": "audio"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(upload, first_id, first_token, "prima.wav")
        assert transcription_started.wait(timeout=5)
        assert database.engine.pool.checkedout() == 0
        second_pending = pool.submit(
            upload,
            second["conversation"]["id"],
            second["continuation_token"],
            "seconda.wav",
        )
        assert second_upload_waiting.wait(timeout=5)
        assert database.engine.pool.checkedout() == 0
        allow_transcription.set()
        responses = [first.result(timeout=10), second_pending.result(timeout=10)]

    assert all(response.status_code == 201 for response in responses)
    assert transcriber.calls == 2
