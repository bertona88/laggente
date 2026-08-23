from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..dependencies import (
    ProfessionalContext,
    current_professional,
    professional_space,
    runtime_settings,
)
from ..models import Conversation, Event, Message, ProfessionalEmail, Space, utcnow
from ..professional_email import (
    PreparedProfessionalEmail,
    ProfessionalEmailError,
    normalize_address,
    verify_resend_webhook,
)
from ..schemas import (
    InboundProfessionalEmail,
    ProfessionalEmailOut,
    ResendEmailReceivedData,
    ResendWebhookEvent,
)

router = APIRouter(tags=["professional-email"])


def _owned_email(
    db: Session, *, email_id: str, account_id: str, space_id: str, lock: bool = False
) -> ProfessionalEmail | None:
    statement = select(ProfessionalEmail).where(
        ProfessionalEmail.id == email_id,
        ProfessionalEmail.account_id == account_id,
        ProfessionalEmail.space_id == space_id,
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


@router.get("/studio/email", response_model=list[ProfessionalEmailOut])
def list_professional_email(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> list[ProfessionalEmailOut]:
    space = professional_space(db, context)
    records = db.scalars(
        select(ProfessionalEmail)
        .where(
            ProfessionalEmail.account_id == context.account_id,
            ProfessionalEmail.space_id == space.id,
        )
        .order_by(ProfessionalEmail.created_at.desc())
        .limit(30)
    ).all()
    return [ProfessionalEmailOut.model_validate(item) for item in records]


@router.post(
    "/studio/email/{email_id}/authorize", response_model=ProfessionalEmailOut
)
async def authorize_professional_email(
    email_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> ProfessionalEmailOut:
    if not settings.agent_mail_enabled:
        raise HTTPException(status_code=409, detail="La posta professionale non è ancora attiva")
    request.app.state.rate_limiter.check(
        f"professional-email-send:{context.member.id}", limit=10, window_seconds=3600
    )
    space = professional_space(db, context)
    email = _owned_email(
        db,
        email_id=email_id,
        account_id=context.account_id,
        space_id=space.id,
        lock=True,
    )
    if not email or email.direction != "outbound":
        raise HTTPException(status_code=404, detail="Email non trovata")
    if email.status in {"sent", "simulated"}:
        return ProfessionalEmailOut.model_validate(email)
    if email.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Questa versione non può essere inviata. Chiedi a Studio una nuova bozza.",
        )

    email.status = "sending"
    email.authorized_by_member_id = context.member.id
    email.authorized_at = utcnow()
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            conversation_id=email.studio_conversation_id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="professional_email_authorized",
            payload={"email_id": email.id, "raw_sha256": email.raw_sha256},
        )
    )
    prepared = PreparedProfessionalEmail(
        id=email.id,
        from_address=email.from_address,
        to_address=email.to_address,
        raw_content=bytes(email.raw_content),
    )
    db.commit()

    try:
        result = await request.app.state.professional_mail_transport.send(prepared)
    except Exception as exc:
        db.rollback()
        email = _owned_email(
            db,
            email_id=email_id,
            account_id=context.account_id,
            space_id=space.id,
            lock=True,
        )
        if email:
            email.status = "failed"
            email.failure_code = type(exc).__name__[:120]
            db.add(
                Event(
                    account_id=context.account_id,
                    space_id=space.id,
                    conversation_id=email.studio_conversation_id,
                    actor_type="system",
                    event_type="professional_email_delivery_failed",
                    payload={"email_id": email.id, "error_type": type(exc).__name__},
                )
            )
            db.commit()
        raise HTTPException(
            status_code=503,
            detail="Consegna non confermata. L'email non verrà ritentata automaticamente.",
        ) from exc

    email = _owned_email(
        db,
        email_id=email_id,
        account_id=context.account_id,
        space_id=space.id,
        lock=True,
    )
    if not email:
        raise HTTPException(status_code=404, detail="Email non trovata")
    email.provider = result.provider
    email.provider_message_id = result.provider_message_id
    email.failure_code = None
    email.status = "sent" if result.delivered else "simulated"
    email.sent_at = utcnow() if result.delivered else None
    system_text = (
        f"Email a {email.to_address} inviata."
        if result.delivered
        else f"Invio a {email.to_address} simulato: nessuna email è uscita da LAGGENTE."
    )
    db.add(
        Message(
            account_id=context.account_id,
            conversation_id=email.studio_conversation_id,
            author_type="system",
            author_label="LAGGENTE",
            content=system_text,
        )
    )
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            conversation_id=email.studio_conversation_id,
            actor_type="system",
            event_type=(
                "professional_email_sent" if result.delivered else "professional_email_simulated"
            ),
            payload={
                "email_id": email.id,
                "provider": result.provider,
                "provider_message_id": result.provider_message_id,
            },
        )
    )
    db.commit()
    db.refresh(email)
    return ProfessionalEmailOut.model_validate(email)


