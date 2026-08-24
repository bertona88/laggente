from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event as ThreadEvent

from app import database
from app.assistants import PublicReply, StudioReply
from app.config import Settings
from app.main import create_app
from app.models import Attachment, Conversation, Event, Message, utcnow
from app.routes import public as public_routes
from app.schemas import PublicAgentOutput
from fastapi.testclient import TestClient
from sqlalchemy import select


PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 24


def login(client):
    result = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert result.status_code == 200


def test_public_conversation_is_persistent_authored_and_correctable(client, app):
    host_resolved = client.get(
        "/api/v1/public/resolve", headers={"Host": "mauro.laggente.com"}
    )
    assert host_resolved.status_code == 200
    assert host_resolved.json()["slug"] == "mauro"
    created = client.post("/api/v1/public/mauro/conversations", json={})
    assert created.status_code == 200, created.text
    body = created.json()
    conversation_id = body["conversation"]["id"]
    token = body["continuation_token"]
    assert [m["author_type"] for m in body["messages"]] == ["public_assistant"]
    assert "assistente AI" in body["messages"][0]["author_label"]
    turn = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers={"X-Conversation-Token": token},
        json={
            "content": "Sto pensando di vendere una casa ereditata.",
            "client_message_id": "first-persistent-turn",
        },
    )
    assert turn.status_code == 200, turn.text
    assert [message["author_type"] for message in turn.json()["messages"]] == [
        "visitor",
        "public_assistant",
    ]
    assert app.state.assistant_service.public_calls
    active_config = app.state.assistant_service.public_calls[0]["configuration"]
    assert active_config["template"]["id"] == "seller_it_v1"

    public_space = client.get("/api/v1/public/mauro").json()["configuration"]
    assert set(public_space) == {"schema_version", "locale", "identity", "public", "capabilities"}
    assert "assistant" not in public_space
    assert "knowledge" not in public_space

    denied = client.get(
        f"/api/v1/public/conversations/{conversation_id}",
        headers={"X-Conversation-Token": "wrong-token"},
    )
    assert denied.status_code == 404
    resumed = client.get(
        f"/api/v1/public/conversations/{conversation_id}",
        headers={"X-Conversation-Token": token},
    )
    assert resumed.status_code == 200
    assert len(resumed.json()["messages"]) == 3

    login(client)
    detail = client.get(f"/api/v1/studio/conversations/{conversation_id}")
    assert detail.status_code == 200
    memories = detail.json()["memory_items"]
    assert "possibile vendita" in detail.json()["summary"]
    assert {m["kind"] for m in memories} >= {"summary", "signal"}
    original_message_count = len(detail.json()["messages"])
    memory_id = next(m["id"] for m in memories if m["kind"] == "signal")
    corrected = client.patch(
        f"/api/v1/studio/conversations/{conversation_id}/memory/{memory_id}",
        json={"content": "Mauro può essere utile se la persona desidera una valutazione."},
    )
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "corrected"
    assert "valutazione" in corrected.json()["corrected_content"]
    # Correcting derived memory never rewrites primary messages.
    after = client.get(f"/api/v1/studio/conversations/{conversation_id}").json()
    assert len(after["messages"]) == original_message_count
    inbox = client.get("/api/v1/studio/conversations").json()["items"]
    assert inbox[0]["summary"]
    assert inbox[0]["attention_reason"]
    assert inbox[0]["last_message"]


