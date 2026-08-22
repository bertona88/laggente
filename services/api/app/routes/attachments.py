from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from weakref import WeakValueDictionary

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..conversations import active_revision
from ..database import get_db
from ..dependencies import authorize_public_conversation, runtime_settings
from ..media import (
    ALLOWED_MEDIA_TYPES,
    attachment_content_url,
    media_magic_matches,
)
from ..models import Attachment, Conversation, Event, Member, Space, utcnow
from ..rate_limit import client_ip
from ..retention import (
    discard_stale_transcription_reservations,
    discard_stale_unbound_attachments,
)
from ..schemas import AttachmentCreated, AttachmentOut
from ..security import hash_token, new_opaque_token, read_session_claims
from ..tenant import require_public_space_host

router = APIRouter(tags=["attachments"])

# Platform-owned pilot ceilings: one public tenant cannot fill the WOFI-shared disk or create
# unbounded transcription spend even when source-IP limits are distributed across a botnet.
MAX_DURABLE_ACCOUNT_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_DURABLE_CONVERSATION_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ACCOUNT_AUDIO_TRANSCRIPTIONS_PER_HOUR = 12
AUDIO_MEDIA_TYPES = tuple(
    media_type for media_type, (media_kind, _) in ALLOWED_MEDIA_TYPES.items() if media_kind == "audio"
)
_upload_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


def _upload_lock(account_id: str) -> asyncio.Lock:
    lock = _upload_locks.get(account_id)
    if lock is None:
        lock = asyncio.Lock()
        _upload_locks[account_id] = lock
    return lock


def _lock_upload_conversation(
    request: Request,
    db: Session,
    conversation_id: str,
    media_kind: str,
) -> Conversation:
    """Reauthorize and lock the tenant conversation before quota or lifecycle mutations."""

    authorized = authorize_public_conversation(request, db, conversation_id)
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.id == authorized.id,
            Conversation.account_id == authorized.account_id,
            Conversation.space_id == authorized.space_id,
            Conversation.kind == "public",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    space = db.scalar(
        select(Space).where(
            Space.id == conversation.space_id,
            Space.account_id == conversation.account_id,
            Space.is_active.is_(True),
        )
    )
    revision = active_revision(db, space) if space else None
    capabilities = revision.document.get("capabilities", {}) if revision else {}
    capability_name = "photographs" if media_kind == "image" else "voice_notes"
    if capabilities.get(capability_name) is not True:
        raise HTTPException(status_code=403, detail="Questa funzione non è attiva nello spazio")
    return conversation


