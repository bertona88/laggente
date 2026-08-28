from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.config import Settings
from app.main import create_app
from app.models import (
    Conversation,
    Member,
    Message,
    OutreachCampaign,
    OutreachRecipient,
    OutreachSuppression,
    Space,
)
from app.outreach import (
    OutreachError,
    create_outreach_campaign,
    prepare_outreach_email,
    record_outreach_permission,
)
from app.professional_email import CaptureMailTransport


@pytest.fixture
def outreach_client(settings: Settings):
    enabled = settings.model_copy(
        update={
            "agent_mail_enabled": True,
            "agent_mail_provider": "capture",
            "agent_mail_inbound_secret": "inbound-test-secret-" + "x" * 32,
            "outreach_enabled": True,
            "outreach_max_recipients": 5,
        }
    )
    application = create_app(enabled)
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/auth/pilot-login",
            json={
                "email": "mauro@laggente.com",
                "password": "password-pilot-molto-sicura",
            },
        )
        assert response.status_code == 200, response.text
        yield client, application, enabled


def _identity() -> tuple[Member, Space]:
    with database.SessionLocal() as db:
        member = db.scalar(select(Member).where(Member.email == "mauro@laggente.com"))
        space = db.scalar(select(Space).where(Space.slug == "mauro"))
        assert member and space
        db.expunge(member)
        db.expunge(space)
        return member, space


def _campaign(settings: Settings, *, email: str = "giulia@example.com") -> OutreachCampaign:
    member, space = _identity()
    with database.SessionLocal() as db:
        campaign = create_outreach_campaign(
            db,
            settings=settings,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=None,
            name="Prime agenzie di Roma",
            landing_url="https://laggente.com/",
            candidates=[
                {
                    "name": "Giulia Bianchi",
                    "email": email,
                    "source_url": "https://example.com/giulia",
                    "source_label": "Profilo dell'agenzia",
                    "personalization_note": "Lavora sul mercato residenziale romano.",
                }
            ],
        )
        db.expunge(campaign)
        return campaign


