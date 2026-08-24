from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.email import AuthEmailSender, EmailDeliveryError


def _settings(**updates) -> Settings:
    values = {
        "_env_file": None,
        "APP_ENV": "test",
        "RESEND_API_KEY": "re_test_only",
        "FROM_EMAIL": "LAGGENTE <accesso@laggente.com>",
        "APP_VERSION": "0.1.0-test",
    }
    values.update(updates)
    return Settings(**values)


@pytest.mark.asyncio
async def test_resend_sends_magic_links_and_invitations_with_html_and_text_fallbacks():
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "authorization": request.headers["authorization"],
                "user_agent": request.headers["user-agent"],
                "json": json.loads(request.content),
            }
        )
        return httpx.Response(200, json={"id": f"email-{len(requests)}"})

    magic_link = 'https://app.laggente.com/login#token=abc&next="<studio>'
    invitation_link = "https://app.laggente.com/login#invite=def"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sender = AuthEmailSender(_settings(), client=client)
        await sender.send_magic_link("mauro@example.com", magic_link)
        await sender.send_professional_invitation(
            "giulia@example.com", invitation_link, "Mauro <LAGGENTE>"
        )

    assert len(requests) == 2
    assert requests[0]["authorization"] == "Bearer re_test_only"
    assert requests[0]["user_agent"] == "LAGGENTE/0.1.0-test"
    assert requests[0]["json"] == {
        "from": "LAGGENTE <accesso@laggente.com>",
        "to": ["mauro@example.com"],
        "subject": "Il tuo accesso a LAGGENTE",
        "html": (
            "<p>Usa questo link per entrare nel tuo Studio LAGGENTE.</p>"
            '<p><a href="https://app.laggente.com/login#token=abc&amp;next=&quot;'
            '&lt;studio&gt;">Entra nello Studio</a></p>'
            "<p>Il link scade tra 15 minuti e può essere usato una sola volta.</p>"
        ),
        "text": (
            "Usa questo link per entrare nel tuo Studio LAGGENTE:\n\n"
            f"{magic_link}\n\n"
            "Il link scade tra 15 minuti e può essere usato una sola volta."
        ),
    }
    invitation = requests[1]["json"]
    assert invitation["to"] == ["giulia@example.com"]
    assert invitation["subject"] == "Crea il tuo spazio su LAGGENTE"
    assert "Mauro &lt;LAGGENTE&gt;" in invitation["html"]
    assert invitation_link in invitation["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["provider", "network"])
async def test_resend_delivery_failures_are_normalized(outcome: str):
    async def handler(request: httpx.Request) -> httpx.Response:
        if outcome == "network":
            raise httpx.ConnectError("provider unavailable", request=request)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sender = AuthEmailSender(_settings(), client=client)
        with pytest.raises(EmailDeliveryError):
            await sender.send_magic_link(
                "mauro@example.com", "https://app.laggente.com/login#token=abc"
            )


@pytest.mark.asyncio
async def test_missing_resend_configuration_is_fail_closed_only_in_production():
    await AuthEmailSender(_settings(RESEND_API_KEY=None, FROM_EMAIL=None)).send_magic_link(
        "mauro@example.com", "https://app.laggente.com/login#token=abc"
    )

    production = _settings(
        APP_ENV="production",
        RESEND_API_KEY=None,
        FROM_EMAIL=None,
    )
    with pytest.raises(EmailDeliveryError, match="not configured"):
        await AuthEmailSender(production).send_magic_link(
            "mauro@example.com", "https://app.laggente.com/login#token=abc"
        )