def _lock_pending_audio_reservation(
    db: Session,
    *,
    attachment_id: str,
    account_id: str,
    space_id: str,
    conversation_id: str,
) -> tuple[Conversation, Attachment] | None:
    """Lock a still-live audio draft after returning from the external provider."""

    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.account_id == account_id,
            Conversation.space_id == space_id,
            Conversation.kind == "public",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not conversation:
        return None
    attachment = db.scalar(
        select(Attachment)
        .where(
            Attachment.id == attachment_id,
            Attachment.account_id == account_id,
            Attachment.space_id == space_id,
            Attachment.conversation_id == conversation_id,
            Attachment.status == "transcribing",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not attachment:
        return None
    return conversation, attachment


def _authorized_attachment(request: Request, db: Session, attachment_id: str) -> Attachment:
    attachment = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if not attachment:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == attachment.conversation_id,
            Conversation.account_id == attachment.account_id,
            Conversation.space_id == attachment.space_id,
        )
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    settings = runtime_settings(request)
    space = db.scalar(
        select(Space).where(
            Space.id == conversation.space_id,
            Space.account_id == conversation.account_id,
        )
    )
    if not space:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    visitor_token = request.headers.get("X-Conversation-Token") or request.cookies.get(
        settings.visitor_cookie_name
    )
    if visitor_token and conversation.visitor_token_hash == hash_token(visitor_token):
        try:
            require_public_space_host(request, settings, space)
        except HTTPException:
            # A professional session on app.laggente.com may coexist with a stale visitor cookie;
            # let the authenticated-member path below decide access in that case.
            pass
        else:
            within_retention = db.scalar(
                select(Conversation.id).where(
                    Conversation.id == conversation.id,
                    Conversation.last_message_at
                    >= utcnow() - timedelta(days=settings.conversation_retention_days),
                )
            )
            if space.is_active and within_retention:
                return attachment
    try:
        claims = read_session_claims(request, settings)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    member = db.scalar(
        select(Member).where(
            Member.id == claims.member_id,
            Member.account_id == claims.account_id,
            Member.account_id == attachment.account_id,
            Member.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    return attachment


@router.post(
    "/public/conversations/{conversation_id}/attachments",
    response_model=AttachmentCreated,
    status_code=201,
)
async def upload_public_attachment(
    conversation_id: str,
    request: Request,
    file: UploadFile = File(...),
    kind: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> AttachmentCreated:
    request.app.state.rate_limiter.check(
        f"upload:{client_ip(request)}", limit=12, window_seconds=10 * 60
    )
    conversation = authorize_public_conversation(request, db, conversation_id)
    request.app.state.rate_limiter.check(
        f"upload-space:{conversation.space_id}", limit=60, window_seconds=60 * 60
    )
    upload_account_id = conversation.account_id
    # Do not retain the synchronous authorization transaction while reading a potentially slow
    # request body or waiting for another upload from the same account. Authorization and active
    # capability checks are repeated inside the serialized quota section below.
    db.commit()
    declared_type = (file.content_type or "").lower().split(";", 1)[0].strip()
    media = ALLOWED_MEDIA_TYPES.get(declared_type)
    if not media:
        raise HTTPException(status_code=415, detail="Tipo di file non supportato")
    media_kind, extension = media
    if kind and kind not in {"image", "audio"}:
        raise HTTPException(status_code=422, detail="Tipo di allegato non valido")
    if kind and kind != media_kind:
        raise HTTPException(status_code=415, detail="Il contenuto non corrisponde al tipo dichiarato")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="File troppo grande")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data or not media_magic_matches(data[:64], declared_type):
        raise HTTPException(status_code=415, detail="Contenuto del file non valido")
    async with _upload_lock(upload_account_id):
        db.expire_all()
        conversation = _lock_upload_conversation(request, db, conversation_id, media_kind)
        stale_audio = discard_stale_transcription_reservations(
            db,
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            commit=False,
        )
        # The conversation row lock is the same lock used when a visitor binds an attachment to a
        # message. Rechecking stale drafts here can therefore free the per-conversation slot without
        # deleting a photograph or transcript that is concurrently being sent.
        stale_attachments = discard_stale_unbound_attachments(
            db,
            settings,
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            commit=False,
        )
        if stale_audio or stale_attachments:
            # Files have already been unlinked, so commit their row cleanup before any later quota
            # or provider failure can roll the new upload transaction back. Committing releases the
            # row lock; immediately reauthorize and reacquire it before accepting another record.
            db.commit()
            db.expire_all()
            conversation = _lock_upload_conversation(request, db, conversation_id, media_kind)
        existing_count = db.scalar(
            select(func.count(Attachment.id)).where(
                Attachment.account_id == conversation.account_id,
                Attachment.conversation_id == conversation.id,
            )
        )
        if (existing_count or 0) >= 20:
            raise HTTPException(status_code=409, detail="Limite allegati raggiunto")

        if media_kind == "image":
            account_bytes = db.scalar(
                select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
                    Attachment.account_id == conversation.account_id,
                    Attachment.status == "available",
                )
            )
            conversation_bytes = db.scalar(
                select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
                    Attachment.account_id == conversation.account_id,
                    Attachment.conversation_id == conversation.id,
                    Attachment.status == "available",
                )
            )
            if int(account_bytes or 0) + total > MAX_DURABLE_ACCOUNT_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=409,
                    detail="Spazio disponibile per gli allegati esaurito",
                )
            if int(conversation_bytes or 0) + total > MAX_DURABLE_CONVERSATION_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=409,
                    detail="Limite spazio allegati della conversazione raggiunto",
                )
        else:
            transcription_count = db.scalar(
                select(func.count(Event.id)).where(
                    Event.account_id == conversation.account_id,
                    Event.event_type == "audio_transcription_started",
                    Event.created_at >= utcnow() - timedelta(hours=1),
                )
            )
            if int(transcription_count or 0) >= MAX_ACCOUNT_AUDIO_TRANSCRIPTIONS_PER_HOUR:
                raise HTTPException(
                    status_code=429,
                    detail="Limite temporaneo delle trascrizioni raggiunto. Riprova più tardi.",
                )

        opaque_name = f"{new_opaque_token()}{extension}"
        storage_key = (
            f"discarded-audio/{conversation.account_id}/{conversation.id}/{opaque_name}"
            if media_kind == "audio"
            else f"{conversation.account_id}/{conversation.id}/{opaque_name}"
        )
        original_name = Path(file.filename or f"allegato{extension}").name[:255]
        attachment = Attachment(
            account_id=conversation.account_id,
            space_id=conversation.space_id,
            conversation_id=conversation.id,
            uploader_type="visitor",
            storage_key=storage_key,
            original_name=original_name,
            media_type=declared_type,
            size_bytes=total,
            sha256=hashlib.sha256(data).hexdigest(),
            status="transcribing" if media_kind == "audio" else "available",
        )
        db.add(attachment)
        transcript = None
        download_url = None
        target: Path | None = None
        try:
            # Flush before touching the filesystem: a DB failure cannot orphan a file.
            db.flush()
            if media_kind == "audio":
                # This content-free account event survives conversation deletion, so deleting a
                # throwaway thread cannot reset the rolling transcription-spend ceiling.
                db.add(
                    Event(
                        account_id=conversation.account_id,
                        space_id=conversation.space_id,
                        conversation_id=None,
                        actor_type="system",
                        event_type="audio_transcription_started",
                        payload={"attachment_id": attachment.id},
                    )
                )
            if media_kind == "audio":
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix="laggente-audio-", suffix=extension, dir="/tmp"
                )
                os.close(descriptor)
                target = Path(temporary_name)
            else:
                target = settings.upload_dir / storage_key
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                for private_dir in (target.parent.parent, target.parent):
                    private_dir.chmod(0o700)
            target.write_bytes(data)
            target.chmod(0o600)

            if media_kind == "audio":
                # Persist the quota reservation and release the synchronous DB connection before
                # the external transcription await. Raw audio remains only in non-backed /tmp.
                pending_attachment_id = attachment.id
                pending_account_id = conversation.account_id
                pending_space_id = conversation.space_id
                pending_conversation_id = conversation.id
                db.commit()
                try:
                    transcript = await request.app.state.audio_transcriber.transcribe(
                        target, declared_type
                    )
                    db.expire_all()
                    pending = _lock_pending_audio_reservation(
                        db,
                        attachment_id=pending_attachment_id,
                        account_id=pending_account_id,
                        space_id=pending_space_id,
                        conversation_id=pending_conversation_id,
                    )
                    if not pending:
                        db.rollback()
                        raise HTTPException(
                            status_code=status.HTTP_410_GONE,
                            detail="Conversazione eliminata durante la trascrizione",
                        )
                    conversation, attachment = pending
                    attachment.transcript = transcript
                    attachment.status = "transcribed"
                except asyncio.CancelledError:
                    # The account-scoped attempt event was committed before the external call and
                    # remains for spend control. The unusable row itself must not consume one of the
                    # conversation's 20 attachment slots.
                    try:
                        db.expire_all()
                        pending = _lock_pending_audio_reservation(
                            db,
                            attachment_id=pending_attachment_id,
                            account_id=pending_account_id,
                            space_id=pending_space_id,
                            conversation_id=pending_conversation_id,
                        )
                        if pending:
                            conversation, attachment = pending
                            db.add(
                                Event(
                                    account_id=pending_account_id,
                                    space_id=pending_space_id,
                                    conversation_id=pending_conversation_id,
                                    actor_type="system",
                                    event_type="audio_transcription_failed",
                                    payload={
                                        "attachment_id": pending_attachment_id,
                                        "error_type": "CancelledError",
                                    },
                                )
                            )
                            db.delete(attachment)
                            db.commit()
                        else:
                            db.rollback()
                    except Exception:
                        db.rollback()
                    raise
                except Exception as exc:
                    if isinstance(exc, HTTPException):
                        raise
                    db.expire_all()
                    pending = _lock_pending_audio_reservation(
                        db,
                        attachment_id=pending_attachment_id,
                        account_id=pending_account_id,
                        space_id=pending_space_id,
                        conversation_id=pending_conversation_id,
                    )
                    if not pending:
                        db.rollback()
                        raise HTTPException(
                            status_code=status.HTTP_410_GONE,
                            detail="Conversazione eliminata durante la trascrizione",
                        ) from exc
                    conversation, attachment = pending
                    db.add(
                        Event(
                            account_id=pending_account_id,
                            space_id=pending_space_id,
                            conversation_id=pending_conversation_id,
                            actor_type="system",
                            event_type="audio_transcription_failed",
                            payload={
                                "attachment_id": pending_attachment_id,
                                "error_type": type(exc).__name__,
                            },
                        )
                    )
                    db.delete(attachment)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Trascrizione non disponibile. Riprova più tardi.",
                    ) from exc
            else:
                download_url = attachment_content_url(attachment)
            db.add(
                Event(
                    account_id=conversation.account_id,
                    space_id=conversation.space_id,
                    conversation_id=conversation.id,
                    actor_type="visitor",
                    event_type="attachment_uploaded",
                    payload={
                        "attachment_id": attachment.id,
                        "kind": media_kind,
                        "size_bytes": total,
                        "raw_audio_deleted": media_kind == "audio",
                    },
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            if target:
                target.unlink(missing_ok=True)
            raise
        finally:
            if media_kind == "audio" and target:
                target.unlink(missing_ok=True)
        return AttachmentCreated(
            attachment=AttachmentOut.model_validate(attachment),
            transcript=transcript,
            download_url=download_url,
        )


def _attachment_file_response(attachment: Attachment, settings: Settings) -> FileResponse:
    base = settings.upload_dir.resolve()
    target = (settings.upload_dir / attachment.storage_key).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    return FileResponse(
        target,
        media_type=attachment.media_type,
        filename=attachment.original_name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


@router.get("/attachments/{attachment_id}/content", include_in_schema=False)
def attachment_content(
    attachment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
):
    attachment = _authorized_attachment(request, db, attachment_id)
    if attachment.status != "available":
        raise HTTPException(status_code=410, detail="File originale non disponibile")
    return _attachment_file_response(attachment, settings)