def _permission_message(member: Member, space: Space) -> str:
    with database.SessionLocal() as db:
        studio = db.scalar(
            select(Conversation).where(
                Conversation.account_id == member.account_id,
                Conversation.space_id == space.id,
                Conversation.kind == "studio",
            )
        )
        assert studio
        message = Message(
            account_id=member.account_id,
            conversation_id=studio.id,
            author_type="professional",
            author_label=member.display_name,
            content="Confermo che questa persona mi ha dato consenso esplicito.",
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message.id


def test_public_email_source_is_research_only_and_cannot_be_authorized(outreach_client):
    client, application, settings = outreach_client
    campaign = _campaign(settings, email="Giulia@Example.com")

    blocked = client.post(f"/api/v1/studio/outreach/{campaign.id}/authorize")

    assert blocked.status_code == 409
    assert "base di contatto" in blocked.json()["detail"]
    transport = application.state.professional_mail_transport
    assert isinstance(transport, CaptureMailTransport)
    assert transport.messages == []
    with database.SessionLocal() as db:
        recipient = db.scalar(
            select(OutreachRecipient).where(OutreachRecipient.campaign_id == campaign.id)
        )
        assert recipient
        assert recipient.email == "giulia@example.com"
        assert recipient.permission_basis == "not_recorded"
        assert recipient.status == "research_only"


def test_permission_requires_the_current_professional_message(outreach_client):
    _client, _application, settings = outreach_client
    campaign = _campaign(settings)
    member, space = _identity()
    with database.SessionLocal() as db, pytest.raises(
        OutreachError, match="current_professional_attestation_required"
    ):
        recipient = db.scalar(
            select(OutreachRecipient).where(OutreachRecipient.campaign_id == campaign.id)
        )
        assert recipient
        record_outreach_permission(
            db,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=None,
            recipient_id=recipient.id,
            basis="explicit_consent",
            evidence="Il professionista dice che Giulia ha dato consenso esplicito.",
        )


def test_exact_consent_qualified_bundle_is_simulated_once_and_can_unsubscribe(
    outreach_client,
):
    client, application, settings = outreach_client
    campaign = _campaign(settings)
    member, space = _identity()
    permission_message_id = _permission_message(member, space)
    with database.SessionLocal() as db:
        recipient = db.scalar(
            select(OutreachRecipient).where(OutreachRecipient.campaign_id == campaign.id)
        )
        assert recipient
        recipient_id = recipient.id
        record_outreach_permission(
            db,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=permission_message_id,
            recipient_id=recipient.id,
            basis="explicit_consent",
            evidence="Giulia ha dato consenso esplicito il 27 agosto durante una chiamata.",
        )
        prepare_outreach_email(
            db,
            settings=settings,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=None,
            recipient_id=recipient.id,
            subject="Uno spazio LAGGENTE per la tua agenzia",
            body="Ciao Giulia,\n\ncome concordato, ecco LAGGENTE: https://laggente.com/",
        )

    ready = client.get(f"/api/v1/studio/outreach/{campaign.id}")
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "ready"
    sealed = ready.json()["recipients"][0]["professional_email"]
    assert "Per non ricevere altri messaggi" in sealed["body_text"]

    sent = client.post(f"/api/v1/studio/outreach/{campaign.id}/authorize")
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "simulated"
    transport = application.state.professional_mail_transport
    assert isinstance(transport, CaptureMailTransport)
    assert len(transport.messages) == 1

    replay = client.post(f"/api/v1/studio/outreach/{campaign.id}/authorize")
    assert replay.status_code == 200
    assert len(transport.messages) == 1

    body = sealed["body_text"]
    token_match = re.search(r"/outreach/unsubscribe#token=([^\s]+)", body)
    assert token_match
    unsubscribed = client.post(
        "/api/v1/outreach/unsubscribe", json={"token": token_match.group(1)}
    )
    assert unsubscribed.status_code == 200
    assert unsubscribed.json()["accepted"] is True
    with database.SessionLocal() as db:
        recipient = db.get(OutreachRecipient, recipient_id)
        suppression = db.scalar(
            select(OutreachSuppression).where(
                OutreachSuppression.account_id == member.account_id,
                OutreachSuppression.email == "giulia@example.com",
            )
        )
        assert recipient and recipient.status == "suppressed"
        assert suppression and suppression.source == "opaque_token_link"


def test_campaign_email_cannot_bypass_exact_bundle_authorization(outreach_client):
    client, _application, settings = outreach_client
    campaign = _campaign(settings)
    member, space = _identity()
    permission_message_id = _permission_message(member, space)
    with database.SessionLocal() as db:
        recipient = db.scalar(
            select(OutreachRecipient).where(OutreachRecipient.campaign_id == campaign.id)
        )
        assert recipient
        record_outreach_permission(
            db,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=permission_message_id,
            recipient_id=recipient.id,
            basis="explicit_consent",
            evidence="Consenso scritto ricevuto e verificato dal professionista.",
        )
        prepare_outreach_email(
            db,
            settings=settings,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=None,
            recipient_id=recipient.id,
            subject="LAGGENTE",
            body="Il link concordato è https://laggente.com/",
        )
        db.refresh(recipient)
        email_id = recipient.professional_email_id

    response = client.post(f"/api/v1/studio/email/{email_id}/authorize")
    assert response.status_code == 409
    assert "pacchetto esatto" in response.json()["detail"]


def test_pilot_cap_is_enforced_before_candidate_storage(outreach_client):
    _client, _application, settings = outreach_client
    member, space = _identity()
    candidates = [
        {
            "name": f"Professionista {index}",
            "email": f"persona{index}@example.com",
            "source_url": f"https://example.com/persona-{index}",
        }
        for index in range(6)
    ]
    with database.SessionLocal() as db, pytest.raises(
        OutreachError, match="invalid_recipient_count"
    ):
        create_outreach_campaign(
            db,
            settings=settings,
            account_id=member.account_id,
            space_id=space.id,
            member_id=member.id,
            source_message_id=None,
            name="Troppi destinatari",
            landing_url="https://laggente.com/",
            candidates=candidates,
        )
