from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.assistants import PublicReply, StudioReply
from app.config import Settings
from app.main import create_app
from app.schemas import PublicAgentOutput, PublicMemoryProposal


class FakeAssistantService:
    public_calls: list[dict]
    studio_calls: list[dict]

    def __init__(self):
        self.public_calls = []
        self.studio_calls = []

    async def public_turn(self, **kwargs):
        self.public_calls.append(kwargs)
        trigger = next(
            (m for m in reversed(kwargs["messages"]) if m.author_type == "visitor"), None
        )
        source = [trigger.id] if trigger else []
        return PublicReply(
            output=PublicAgentOutput(
                answer="Capisco. Qual è l'aspetto più importante per te in questo momento?",
                summary="La persona sta valutando una possibile vendita e ha iniziato a raccontarsi.",
                memory_items=[
                    PublicMemoryProposal(
                        kind="signal",
                        content=(
                            f"Una conversazione diretta con {kwargs['professional_name']} "
                            "potrebbe essere utile."
                        ),
                        source_message_ids=source,
                    )
                ],
            ),
            response_id="resp_test_public",
        )

    async def studio_turn(self, db, **kwargs):
        self.studio_calls.append(kwargs)
        return StudioReply(
            text="Ho capito. Posso preparare una bozza quando mi dici di procedere.",
            response_id="resp_test_studio",
            proposed_revision_id=None,
            proposed_email_id=None,
        )


class FakeTranscriber:
    def __init__(self):
        self.seen_paths = []

    async def transcribe(self, path, media_type):
        self.seen_paths.append(Path(path))
        return "Vorrei parlare di una casa ereditata."


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'test.db'}",
        SESSION_SECRET="s" * 48,
        AUTH_MODE="pilot_password",
        PILOT_EMAIL="mauro@laggente.com",
        PILOT_PASSWORD="password-pilot-molto-sicura",
        OPENAI_API_KEY=None,
        UPLOAD_DIR=tmp_path / "uploads",
        MAX_UPLOAD_BYTES=128,
        APP_ORIGIN="https://app.laggente.com",
        TRUSTED_HOSTS="testserver,localhost,*.localhost,*.laggente.com",
        CORS_ORIGINS="http://localhost:3000,https://app.laggente.com",
    )


@pytest.fixture
def app(settings):
    application = create_app(settings)
    application.state.assistant_service = FakeAssistantService()
    application.state.audio_transcriber = FakeTranscriber()
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def professional_client(client):
    response = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def public_conversation(client):
    response = client.post("/api/v1/public/mauro/conversations", json={})
    assert response.status_code == 200, response.text
    data = response.json()
    return data["conversation"]["id"], data["continuation_token"]
