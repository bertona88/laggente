from __future__ import annotations

import html

import httpx

from .config import Settings


class EmailDeliveryError(RuntimeError):
    pass


class AuthEmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_magic_link(self, recipient: str, magic_link: str) -> None:
        if not self.settings.resend_api_key or not self.settings.from_email:
            if self.settings.is_production:
                raise EmailDeliveryError("Email provider is not configured")
            return
        safe_link = html.escape(magic_link, quote=True)
        payload = {
            "from": self.settings.from_email,
            "to": [recipient],
            "subject": "Il tuo accesso a LAGGENTE",
            "html": (
                "<p>Usa questo link per entrare nel tuo Studio LAGGENTE.</p>"
                f'<p><a href="{safe_link}">Entra nello Studio</a></p>'
                "<p>Il link scade tra 15 minuti e può essere usato una sola volta.</p>"
            ),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                json=payload,
            )
        if response.status_code >= 300:
            raise EmailDeliveryError(f"Email provider returned HTTP {response.status_code}")
