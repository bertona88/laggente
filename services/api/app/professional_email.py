from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import SMTP
from email.utils import format_datetime, make_msgid
from typing import Protocol
from urllib.parse import urlparse

import httpx
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Conversation, Event, ProfessionalEmail, Space, new_id, utcnow

MAX_SUBJECT_LENGTH = 300
MAX_BODY_LENGTH = 20_000


class ProfessionalEmailError(ValueError):
    pass


@dataclass(frozen=True)
class MailSendResult:
    delivered: bool
    provider: str
    provider_message_id: str


@dataclass(frozen=True)
class PreparedProfessionalEmail:
    id: str
    from_address: str
    to_address: str
    raw_content: bytes


class ProfessionalMailTransport(Protocol):
    async def send(self, email: PreparedProfessionalEmail) -> MailSendResult: ...


class CaptureMailTransport:
    """Development transport that records attempts without claiming external delivery."""

    def __init__(self) -> None:
        self.messages: list[bytes] = []

    async def send(self, email: PreparedProfessionalEmail) -> MailSendResult:
        self.messages.append(bytes(email.raw_content))
        return MailSendResult(
            delivered=False,
            provider="capture",
            provider_message_id=f"capture-{email.id}",
        )


class SesMailTransport:
    def __init__(
        self,
        region: str,
        *,
        access_key_id: str | None,
        secret_access_key: str | None,
        session_token: str | None,
    ):
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token

    async def send(self, email: PreparedProfessionalEmail) -> MailSendResult:
        def send_sync() -> dict:
            # Import lazily so disabled local environments do not initialize an AWS client.
            import boto3

            return boto3.client(
                "sesv2",
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                aws_session_token=self.session_token,
            ).send_email(
                FromEmailAddress=email.from_address,
                Destination={"ToAddresses": [email.to_address]},
                Content={"Raw": {"Data": bytes(email.raw_content)}},
            )

        response = await asyncio.to_thread(send_sync)
        provider_message_id = response.get("MessageId")
        if not provider_message_id:
            raise RuntimeError("SES did not return a MessageId")
        return MailSendResult(
            delivered=True,
            provider="ses",
            provider_message_id=str(provider_message_id),
        )


