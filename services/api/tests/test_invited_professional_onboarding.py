from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select

from app import database
from app.assistants import StudioReply
from app.models import Account, ConfigRevision, Member, Space
from app.onboarding import starter_space_configuration
from app.security import hash_password


def test_shared_provisioning_runtime_has_no_seeded_professional_assumptions():
    api_root = Path(__file__).resolve().parents[1]
    shared_runtime_files = [
        "app/assistants.py",
        "app/onboarding.py",
        "app/routes/auth.py",
        "app/routes/invitations.py",
        "app/routes/public.py",
        "app/routes/studio.py",
        "app/tenant.py",
    ]
    source = "\n".join(
        (api_root / relative_path).read_text(encoding="utf-8")
        for relative_path in shared_runtime_files
    )
    assert "mauro" not in source.lower()


def _fragment_token(link: str, key: str) -> str:
    return parse_qs(urlparse(link).fragment)[key][0]


class GiuliaOnboardingAssistant:
    def __init__(self, public_delegate):
        self.public_delegate = public_delegate
        self.studio_calls: list[dict] = []

    async def public_turn(self, **kwargs):
        return await self.public_delegate.public_turn(**kwargs)

    async def studio_turn(self, db, **kwargs):
        self.studio_calls.append(kwargs)
        document = deepcopy(starter_space_configuration())
        document["identity"] = {
            "name": "Giulia Bianchi",
            "role": "agente immobiliare",
            "agency": None,
            "territory": "Milano Porta Romana",
        }
        document["public"]["headline"] = "Porta Romana, casa per casa."
        document["public"]["welcome"] = (
            "Ciao, sono LAGGENTE, l'assistente AI di Giulia Bianchi. "
            "Raccontami cosa stai valutando a Milano."
        )
        document["knowledge"] = [
            {
                "topic": "territorio",
                "content": "Giulia lavora principalmente a Milano Porta Romana.",
            }
        ]
        latest = db.scalar(
            select(func.max(ConfigRevision.revision_number)).where(
                ConfigRevision.account_id == kwargs["account_id"],
                ConfigRevision.space_id == kwargs["space_id"],
            )
        )
        revision = ConfigRevision(
            account_id=kwargs["account_id"],
            space_id=kwargs["space_id"],
            revision_number=(latest or 0) + 1,
            status="draft",
            document=document,
            rationale="Prima configurazione ricavata dalla presentazione di Giulia.",
            proposed_by_member_id=kwargs["member_id"],
        )
        db.add(revision)
        db.commit()
        return StudioReply(
            text=(
                "Ho preparato una prima bozza per Giulia a Porta Romana. "
                "Scegli il tuo indirizzo e controllala prima di attivarla."
            ),
            response_id="resp_giulia_onboarding",
            proposed_revision_id=revision.id,
        )