def _verify_inbound_signature(request_body: bytes, request: Request, settings: Settings) -> None:
    timestamp_text = request.headers.get("X-Laggente-Timestamp", "")
    signature = request.headers.get("X-Laggente-Signature", "")
    try:
        timestamp = int(timestamp_text)
    except ValueError:
        raise HTTPException(status_code=401, detail="Firma inbound non valida")
    now = int(datetime.now(UTC).timestamp())
    if abs(now - timestamp) > 300 or not settings.agent_mail_inbound_secret:
        raise HTTPException(status_code=401, detail="Firma inbound non valida")
    expected = hmac.new(
        settings.agent_mail_inbound_secret.encode("utf-8"),
        timestamp_text.encode("ascii") + b"." + request_body,
        hashlib.sha256,
    ).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="Firma inbound non valida")


def _plain_body(parsed) -> str:
    if parsed.is_multipart():
        for part in parsed.walk():
            if part.get_content_type() == "text/plain" and not part.get_content_disposition():
                try:
                    return str(part.get_content())[:20_000]
                except Exception:
                    continue
        return "[Email senza parte testuale leggibile]"
    try:
        return str(parsed.get_content())[:20_000]
    except Exception:
        return "[Email non leggibile]"


def _store_inbound_email(
    db: Session,
    *,
    settings: Settings,
    recipient_value: str,
    receipt_id: str,
    raw: bytes,
    received_at: datetime | None,
    provider: str,
) -> ProfessionalEmailOut:
    if len(raw) > settings.agent_mail_max_inbound_bytes:
        raise HTTPException(status_code=413, detail="Email inbound troppo grande")

    try:
        recipient = normalize_address(recipient_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Destinatario inbound non valido") from exc
    local, _, domain = recipient.partition("@")
    if domain.lower() != settings.agent_mail_reply_domain.lower():
        raise HTTPException(status_code=404, detail="Destinatario non riconosciuto")
    slug, _, reply_id = local.partition("+")
    slug = slug.lower()
    space = db.scalar(select(Space).where(Space.slug == slug, Space.is_active.is_(True)))
    if not space:
        raise HTTPException(status_code=404, detail="Destinatario non riconosciuto")
    duplicate = db.scalar(
        select(ProfessionalEmail).where(
            ProfessionalEmail.account_id == space.account_id,
            ProfessionalEmail.space_id == space.id,
            ProfessionalEmail.provider == provider,
            ProfessionalEmail.provider_message_id == receipt_id,
        )
    )
    if duplicate:
        return ProfessionalEmailOut.model_validate(duplicate)
    studio = db.scalar(
        select(Conversation).where(
            Conversation.account_id == space.account_id,
            Conversation.space_id == space.id,
            Conversation.kind == "studio",
        )
    )
    if not studio:
        raise HTTPException(status_code=409, detail="Studio non disponibile")

    parsed = BytesParser(policy=policy.default).parsebytes(raw)
    try:
        sender = normalize_address(parseaddr(str(parsed.get("From", "")))[1])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Mittente inbound non valido") from exc
    subject = str(parsed.get("Subject", "(senza oggetto)"))[:300]
    internet_message_id = str(parsed.get("Message-ID", ""))[:998] or None
    reply_to_email = None
    if reply_id:
        reply_to_email = db.scalar(
            select(ProfessionalEmail).where(
                ProfessionalEmail.id == reply_id,
                ProfessionalEmail.account_id == space.account_id,
                ProfessionalEmail.space_id == space.id,
                ProfessionalEmail.direction == "outbound",
            )
        )
    received_at = received_at or utcnow()
    plain_body = _plain_body(parsed)
    record = ProfessionalEmail(
        account_id=space.account_id,
        space_id=space.id,
        studio_conversation_id=studio.id,
        in_reply_to_email_id=reply_to_email.id if reply_to_email else None,
        direction="inbound",
        status="received",
        from_address=sender,
        to_address=recipient,
        subject=subject,
        body_text=plain_body,
        raw_content=raw,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        content_sha256=hashlib.sha256(plain_body.encode("utf-8")).hexdigest(),
        internet_message_id=internet_message_id,
        provider=provider,
        provider_message_id=receipt_id,
        received_at=received_at,
    )
    db.add(record)
    db.flush()
    db.add(
        Message(
            account_id=space.account_id,
            conversation_id=studio.id,
            author_type="system",
            author_label="LAGGENTE",
            content=(
                f"Nuova email ricevuta da {record.from_address}: “{record.subject}”. "
                "Il contenuto esterno è non attendibile finché non lo esamini con Studio."
            ),
        )
    )
    db.add(
        Event(
            account_id=space.account_id,
            space_id=space.id,
            conversation_id=studio.id,
            actor_type="system",
            event_type="professional_email_received",
            payload={
                "email_id": record.id,
                "receipt_id": receipt_id,
                "provider": provider,
                "raw_sha256": record.raw_sha256,
                "content_is_untrusted": True,
            },
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.scalar(
            select(ProfessionalEmail).where(
                ProfessionalEmail.account_id == space.account_id,
                ProfessionalEmail.space_id == space.id,
                ProfessionalEmail.provider == provider,
                ProfessionalEmail.provider_message_id == receipt_id,
            )
        )
        if not duplicate:
            raise
        return ProfessionalEmailOut.model_validate(duplicate)
    db.refresh(record)
    return ProfessionalEmailOut.model_validate(record)


@router.post(
    "/integrations/professional-email/inbound",
    response_model=ProfessionalEmailOut,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_professional_email(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> ProfessionalEmailOut:
    """Future SES/S3 relay endpoint retained behind the replaceable transport boundary."""

    if not settings.agent_mail_enabled or settings.agent_mail_provider not in {"capture", "ses"}:
        raise HTTPException(status_code=404, detail="Not Found")
    request_body = await request.body()
    if len(request_body) > settings.agent_mail_max_inbound_bytes * 2:
        raise HTTPException(status_code=413, detail="Payload inbound troppo grande")
    _verify_inbound_signature(request_body, request, settings)
    try:
        body = InboundProfessionalEmail.model_validate(json.loads(request_body))
        raw = base64.b64decode(body.raw_base64, validate=True)
    except (json.JSONDecodeError, ValidationError, binascii.Error, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Payload inbound non valido") from exc
    return _store_inbound_email(
        db,
        settings=settings,
        recipient_value=str(body.recipient),
        receipt_id=body.receipt_id,
        raw=raw,
        received_at=body.received_at,
        provider="inbound_relay",
    )


@router.post(
    "/integrations/professional-email/resend",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_resend_professional_email(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> ProfessionalEmailOut | Response:
    if not settings.agent_mail_enabled or settings.agent_mail_provider != "resend":
        raise HTTPException(status_code=404, detail="Not Found")
    request_body = await request.body()
    if len(request_body) > 256 * 1024:
        raise HTTPException(status_code=413, detail="Webhook troppo grande")
    try:
        verify_resend_webhook(
            request_body,
            {key.lower(): value for key, value in request.headers.items()},
            settings.resend_webhook_secret or "",
            now=int(datetime.now(UTC).timestamp()),
        )
    except ProfessionalEmailError as exc:
        raise HTTPException(status_code=401, detail="Firma webhook non valida") from exc
    try:
        event = ResendWebhookEvent.model_validate(json.loads(request_body))
    except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Webhook non valido") from exc
    if event.type != "email.received":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        data = ResendEmailReceivedData.model_validate(event.data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Evento email.received non valido") from exc
    recipient = next(
        (
            str(address)
            for address in data.to
            if str(address).lower().endswith(f"@{settings.agent_mail_reply_domain}")
        ),
        None,
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="Destinatario non riconosciuto")
    try:
        raw = await request.app.state.resend_inbound_source.retrieve_raw(data.email_id)
    except ProfessionalEmailError as exc:
        if str(exc) == "inbound_email_too_large":
            raise HTTPException(status_code=413, detail="Email inbound troppo grande") from exc
        raise HTTPException(status_code=503, detail="Email inbound non disponibile") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Email inbound non disponibile") from exc
    return _store_inbound_email(
        db,
        settings=settings,
        recipient_value=recipient,
        receipt_id=data.email_id,
        raw=raw,
        received_at=data.created_at,
        provider="resend_inbound",
    )
