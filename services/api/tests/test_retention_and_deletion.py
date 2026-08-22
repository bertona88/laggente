from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from app import database
from app.models import Attachment, Conversation, Event, MemoryItem, Message, utcnow
from app.retention import delete_conversation_data, purge_all_expired_conversations


PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 24


def _login(client):
    response = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert response.status_code == 200


def test_privacy_notice_receipt_is_versioned_and_not_marketing_consent(client):
    client.app.state.settings.privacy_notice_version = "2026-09-01"
    public_space = client.get("/api/v1/public/mauro")
    assert public_space.json()["privacy_notice_version"] == "2026-09-01"
    created = client.post(
        "/api/v1/public/mauro/conversations",
        json={
            "privacy_notice_version": public_space.json()["privacy_notice_version"],
            "privacy_notice_acknowledged": True,
        },
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation"]["id"]
    with database.SessionLocal() as db:
        event = db.scalar(
            select(Event).where(
                Event.conversation_id == conversation_id,
                Event.event_type == "privacy_notice_acknowledged",
            )
        )
        assert event.payload["notice_version"] == "2026-09-01"
        assert event.payload["acknowledgement_recorded"] is True
        assert event.payload["event_scope"] == "privacy_notice_receipt_only_not_marketing_consent"


def test_visitor_deletion_removes_files_primary_and_derived_records(client):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id = created["conversation"]["id"]
    headers = {"X-Conversation-Token": created["continuation_token"]}
    first_turn = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "Vorrei parlare della vendita della mia casa.",
            "client_message_id": "deletion-first-turn",
        },
    )
    assert first_turn.status_code == 200, first_turn.text
    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=headers,
        files={"file": ("casa.png", PNG, "image/png")},
        data={"kind": "image"},
    ).json()
    attachment_id = uploaded["attachment"]["id"]
    sent = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "Questa è la facciata.",
            "attachment_id": attachment_id,
            "client_message_id": "deletion-photo-attempt",
        },
    )
    assert sent.status_code == 200
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        private_file = Path(client.app.state.settings.upload_dir) / attachment.storage_key
        account_id = attachment.account_id
        assert private_file.exists()

    deleted = client.delete(
        f"/api/v1/public/conversations/{conversation_id}",
        headers=headers,
    )
    assert deleted.status_code == 204
    assert not private_file.exists()
    assert client.get(
        f"/api/v1/public/conversations/{conversation_id}", headers=headers
    ).status_code == 404
    with database.SessionLocal() as db:
        assert db.get(Conversation, conversation_id) is None
        assert db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        ) == 0
        assert db.scalar(
            select(func.count(MemoryItem.id)).where(MemoryItem.conversation_id == conversation_id)
        ) == 0
        assert db.scalar(
            select(func.count(Attachment.id)).where(Attachment.conversation_id == conversation_id)
        ) == 0
        assert db.scalar(
            select(func.count(Event.id)).where(Event.conversation_id == conversation_id)
        ) == 0
        outcome = db.scalar(
            select(Event).where(
                Event.account_id == account_id,
                Event.event_type == "conversation_deletion_completed",
            )
        )
        assert outcome.conversation_id is None
        assert outcome.payload["trigger"] == "visitor_request"
        assert outcome.payload["conversation_ref"] != conversation_id
        assert "facciata" not in json.dumps(outcome.payload).lower()


def test_deletion_authorization_and_explicit_retention_purge(client):
    protected = client.post("/api/v1/public/mauro/conversations", json={}).json()
    other = client.post("/api/v1/public/mauro/conversations", json={}).json()
    denied = client.delete(
        f"/api/v1/public/conversations/{protected['conversation']['id']}",
        headers={"X-Conversation-Token": other["continuation_token"]},
    )
    assert denied.status_code == 404

    with database.SessionLocal() as db:
        old = db.get(Conversation, protected["conversation"]["id"])
        old.last_message_at = utcnow() - timedelta(
            days=client.app.state.settings.conversation_retention_days + 1
        )
        db.commit()
    _login(client)
    purged = client.post("/api/v1/studio/retention/purge")
    assert purged.status_code == 200
    assert purged.json()["deleted"] == 1
    assert purged.json()["retention_days"] == 365
    with database.SessionLocal() as db:
        assert db.get(Conversation, protected["conversation"]["id"]) is None
        assert db.get(Conversation, other["conversation"]["id"]) is not None


def test_automatic_retention_cycle_applies_policy_without_an_authenticated_request(client):
    expired = client.post("/api/v1/public/mauro/conversations", json={}).json()
    current = client.post("/api/v1/public/mauro/conversations", json={}).json()
    with database.SessionLocal() as db:
        old = db.get(Conversation, expired["conversation"]["id"])
        old.last_message_at = utcnow() - timedelta(
            days=client.app.state.settings.conversation_retention_days + 1
        )
        db.commit()

    with database.SessionLocal() as db:
        deleted = purge_all_expired_conversations(db, client.app.state.settings)

    assert len(deleted) == 1
    with database.SessionLocal() as db:
        assert db.get(Conversation, expired["conversation"]["id"]) is None
        assert db.get(Conversation, current["conversation"]["id"]) is not None
        outcome = db.scalar(
            select(Event).where(
                Event.event_type == "conversation_deletion_completed",
                Event.payload["trigger"].as_string() == "retention_policy",
            )
        )
        assert outcome is not None


def test_retention_rechecks_cutoff_after_lock_before_deleting(client):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id = created["conversation"]["id"]
    cutoff = utcnow() - timedelta(days=client.app.state.settings.conversation_retention_days)
    with database.SessionLocal() as db:
        candidate = db.get(Conversation, conversation_id)
        candidate.last_message_at = cutoff - timedelta(seconds=1)
        db.commit()

    # Simulate a visitor turn committed after candidate discovery but before retention acquires the
    # row lock. The locked re-read must preserve the newly active conversation.
    with database.SessionLocal() as db:
        candidate = db.get(Conversation, conversation_id)
        db.expunge(candidate)
    with database.SessionLocal() as db:
        refreshed = db.get(Conversation, conversation_id)
        refreshed.last_message_at = cutoff + timedelta(seconds=1)
        db.commit()
    with database.SessionLocal() as db:
        result = delete_conversation_data(
            db,
            client.app.state.settings,
            conversation=candidate,
            actor_type="system",
            actor_id=None,
            trigger="retention_policy",
            only_if_last_message_before=cutoff,
        )

    assert result is None
    with database.SessionLocal() as db:
        assert db.get(Conversation, conversation_id) is not None