def test_invite_build_publish_and_operate_a_second_tenant(client, app):
    operator_login = client.post(
        "/api/v1/auth/pilot-login",
        json={
            "email": "mauro@laggente.com",
            "password": "password-pilot-molto-sicura",
        },
    )
    assert operator_login.status_code == 200
    assert operator_login.json()["member"]["can_invite"] is True

    invited = client.post(
        "/api/v1/studio/invitations",
        json={"email": "giulia@example.com"},
    )
    assert invited.status_code == 201, invited.text
    invitation = invited.json()
    assert invitation["status"] == "sent"
    token = _fragment_token(invitation["development_magic_link"], "invite")
    premature_login = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "giulia@example.com"}
    )
    assert premature_login.status_code == 200
    assert premature_login.json()["development_magic_link"] is None

    with database.SessionLocal() as db:
        mauro = db.scalar(select(Member).where(Member.email == "mauro@laggente.com"))
        giulia = db.scalar(select(Member).where(Member.email == "giulia@example.com"))
        giulia_space = db.scalar(select(Space).where(Space.account_id == giulia.account_id))
        assert giulia.account_id != mauro.account_id
        assert giulia.can_invite is False
        assert giulia_space.is_active is False
        assert giulia_space.slug_claimed is False
        assert giulia_space.onboarding_state == "invited"
        assert giulia_space.active_revision_id is None

    client.post("/api/v1/auth/logout")
    accepted = client.post("/api/v1/auth/invitation/consume", json={"token": token})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["space"]["onboarding_state"] == "building"
    assert client.post("/api/v1/auth/invitation/consume", json={"token": token}).status_code == 401

    setup = client.get("/api/v1/studio/space")
    messages = client.get("/api/v1/studio/messages")
    assert setup.status_code == messages.status_code == 200
    assert setup.json()["active_revision"] is None
    assert "Mauro" not in messages.text

    original_assistant = app.state.assistant_service
    app.state.assistant_service = GiuliaOnboardingAssistant(original_assistant)
    proposed = client.post(
        "/api/v1/studio/messages",
        json={
            "content": (
                "Sono Giulia Bianchi, lavoro principalmente a Milano Porta Romana e voglio "
                "accogliere le persone in modo competente ma informale."
            ),
            "client_message_id": "giulia-introduction-1",
        },
    )
    assert proposed.status_code == 200, proposed.text
    draft = proposed.json()["proposed_revision"]
    assert draft["document"]["identity"]["name"] == "Giulia Bianchi"
    assert draft["document"]["identity"]["territory"] == "Milano Porta Romana"

    unpublished_activation = client.post(
        f"/api/v1/studio/config/revisions/{draft['id']}/activate"
    )
    assert unpublished_activation.status_code == 409
    assert client.get("/api/v1/studio/space/slug/giulia/availability").json() == {
        "slug": "giulia",
        "available": True,
    }
    assert client.get("/api/v1/studio/space/slug/mauro/availability").json() == {
        "slug": "mauro",
        "available": False,
    }
    reserved = client.patch("/api/v1/studio/space/slug", json={"slug": "studio"})
    assert reserved.status_code == 409
    already_used = client.patch("/api/v1/studio/space/slug", json={"slug": "mauro"})
    assert already_used.status_code == 409
    temporary_claim = client.patch(
        "/api/v1/studio/space/slug", json={"slug": "giulia-temp"}
    )
    assert temporary_claim.status_code == 200
    claimed = client.patch("/api/v1/studio/space/slug", json={"slug": "Giulia"})
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["slug"] == "giulia"
    assert claimed.json()["slug_claimed"] is True
    assert client.get("/api/v1/public/giulia").status_code == 404

    activated = client.post(
        f"/api/v1/studio/config/revisions/{draft['id']}/activate"
    )
    assert activated.status_code == 200, activated.text
    session = client.get("/api/v1/auth/session").json()
    assert session["member"]["display_name"] == "Giulia Bianchi"
    assert session["space"]["slug"] == "giulia"
    assert session["space"]["is_active"] is True
    assert session["space"]["onboarding_state"] == "published"

    public_space = client.get("/api/v1/public/giulia")
    assert public_space.status_code == 200, public_space.text
    assert public_space.json()["professional_name"] == "Giulia Bianchi"
    assert public_space.json()["ai_label"] == "LAGGENTE — assistente AI di Giulia Bianchi"
    public_conversation = client.post(
        "/api/v1/public/giulia/conversations", json={}
    ).json()
    conversation_id = public_conversation["conversation"]["id"]
    visitor_turn = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        json={
            "content": "Sto pensando di vendere un bilocale in Porta Romana.",
            "client_message_id": "giulia-visitor-1",
        },
    )
    assert visitor_turn.status_code == 200, visitor_turn.text
    inbox = client.get("/api/v1/studio/conversations")
    assert inbox.status_code == 200
    assert inbox.json()["items"][0]["conversation"]["id"] == conversation_id
    giulia_detail = client.get(f"/api/v1/studio/conversations/{conversation_id}")
    assert giulia_detail.status_code == 200
    assert "Mauro" not in giulia_detail.text
    joined = client.post(f"/api/v1/studio/conversations/{conversation_id}/join")
    assert joined.status_code == 200
    human = client.post(
        f"/api/v1/studio/conversations/{conversation_id}/messages",
        json={"content": "Ciao, sono Giulia.", "client_message_id": "giulia-human-1"},
    )
    assert human.status_code == 200
    assert any(
        message["author_label"] == "Giulia Bianchi — agente immobiliare"
        for message in human.json()["messages"]
    )

    assert client.post(
        "/api/v1/studio/invitations", json={"email": "another@example.com"}
    ).status_code == 403

    client.post("/api/v1/auth/logout")
    mauro_again = client.post(
        "/api/v1/auth/pilot-login",
        json={
            "email": "mauro@laggente.com",
            "password": "password-pilot-molto-sicura",
        },
    )
    assert mauro_again.status_code == 200
    assert client.get(
        f"/api/v1/studio/conversations/{conversation_id}"
    ).status_code == 404
    assert client.post(
        "/api/v1/studio/invitations", json={"email": "giulia@example.com"}
    ).status_code == 409

    client.post("/api/v1/auth/logout")
    return_link = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "giulia@example.com"}
    )
    assert return_link.status_code == 200
    login_token = _fragment_token(return_link.json()["development_magic_link"], "token")
    return_session = client.post(
        "/api/v1/auth/magic-link/consume", json={"token": login_token}
    )
    assert return_session.status_code == 200
    assert return_session.json()["space"]["slug"] == "giulia"

    with database.SessionLocal() as db:
        assert db.scalar(select(func.count(Account.id))) == 2


def test_pending_invitation_can_be_resent_without_creating_another_tenant(
    professional_client,
):
    first = professional_client.post(
        "/api/v1/studio/invitations", json={"email": "pending@example.com"}
    )
    second = professional_client.post(
        "/api/v1/studio/invitations", json={"email": "pending@example.com"}
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["status"] == "sent"
    assert second.json()["status"] == "resent"
    first_token = _fragment_token(first.json()["development_magic_link"], "invite")
    second_token = _fragment_token(second.json()["development_magic_link"], "invite")
    with database.SessionLocal() as db:
        assert db.scalar(
            select(func.count(Member.id)).where(Member.email == "pending@example.com")
        ) == 1
        other_account = Account(name="Altro operatore pilot")
        db.add(other_account)
        db.flush()
        db.add(
            Member(
                account_id=other_account.id,
                email="other-operator@example.com",
                display_name="Altro operatore",
                password_hash=hash_password("password-altro-operatore"),
                can_invite=True,
            )
        )
        db.commit()

    professional_client.post("/api/v1/auth/logout")
    other_login = professional_client.post(
        "/api/v1/auth/pilot-login",
        json={
            "email": "other-operator@example.com",
            "password": "password-altro-operatore",
        },
    )
    assert other_login.status_code == 200
    assert professional_client.post(
        "/api/v1/studio/invitations", json={"email": "pending@example.com"}
    ).status_code == 409
    professional_client.post("/api/v1/auth/logout")
    assert professional_client.post(
        "/api/v1/auth/invitation/consume", json={"token": first_token}
    ).status_code == 200
    assert professional_client.post(
        "/api/v1/auth/invitation/consume", json={"token": second_token}
    ).status_code == 401
