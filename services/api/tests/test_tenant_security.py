from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import database
from app.models import Account, ConfigRevision, Conversation, Member, Message, Space, utcnow
from app.security import hash_password, hash_token
from app.seed import MAURO_SELLER_CONFIG


PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 24


def seed_second_tenant():
    with database.SessionLocal() as db:
        account = Account(name="Second tenant")
        db.add(account)
        db.flush()
        member = Member(
            account_id=account.id,
            email="secondo@laggente.com",
            display_name="Secondo Professionista",
            password_hash=hash_password("password-secondo-molto-sicura"),
        )
        db.add(member)
        config = deepcopy(MAURO_SELLER_CONFIG)
        config["identity"]["name"] = "Secondo Professionista"
        space = Space(
            account_id=account.id,
            slug="secondo",
            professional_name="Secondo Professionista",
        )
        db.add(space)
        db.flush()
        revision = ConfigRevision(
            account_id=account.id,
            space_id=space.id,
            revision_number=1,
            status="active",
            document=config,
            activated_by_member_id=member.id,
            activated_at=utcnow(),
        )
        db.add(revision)
        db.flush()
        space.active_revision_id = revision.id
        conversation = Conversation(
            account_id=account.id,
            space_id=space.id,
            kind="public",
            visitor_token_hash=hash_token("second-visitor-token"),
        )
        db.add(conversation)
        db.flush()
        db.add(
            Message(
                account_id=account.id,
                conversation_id=conversation.id,
                author_type="visitor",
                author_label="Visitatore",
                content="Dato privato del secondo tenant",
            )
        )
        db.commit()
        return account.id, member.id, space.id, revision.id, conversation.id


def test_cross_account_conversation_and_revision_access_is_denied(professional_client):
    client = professional_client
    _, _, _, revision_id, conversation_id = seed_second_tenant()
    assert client.get(f"/api/v1/studio/conversations/{conversation_id}").status_code == 404
    assert client.post(f"/api/v1/studio/conversations/{conversation_id}/join").status_code == 404
    assert client.delete(f"/api/v1/studio/conversations/{conversation_id}").status_code == 404
    assert (
        client.post(f"/api/v1/studio/config/revisions/{revision_id}/activate").status_code == 404
    )
    public_denied = client.get(
        f"/api/v1/public/conversations/{conversation_id}",
        headers={"X-Conversation-Token": "not-the-second-token"},
    )
    assert public_denied.status_code == 404

    graph = client.get("/api/v1/studio/relationship-graph")
    assert graph.status_code == 200
    assert conversation_id not in {
        node.get("conversation_id") for node in graph.json()["nodes"]
    }


def test_auth_email_is_globally_unique_before_tenant_context(client):
    with database.SessionLocal() as db:
        account = Account(name="Conflicting tenant")
        db.add(account)
        db.flush()
        db.add(
            Member(
                account_id=account.id,
                email="mauro@laggente.com",
                display_name="Impostore",
                password_hash=hash_password("password-impostore-molto-sicura"),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_inactive_space_blocks_old_public_tokens_but_preserves_visitor_deletion(client):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id = created["conversation"]["id"]
    headers = {"X-Conversation-Token": created["continuation_token"]}
    with database.SessionLocal() as db:
        space = db.scalar(select(Space).where(Space.slug == "mauro"))
        space.is_active = False
        before = db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
        db.commit()

    assert client.get(
        f"/api/v1/public/conversations/{conversation_id}", headers=headers
    ).status_code == 410
    denied = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Questo non deve essere salvato.", "client_message_id": "inactive"},
    )
    assert denied.status_code == 410
    with database.SessionLocal() as db:
        after = db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
    assert after == before

    deleted = client.delete(
        f"/api/v1/public/conversations/{conversation_id}", headers=headers
    )
    assert deleted.status_code == 204


def test_public_conversation_and_attachment_tokens_are_bound_to_the_tenant_host(client):
    correct_host = {"Host": "mauro.laggente.com"}
    wrong_host = {"Host": "secondo.laggente.com"}
    assert client.get("/api/v1/public/mauro", headers=correct_host).status_code == 200
    assert client.get("/api/v1/public/mauro", headers=wrong_host).status_code == 404
    assert (
        client.post("/api/v1/public/mauro/conversations", headers=wrong_host, json={}).status_code
        == 404
    )

    created = client.post(
        "/api/v1/public/mauro/conversations", headers=correct_host, json={}
    ).json()
    conversation_id = created["conversation"]["id"]
    token = created["continuation_token"]
    correct_token_headers = {**correct_host, "X-Conversation-Token": token}
    wrong_token_headers = {**wrong_host, "X-Conversation-Token": token}
    assert (
        client.get(
            f"/api/v1/public/conversations/{conversation_id}", headers=correct_token_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/public/conversations/{conversation_id}", headers=wrong_token_headers
        ).status_code
        == 404
    )

    uploaded = client.post(
        f"/api/v1/public/conversations/{conversation_id}/attachments",
        headers=correct_token_headers,
        files={"file": ("casa.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["attachment"]["id"]
    assert (
        client.get(
            f"/api/v1/attachments/{attachment_id}/content", headers=wrong_token_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/public/conversations/{conversation_id}", headers=wrong_token_headers
        ).status_code
        == 404
    )


def test_database_errors_hide_bound_parameters(settings):
    engine = database.build_engine(settings.database_url)
    try:
        assert engine.hide_parameters is True
    finally:
        engine.dispose()
