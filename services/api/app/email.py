from __future__ import annotations

import html

import httpx

from .config import Settings


class EmailDeliveryError(RuntimeError):
    pass


class AuthEmailSender:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def _send(
        self, recipient: str, subject: str, body_html: str, body_text: str
    ) -> None:
        if not self.settings.resend_api_key or not self.settings.from_email:
            if self.settings.is_production:
                raise EmailDeliveryError("Email provider is not configured")
            return
        payload = {
            "from": self.settings.from_email,
            "to": [recipient],
            "subject": subject,
            "html": body_html,
            "text": body_text,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.resend_api_key}",
            "User-Agent": f"LAGGENTE/{self.settings.version}",
        }
        try:
            if self.client is not None:
                response = await self.client.post(
                    "https://api.resend.com/emails", headers=headers, json=payload
                )
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        "https://api.resend.com/emails", headers=headers, json=payload
                    )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Email provider request failed") from exc
        if response.status_code >= 300:
            raise EmailDeliveryError(f"Email provider returned HTTP {response.status_code}")

    async def send_magic_link(self, recipient: str, magic_link: str) -> None:
        safe_link = html.escape(magic_link, quote=True)
        await self._send(
            recipient,
            "Il tuo accesso a LAGGENTE",
            (
                "<p>Usa questo link per entrare nel tuo Studio LAGGENTE.</p>"
                f'<p><a href="{safe_link}">Entra nello Studio</a></p>'
                "<p>Il link scade tra 15 minuti e può essere usato una sola volta.</p>"
            ),
            (
                "Usa questo link per entrare nel tuo Studio LAGGENTE:\n\n"
                f"{magic_link}\n\n"
                "Il link scade tra 15 minuti e può essere usato una sola volta."
            ),
        )

    async def send_professional_invitation(
        self, recipient: str, invitation_link: str, inviter_name: str
    ) -> None:
        safe_link = html.escape(invitation_link, quote=True)
        safe_inviter = html.escape(inviter_name)
        await self._send(
            recipient,
            "Crea il tuo spazio su LAGGENTE",
            (
                f"<p>{safe_inviter} ti ha invitato a creare il tuo spazio professionale "
                "su LAGGENTE.</p>"
                "<p>Apri il link, racconta allo Studio come lavori, scegli il tuo indirizzo "
                "e pubblica quando lo spazio ti rappresenta.</p>"
                f'<p><a href="{safe_link}">Crea il mio spazio</a></p>'
                "<p>Il link è personale e può essere usato una sola volta.</p>"
            ),
            (
                f"{inviter_name} ti ha invitato a creare il tuo spazio professionale "
                "su LAGGENTE.\n\n"
                "Apri il link, racconta allo Studio come lavori, scegli il tuo indirizzo "
                "e pubblica quando lo spazio ti rappresenta.\n\n"
                f"{invitation_link}\n\n"
                "Il link è personale e può essere usato una sola volta."
            ),
        )