def test_professional_presence_and_automatic_reply_control_are_independent(client, app):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id, token = created["conversation"]["id"], created["continuation_token"]
    login(client)
    assert client.post(
        "/api/v1/studio/messages",
        json={"content": "", "attachment_id": "not-supported-in-studio"},
    ).status_code == 422
    assert client.post(
        f"/api/v1/studio/conversations/{conversation_id}/messages",
        json={"content": "", "attachment_id": "not-supported-for-professional"},
    ).status_code == 422
    joined = client.post(f"/api/v1/studio/conversations/{conversation_id}/join")
    assert joined.status_code == 200
    assert joined.json()["professional_present"] is True
    assert joined.json()["automatic_replies_enabled"] is True
    human = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/messages",
        json={
            "content": "Buongiorno, sono Mauro. Ho letto il messaggio.",
            "client_message_id": "professional-attempt-1",
        },
    )
    assert human.status_code == 200
    assert human.json()["automatic_replies_enabled"] is False
    assert human.json()["messages"][-1]["author_type"] == "professional"
    replayed_human = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/messages",
        json={
            "content": "Buongiorno, sono Mauro. Ho letto il messaggio.",
            "client_message_id": "professional-attempt-1",
        },
    )
    assert replayed_human.status_code == 200
    assert [item["id"] for item in replayed_human.json()["messages"]] == [
        item["id"] for item in human.json()["messages"]
    ]
    assert sum(
        item["author_type"] == "professional" for item in replayed_human.json()["messages"]
    ) == 1

    public_while_paused = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers={"X-Conversation-Token": token},
        json={"content": "Grazie Mauro."},
    )
    assert public_while_paused.status_code == 200
    assert public_while_paused.json()["automatic_reply_generated"] is False
    calls_before = len(app.state.assistant_service.public_calls)
    enabled = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/assistant-control",
        json={"automatic_replies_enabled": True},
    )
    assert enabled.json()["automatic_ai_enabled"] is True
    public_after = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers={"X-Conversation-Token": token},
        json={"content": "Possiamo continuare."},
    )
    assert public_after.json()["automatic_reply_generated"] is True
    assert len(app.state.assistant_service.public_calls) == calls_before + 1


def test_human_pause_suppresses_an_in_flight_public_assistant_reply(client, app):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id = created["conversation"]["id"]
    token = created["continuation_token"]
    original_turn = app.state.assistant_service.public_turn

    async def pause_before_model_returns(**kwargs):
        with database.SessionLocal() as other_db:
            conversation = other_db.get(Conversation, conversation_id)
            conversation.automatic_ai_enabled = False
            conversation.professional_joined = True
            other_db.commit()
        return await original_turn(**kwargs)

    app.state.assistant_service.public_turn = pause_before_model_returns
    response = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers={"X-Conversation-Token": token},
        json={"content": "Mauro è già entrato?", "client_message_id": "race-attempt-1"},
    )
    assert response.status_code == 200
    assert response.json()["automatic_reply_generated"] is False
    assert [item["author_type"] for item in response.json()["messages"]] == ["visitor"]
    with database.SessionLocal() as db:
        event = db.scalar(
            select(Event).where(
                Event.conversation_id == conversation_id,
                Event.event_type == "stale_public_assistant_reply_suppressed",
            )
        )
        assert event is not None