class ResendMailTransport:
    def __init__(
        self,
        api_key: str,
        *,
        user_agent: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.user_agent = user_agent
        self.client = client

    async def send(self, email: PreparedProfessionalEmail) -> MailSendResult:
        parsed = BytesParser(policy=policy.default).parsebytes(email.raw_content)
        body = parsed.get_body(preferencelist=("plain",))
        text = str(body.get_content()) if body else str(parsed.get_content())
        payload = {
            "from": str(parsed["From"]),
            "to": [str(parsed["To"])],
            "reply_to": str(parsed["Reply-To"]),
            "subject": str(parsed["Subject"]),
            "text": text,
            "headers": {
                "X-Laggente-Authored-By": str(parsed["X-Laggente-Authored-By"]),
                "X-Laggente-Content-SHA256": str(parsed["X-Laggente-Content-SHA256"]),
            },
            "tags": [{"name": "laggente_email_id", "value": email.id}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": f"laggente-email-{email.id}",
            "User-Agent": self.user_agent,
        }
        if self.client:
            response = await self.client.post(
                "https://api.resend.com/emails", headers=headers, json=payload
            )
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://api.resend.com/emails", headers=headers, json=payload
                )
        response.raise_for_status()
        provider_message_id = response.json().get("id")
        if not provider_message_id:
            raise RuntimeError("Resend did not return an email id")
        return MailSendResult(
            delivered=True,
            provider="resend",
            provider_message_id=str(provider_message_id),
        )


class ResendInboundSource:
    def __init__(
        self,
        api_key: str,
        *,
        user_agent: str,
        max_bytes: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.client = client

    async def _get(self, url: str, *, authenticated: bool) -> httpx.Response:
        headers = {"User-Agent": self.user_agent}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.client:
            return await self.client.get(url, headers=headers)
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            return await client.get(url, headers=headers)

    async def retrieve_raw(self, email_id: str) -> bytes:
        metadata = await self._get(
            f"https://api.resend.com/emails/receiving/{email_id}", authenticated=True
        )
        metadata.raise_for_status()
        raw_url = (metadata.json().get("raw") or {}).get("download_url")
        parsed_url = urlparse(str(raw_url or ""))
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise RuntimeError("Resend did not return a valid raw email URL")
        raw_response = await self._get(str(raw_url), authenticated=False)
        raw_response.raise_for_status()
        declared_size = int(raw_response.headers.get("Content-Length", "0") or 0)
        if declared_size > self.max_bytes or len(raw_response.content) > self.max_bytes:
            raise ProfessionalEmailError("inbound_email_too_large")
        return bytes(raw_response.content)


def verify_resend_webhook(
    request_body: bytes,
    headers: dict[str, str],
    secret: str,
    *,
    now: int,
) -> None:
    """Verify Resend's Svix signature without parsing or rewriting the signed body."""

    message_id = headers.get("svix-id", "")
    timestamp_text = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not secret.startswith("whsec_"):
        raise ProfessionalEmailError("invalid_resend_webhook_signature")
    try:
        timestamp = int(timestamp_text)
        secret_bytes = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ProfessionalEmailError("invalid_resend_webhook_signature") from exc
    if not message_id or abs(now - timestamp) > 300:
        raise ProfessionalEmailError("invalid_resend_webhook_signature")
    signed = (
        message_id.encode("utf-8")
        + b"."
        + timestamp_text.encode("ascii")
        + b"."
        + request_body
    )
    expected = base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode()
    supplied = [item.partition(",")[2] for item in signatures.split() if item.startswith("v1,")]
    if not any(hmac.compare_digest(expected, item) for item in supplied):
        raise ProfessionalEmailError("invalid_resend_webhook_signature")


def build_professional_mail_transport(settings: Settings) -> ProfessionalMailTransport:
    # Keep this boundary provider-neutral: Resend is the pilot transport, while the SES raw-MIME
    # adapter remains available for the planned later switch documented in ADR-0003.
    if settings.agent_mail_provider == "resend":
        return ResendMailTransport(
            settings.resend_api_key or "",
            user_agent=f"LAGGENTE/{settings.version}",
        )
    if settings.agent_mail_provider == "ses":
        return SesMailTransport(
            settings.agent_mail_aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            session_token=settings.aws_session_token,
        )
    return CaptureMailTransport()


def build_resend_inbound_source(settings: Settings) -> ResendInboundSource:
    return ResendInboundSource(
        settings.resend_api_key or "",
        user_agent=f"LAGGENTE/{settings.version}",
        max_bytes=settings.agent_mail_max_inbound_bytes,
    )


def normalize_address(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise ProfessionalEmailError("invalid_email_address")
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ProfessionalEmailError("invalid_email_address") from exc


def _clean_text(value: str, *, maximum: int, error: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or "\x00" in cleaned:
        raise ProfessionalEmailError(error)
    return cleaned


def _content_hash(*, sender: str, recipient: str, subject: str, body: str) -> str:
    canonical = json.dumps(
        {"from": sender, "to": recipient, "subject": subject, "body": body},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _raw_outbound_message(
    *,
    email_id: str,
    created_at: datetime,
    sender: str,
    recipient: str,
    reply_to: str,
    subject: str,
    body: str,
    message_domain: str,
    content_sha256: str,
) -> tuple[bytes, str]:
    internet_message_id = make_msgid(idstring=email_id, domain=message_domain)
    message = EmailMessage(policy=SMTP)
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = reply_to
    message["Subject"] = subject
    message["Date"] = format_datetime(created_at)
    message["Message-ID"] = internet_message_id
    message["X-Laggente-Authored-By"] = "Studio LAGGENTE"
    message["X-Laggente-Content-SHA256"] = content_sha256
    message.set_content(body, subtype="plain", charset="utf-8")
    return message.as_bytes(policy=SMTP), internet_message_id


def create_outbound_email_draft(
    db: Session,
    *,
    account_id: str,
    space_id: str,
    member_id: str,
    source_message_id: str | None,
    recipient: str,
    subject: str,
    body: str,
    from_domain: str,
    reply_domain: str,
) -> ProfessionalEmail:
    space = db.scalar(
        select(Space).where(Space.id == space_id, Space.account_id == account_id)
    )
    studio = db.scalar(
        select(Conversation).where(
            Conversation.account_id == account_id,
            Conversation.space_id == space_id,
            Conversation.kind == "studio",
        )
    )
    if not space or not studio:
        raise ProfessionalEmailError("space_not_found")

    recipient = normalize_address(recipient)
    subject = _clean_text(subject, maximum=MAX_SUBJECT_LENGTH, error="invalid_subject")
    if "\r" in subject or "\n" in subject:
        raise ProfessionalEmailError("invalid_subject")
    body = _clean_text(body, maximum=MAX_BODY_LENGTH, error="invalid_body")
    sender = normalize_address(f"{space.slug}@{from_domain}")
    email_id = new_id()
    reply_to = normalize_address(f"{space.slug}+{email_id}@{reply_domain}")
    created_at = utcnow()
    sealed_body = (
        f"{body}\n\n---\n"
        f"Messaggio preparato dall’assistente AI Studio LAGGENTE e autorizzato da "
        f"{space.professional_name}."
    )
    content_sha256 = _content_hash(
        sender=sender, recipient=recipient, subject=subject, body=sealed_body
    )
    raw_content, internet_message_id = _raw_outbound_message(
        email_id=email_id,
        created_at=created_at,
        sender=sender,
        recipient=recipient,
        reply_to=reply_to,
        subject=subject,
        body=sealed_body,
        message_domain=from_domain,
        content_sha256=content_sha256,
    )

    pending = db.scalars(
        select(ProfessionalEmail).where(
            ProfessionalEmail.account_id == account_id,
            ProfessionalEmail.space_id == space_id,
            ProfessionalEmail.direction == "outbound",
            ProfessionalEmail.status == "draft",
        )
    ).all()
    for previous in pending:
        previous.status = "superseded"

    email = ProfessionalEmail(
        id=email_id,
        account_id=account_id,
        space_id=space_id,
        studio_conversation_id=studio.id,
        source_message_id=source_message_id,
        direction="outbound",
        status="draft",
        from_address=sender,
        to_address=recipient,
        reply_to_address=reply_to,
        subject=subject,
        body_text=sealed_body,
        raw_content=raw_content,
        raw_sha256=hashlib.sha256(raw_content).hexdigest(),
        content_sha256=content_sha256,
        internet_message_id=internet_message_id,
        proposed_by_member_id=member_id,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(email)
    db.flush()
    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            conversation_id=studio.id,
            actor_type="studio_assistant",
            actor_id="studio_assistant",
            event_type="professional_email_proposed",
            payload={
                "email_id": email.id,
                "recipient": email.to_address,
                "content_sha256": email.content_sha256,
                "requires_explicit_authorization": True,
            },
        )
    )
    db.commit()
    db.refresh(email)
    return email
