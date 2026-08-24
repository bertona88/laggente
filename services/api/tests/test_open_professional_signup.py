from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select

from app import database
from app.models import Account, Member, SignupLink, Space


def _fragment_token(link: str, key: str) -> str:
    return parse_qs(urlparse(link).fragment)[key][0]


def test_unknown_email_verifies_before_creating_a_private_tenant(client):
    requested = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "nuova@example.com"}
    )
    assert requested.status_code == 200, requested.text
    signup_link = requested.json()["development_magic_link"]
    assert urlparse(signup_link).path == "/login"
    token = _fragment_token(signup_link, "signup")

    with database.SessionLocal() as db:
        assert db.scalar(select(func.count(Account.id))) == 1
        assert db.scalar(
            select(func.count(Member.id)).where(Member.email == "nuova@example.com")
        ) == 0
        assert db.scalar(
            select(func.count(SignupLink.id)).where(SignupLink.email == "nuova@example.com")
        ) == 1

    consumed = client.post("/api/v1/auth/signup/consume", json={"token": token})
    assert consumed.status_code == 200, consumed.text
    assert consumed.json()["space"]["onboarding_state"] == "building"
    assert consumed.json()["space"]["is_active"] is False
    assert consumed.json()["space"]["slug_claimed"] is False
    assert consumed.json()["space"]["public_role"] == "professionista"
    assert client.post("/api/v1/auth/signup/consume", json={"token": token}).status_code == 401

    studio_messages = client.get("/api/v1/studio/messages")
    assert studio_messages.status_code == 200
    assert "che lavoro fai" in studio_messages.text.lower()

    with database.SessionLocal() as db:
        member = db.scalar(select(Member).where(Member.email == "nuova@example.com"))
        space = db.scalar(select(Space).where(Space.account_id == member.account_id))
        assert member.can_invite is False
        assert member.password_hash is None
        assert space.onboarding_state == "building"
        assert db.scalar(select(func.count(Account.id))) == 2

    client.post("/api/v1/auth/logout")
    returning = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "nuova@example.com"}
    )
    assert _fragment_token(returning.json()["development_magic_link"], "token")


def test_consuming_one_signup_link_invalidates_siblings_without_duplicate_tenants(client):
    first = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "doppio@example.com"}
    )
    second = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "doppio@example.com"}
    )
    first_token = _fragment_token(first.json()["development_magic_link"], "signup")
    second_token = _fragment_token(second.json()["development_magic_link"], "signup")

    assert client.post("/api/v1/auth/signup/consume", json={"token": first_token}).status_code == 200
    assert client.post("/api/v1/auth/signup/consume", json={"token": second_token}).status_code == 401
    with database.SessionLocal() as db:
        assert db.scalar(
            select(func.count(Member.id)).where(Member.email == "doppio@example.com")
        ) == 1
        assert db.scalar(select(func.count(Account.id))) == 2


def test_invited_email_can_enter_through_open_signup_without_an_inviter_resend(
    professional_client,
):
    invited = professional_client.post(
        "/api/v1/studio/invitations", json={"email": "pending-open@example.com"}
    )
    invitation_token = _fragment_token(
        invited.json()["development_magic_link"], "invite"
    )
    professional_client.post("/api/v1/auth/logout")

    requested = professional_client.post(
        "/api/v1/auth/magic-link/request", json={"email": "pending-open@example.com"}
    )
    signup_token = _fragment_token(
        requested.json()["development_magic_link"], "signup"
    )
    accepted = professional_client.post(
        "/api/v1/auth/signup/consume", json={"token": signup_token}
    )
    assert accepted.status_code == 200
    assert accepted.json()["space"]["onboarding_state"] == "building"
    assert professional_client.post(
        "/api/v1/auth/invitation/consume", json={"token": invitation_token}
    ).status_code == 401