def test_draft_does_not_change_public_behavior_until_explicit_activation(professional_client):
    client = professional_client
    current = client.get("/api/v1/studio/space").json()
    document = current["active_revision"]["document"]
    original_welcome = document["public"]["welcome"]
    document["public"]["welcome"] = "Una nuova accoglienza ancora in bozza."
    document["identity"]["name"] = "Mauro Bianchi"
    document["identity"]["role"] = "architetto"
    draft = client.post(
        "/api/v1/studio/config/revisions",
        json={"document": document, "rationale": "Test della separazione bozza/attiva"},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    before = client.get("/api/v1/public/mauro").json()
    assert before["configuration"]["public"]["welcome"] == original_welcome
    activated = client.post(f"/api/v1/studio/config/revisions/{draft_id}/activate")
    assert activated.status_code == 200
    after = client.get("/api/v1/public/mauro").json()
    assert after["configuration"]["public"]["welcome"] == "Una nuova accoglienza ancora in bozza."
    assert after["professional_name"] == "Mauro Bianchi"
    assert after["public_role"] == "architetto"
    assert after["ai_label"] == "LAGGENTE — assistente AI di Mauro Bianchi"
    created = client.post("/api/v1/public/mauro/conversations", json={})
    assert created.status_code == 200
    welcome = created.json()["messages"][0]
    assert welcome["content"] == "Una nuova accoglienza ancora in bozza."
    assert welcome["author_label"] == "LAGGENTE — assistente AI di Mauro Bianchi"
    studio_turn = client.post(
        "/api/v1/studio/messages",
        json={"content": "Manteniamo questo ruolo.", "client_message_id": "role-author-test"},
    )
    assert studio_turn.status_code == 200
    assert studio_turn.json()["messages"][0]["author_label"] == "Mauro Rossi — architetto"


def test_text_conversation_cannot_be_disabled_by_tenant_configuration(professional_client):
    document = professional_client.get("/api/v1/studio/space").json()["active_revision"][
        "document"
    ]
    document["capabilities"]["text"] = False
    rejected = professional_client.post(
        "/api/v1/studio/config/revisions",
        json={"document": document, "rationale": "Tentativo di disattivare il testo"},
    )
    assert rejected.status_code == 422


def test_manual_configuration_revision_uses_the_same_size_ceiling_as_the_assistant_tool(
    professional_client,
):
    document = professional_client.get("/api/v1/studio/space").json()["active_revision"][
        "document"
    ]
    document["extensions"] = {"oversized_private_context": "x" * 64_000}

    rejected = professional_client.post(
        "/api/v1/studio/config/revisions",
        json={"document": document, "rationale": "Configurazione fuori limite"},
    )

    assert rejected.status_code == 413
    assert rejected.json()["detail"] == "Configurazione troppo grande"


def test_studio_chat_persists_clear_authorship(professional_client, app):
    response = professional_client.post(
        "/api/v1/studio/messages",
        json={
            "content": "Voglio essere diretto, mai aggressivo.",
            "client_message_id": "studio-attempt-1",
        },
    )
    assert response.status_code == 200, response.text
    assert [m["author_type"] for m in response.json()["messages"]] == [
        "professional",
        "studio_assistant",
    ]
    assert app.state.assistant_service.studio_calls
    replay = professional_client.post(
        "/api/v1/studio/messages",
        json={
            "content": "Voglio essere diretto, mai aggressivo.",
            "client_message_id": "studio-attempt-1",
        },
    )
    assert replay.status_code == 200
    assert [m["id"] for m in replay.json()["messages"]] == [
        m["id"] for m in response.json()["messages"]
    ]
    history = professional_client.get("/api/v1/studio/messages").json()["messages"]
    for persisted in response.json()["messages"]:
        assert sum(item["id"] == persisted["id"] for item in history) == 1
    assert len(app.state.assistant_service.studio_calls) == 1


def test_studio_retry_resumes_a_committed_message_without_a_reply(professional_client, app):
    studio = professional_client.get("/api/v1/studio/messages").json()["conversation"]
    with database.SessionLocal() as db:
        interrupted = Message(
            account_id=studio["account_id"],
            conversation_id=studio["id"],
            author_type="professional",
            author_label="Mauro Rossi — agente immobiliare",
            content="Riprendi questo turno interrotto.",
            client_message_id="studio-interrupted-attempt",
        )
        db.add(interrupted)
        db.commit()
        interrupted_id = interrupted.id

    recovered = professional_client.post(
        "/api/v1/studio/messages",
        json={
            "content": "Riprendi questo turno interrotto.",
            "client_message_id": "studio-interrupted-attempt",
        },
    )
    assert recovered.status_code == 200, recovered.text
    assert [message["author_type"] for message in recovered.json()["messages"]] == [
        "professional",
        "studio_assistant",
    ]
    assert recovered.json()["messages"][0]["id"] == interrupted_id
    with database.SessionLocal() as db:
        reply = db.scalar(select(Message).where(Message.reply_to_message_id == interrupted_id))
        assert reply is not None
    assert len(app.state.assistant_service.studio_calls) == 1


def test_concurrent_studio_retry_returns_one_durable_turn(professional_client, app):
    entered = ThreadEvent()
    release = ThreadEvent()

    class SlowStudioService:
        def __init__(self):
            self.calls = 0

        async def studio_turn(self, _db, **_kwargs):
            self.calls += 1
            entered.set()
            await asyncio.to_thread(release.wait, 5)
            return StudioReply(
                text="Un solo seguito durevole.",
                response_id="resp_studio_concurrent",
                proposed_revision_id=None,
            )

    service = SlowStudioService()
    app.state.assistant_service = service
    payload = {
        "content": "Non duplicare questo turno.",
        "client_message_id": "studio-concurrent-attempt",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(professional_client.post, "/api/v1/studio/messages", json=payload)
        assert entered.wait(timeout=5)
        assert database.engine.pool.checkedout() == 0
        second = pool.submit(professional_client.post, "/api/v1/studio/messages", json=payload)
        release.set()
        responses = [first.result(timeout=10), second.result(timeout=10)]

    assert all(response.status_code == 200 for response in responses)
    first_ids = [message["id"] for message in responses[0].json()["messages"]]
    second_ids = [message["id"] for message in responses[1].json()["messages"]]
    assert first_ids == second_ids
    assert service.calls == 1


def test_concurrent_public_retry_returns_one_durable_turn(client, app):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id = created["conversation"]["id"]
    headers = {"X-Conversation-Token": created["continuation_token"]}
    entered = ThreadEvent()
    release = ThreadEvent()

    class SlowPublicService:
        def __init__(self):
            self.calls = 0

        async def public_turn(self, **_kwargs):
            self.calls += 1
            entered.set()
            await asyncio.to_thread(release.wait, 5)
            return PublicReply(
                output=PublicAgentOutput(
                    answer="Una sola risposta durevole.",
                    summary="Turno pubblico serializzato.",
                    memory_items=[],
                ),
                response_id="resp_public_concurrent",
            )

    service = SlowPublicService()
    app.state.assistant_service = service
    payload = {
        "content": "Non duplicare questa domanda.",
        "client_message_id": "public-concurrent-attempt",
    }

    def send():
        return client.post(
            f"/api/v1/public/conversations/{conversation_id}/messages",
            headers=headers,
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send)
        assert entered.wait(timeout=5)
        assert database.engine.pool.checkedout() == 0
        second = pool.submit(send)
        release.set()
        responses = [first.result(timeout=10), second.result(timeout=10)]

    assert all(response.status_code == 200 for response in responses)
    assert [message["id"] for message in responses[0].json()["messages"]] == [
        message["id"] for message in responses[1].json()["messages"]
    ]
    assert responses[0].json()["automatic_reply_generated"] is True
    assert responses[1].json()["automatic_reply_generated"] is False
    assert service.calls == 1


def test_public_model_backed_turns_have_conservative_ip_rate_limit(client):
    created = client.post("/api/v1/public/mauro/conversations", json={}).json()
    conversation_id = created["conversation"]["id"]
    headers = {"X-Conversation-Token": created["continuation_token"]}
    with database.SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        conversation.automatic_ai_enabled = False
        db.commit()
    for index in range(12):
        response = client.post(
            f"/api/v1/public/conversations/{conversation_id}/messages",
            headers=headers,
            json={
                "content": f"Messaggio {index}",
                "client_message_id": f"rate-attempt-{index}",
            },
        )
        assert response.status_code == 200
    limited = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Uno di troppo", "client_message_id": "rate-attempt-13"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


def test_unengaged_limit_ignores_welcome_and_unbound_upload_then_honors_real_engagement(
    client, monkeypatch
):
    monkeypatch.setattr(public_routes, "MAX_UNENGAGED_CONVERSATIONS_PER_SPACE", 1)
    first = client.post("/api/v1/public/mauro/conversations", json={}).json()
    first_id = first["conversation"]["id"]
    first_headers = {"X-Conversation-Token": first["continuation_token"]}
    uploaded = client.post(
        f"/api/v1/public/conversations/{first_id}/attachments",
        headers=first_headers,
        files={"file": ("non-inviata.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["attachment"]["id"]
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        uploaded_path = Path(client.app.state.settings.upload_dir) / attachment.storage_key
        assert uploaded_path.is_file()

    # The configured AI welcome and an uploaded-but-unbound file are not visitor engagement.
    limited = client.post("/api/v1/public/mauro/conversations", json={})
    assert limited.status_code == 429
    with database.SessionLocal() as db:
        conversation = db.get(Conversation, first_id)
        conversation.created_at = (
            utcnow() - public_routes.UNENGAGED_CONVERSATION_TTL - timedelta(seconds=1)
        )
        db.commit()

    second = client.post("/api/v1/public/mauro/conversations", json={})
    assert second.status_code == 200, second.text
    with database.SessionLocal() as db:
        assert db.get(Conversation, first_id) is None
        assert db.get(Attachment, attachment_id) is None
    assert not uploaded_path.exists()

    # A durable binding counts independently of message authorship. Use the existing welcome as
    # the bound-message marker so this branch remains distinct from visitor-message engagement.
    second_body = second.json()
    second_id = second_body["conversation"]["id"]
    second_headers = {"X-Conversation-Token": second_body["continuation_token"]}
    bound_upload = client.post(
        f"/api/v1/public/conversations/{second_id}/attachments",
        headers=second_headers,
        files={"file": ("inviata.png", PNG, "image/png")},
        data={"kind": "image"},
    )
    assert bound_upload.status_code == 201
    with database.SessionLocal() as db:
        attachment = db.get(Attachment, bound_upload.json()["attachment"]["id"])
        welcome = db.scalar(
            select(Message).where(
                Message.conversation_id == second_id,
                Message.author_type == "public_assistant",
            )
        )
        attachment.message_id = welcome.id
        db.commit()

    third = client.post("/api/v1/public/mauro/conversations", json={})
    assert third.status_code == 200, third.text
    third_body = third.json()
    visitor_turn = client.post(
        f"/api/v1/public/conversations/{third_body['conversation']['id']}/messages",
        headers={"X-Conversation-Token": third_body["continuation_token"]},
        json={"content": "Vorrei iniziare a parlarne."},
    )
    assert visitor_turn.status_code == 200, visitor_turn.text
    fourth = client.post("/api/v1/public/mauro/conversations", json={})
    assert fourth.status_code == 200, fourth.text


def test_studio_inbox_pagination_has_total_next_offset_and_disjoint_pages(client):
    created_ids = []
    for _index in range(5):
        created = client.post("/api/v1/public/mauro/conversations", json={})
        assert created.status_code == 200
        created_ids.append(created.json()["conversation"]["id"])
    base = utcnow()
    with database.SessionLocal() as db:
        for index, conversation_id in enumerate(created_ids):
            conversation = db.get(Conversation, conversation_id)
            conversation.last_message_at = base + timedelta(seconds=index)
        db.commit()

    login(client)
    pages = [
        client.get("/api/v1/studio/conversations?limit=2&offset=0"),
        client.get("/api/v1/studio/conversations?limit=2&offset=2"),
        client.get("/api/v1/studio/conversations?limit=2&offset=4"),
    ]
    assert all(page.status_code == 200 for page in pages)
    bodies = [page.json() for page in pages]
    assert [body["total"] for body in bodies] == [5, 5, 5]
    assert [body["next_offset"] for body in bodies] == [2, 4, None]
    assert [len(body["items"]) for body in bodies] == [2, 2, 1]
    page_ids = [
        [item["conversation"]["id"] for item in body["items"]] for body in bodies
    ]
    assert not (set(page_ids[0]) & set(page_ids[1]))
    assert not (set(page_ids[0]) & set(page_ids[2]))
    assert not (set(page_ids[1]) & set(page_ids[2]))
    assert set().union(*map(set, page_ids)) == set(created_ids)


def test_secure_visitor_cookie_satisfies_host_prefix_rules(tmp_path):
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'cookie.db'}",
        SESSION_SECRET="c" * 48,
        AUTH_MODE="pilot_password",
        PILOT_PASSWORD="password-pilot-molto-sicura",
        COOKIE_SECURE=True,
        OPENAI_API_KEY=None,
        UPLOAD_DIR=tmp_path / "uploads",
        TRUSTED_HOSTS="testserver",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/public/mauro/conversations", json={})
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("__Host-laggente_visitor=")
        assert "Secure" in cookie
        assert "Path=/" in cookie
        assert "Domain=" not in cookie
