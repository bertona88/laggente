from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Attachment, Conversation, Event, MemoryItem, Message, SignupLink, utcnow


STALE_TRANSCRIPTION_RESERVATION_TTL = timedelta(minutes=30)
STALE_UNBOUND_ATTACHMENT_TTL = timedelta(hours=1)
EXPIRED_SIGNUP_LINK_RETENTION = timedelta(days=1)


@dataclass(frozen=True)
class DeletionResult:
    conversation_ref: str
    messages_deleted: int
    memories_deleted: int
    attachments_deleted: int
    files_deleted: int


def purge_expired_signup_links(
    db: Session,
    *,
    now: datetime | None = None,
    commit: bool = True,
) -> int:
    """Remove pre-tenant email proofs shortly after they can no longer be used."""

    cutoff = (now or utcnow()) - EXPIRED_SIGNUP_LINK_RETENTION
    result = db.execute(delete(SignupLink).where(SignupLink.expires_at < cutoff))
    if commit:
        db.commit()
    return result.rowcount or 0


def _conversation_ref(settings: Settings, conversation_id: str) -> str:
    return hashlib.sha256(
        f"{settings.session_secret}:deleted-conversation:{conversation_id}".encode()
    ).hexdigest()


def _private_attachment_path(settings: Settings, storage_key: str) -> Path:
    base = settings.upload_dir.resolve()
    target = (settings.upload_dir / storage_key).resolve()
    if not target.is_relative_to(base):
        raise RuntimeError("Attachment path escaped the private upload directory")
    return target


def _utc_datetime(value: datetime) -> datetime:
    """Normalize driver-specific timestamp values for an in-process cutoff comparison.

    PostgreSQL returns aware values for ``TIMESTAMP WITH TIME ZONE`` while SQLite drops timezone
    information even when SQLAlchemy's ``timezone=True`` flag is present. Both represent UTC in
    this application.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def delete_conversation_data(
    db: Session,
    settings: Settings,
    *,
    conversation: Conversation,
    actor_type: str,
    actor_id: str | None,
    trigger: str,
    only_if_last_message_before: datetime | None = None,
    only_if_created_before: datetime | None = None,
    only_if_unengaged: bool = False,
) -> DeletionResult | None:
    """Delete one scoped conversation and leave only content-free outcome metadata.

    Raw files are unlinked before the database transaction completes. A database failure can
    therefore leave unavailable attachment metadata, but cannot resurrect a private file.
    """

    locked_conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation.id,
            Conversation.account_id == conversation.account_id,
            Conversation.space_id == conversation.space_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_conversation:
        return DeletionResult(
            conversation_ref=_conversation_ref(settings, conversation.id),
            messages_deleted=0,
            memories_deleted=0,
            attachments_deleted=0,
            files_deleted=0,
        )
    if (
        only_if_last_message_before is not None
        and _utc_datetime(locked_conversation.last_message_at)
        >= _utc_datetime(only_if_last_message_before)
    ):
        # Retention candidates are discovered before their row locks are acquired. A concurrent
        # visitor turn may have refreshed the conversation in between; never delete that now-live
        # thread. Explicit visitor/professional deletion does not pass this condition.
        db.rollback()
        return None
    if (
        only_if_created_before is not None
        and _utc_datetime(locked_conversation.created_at) >= _utc_datetime(only_if_created_before)
    ):
        db.rollback()
        return None
    if only_if_unengaged:
        has_human_message = db.scalar(
            select(Message.id)
            .where(
                Message.account_id == locked_conversation.account_id,
                Message.conversation_id == locked_conversation.id,
                Message.author_type.in_(["visitor", "professional"]),
            )
            .limit(1)
        )
        has_bound_attachment = db.scalar(
            select(Attachment.id)
            .where(
                Attachment.account_id == locked_conversation.account_id,
                Attachment.conversation_id == locked_conversation.id,
                Attachment.message_id.is_not(None),
            )
            .limit(1)
        )
        if locked_conversation.professional_joined or has_human_message or has_bound_attachment:
            db.rollback()
            return None
    conversation = locked_conversation

    attachments = list(
        db.scalars(
            select(Attachment).where(
                Attachment.account_id == conversation.account_id,
                Attachment.conversation_id == conversation.id,
            )
        ).all()
    )
    files_deleted = 0
    for attachment in attachments:
        target = _private_attachment_path(settings, attachment.storage_key)
        if target.exists():
            if not target.is_file():
                raise RuntimeError("Attachment target is not a regular file")
            target.unlink()
            files_deleted += 1

    message_count = len(
        db.scalars(
            select(Message.id).where(
                Message.account_id == conversation.account_id,
                Message.conversation_id == conversation.id,
            )
        ).all()
    )
    memory_count = len(
        db.scalars(
            select(MemoryItem.id).where(
                MemoryItem.account_id == conversation.account_id,
                MemoryItem.conversation_id == conversation.id,
            )
        ).all()
    )
    conversation_ref = _conversation_ref(settings, conversation.id)
    db.execute(
        delete(Event).where(
            Event.account_id == conversation.account_id,
            Event.conversation_id == conversation.id,
        )
    )
    db.execute(
        delete(Attachment).where(
            Attachment.account_id == conversation.account_id,
            Attachment.conversation_id == conversation.id,
        )
    )
    db.execute(
        delete(MemoryItem).where(
            MemoryItem.account_id == conversation.account_id,
            MemoryItem.conversation_id == conversation.id,
        )
    )
    db.execute(
        delete(Message).where(
            Message.account_id == conversation.account_id,
            Message.conversation_id == conversation.id,
        )
    )
    db.execute(
        delete(Conversation).where(
            Conversation.id == conversation.id,
            Conversation.account_id == conversation.account_id,
            Conversation.space_id == conversation.space_id,
        )
    )
    result = DeletionResult(
        conversation_ref=conversation_ref,
        messages_deleted=message_count,
        memories_deleted=memory_count,
        attachments_deleted=len(attachments),
        files_deleted=files_deleted,
    )
    db.add(
        Event(
            account_id=conversation.account_id,
            space_id=conversation.space_id,
            conversation_id=None,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type="conversation_deletion_completed",
            payload={
                "conversation_ref": result.conversation_ref,
                "trigger": trigger,
                "messages_deleted": result.messages_deleted,
                "memories_deleted": result.memories_deleted,
                "attachments_deleted": result.attachments_deleted,
                "files_deleted": result.files_deleted,
            },
        )
    )
    db.commit()
    return result


def purge_expired_conversations(
    db: Session,
    settings: Settings,
    *,
    account_id: str,
    now: datetime | None = None,
) -> list[DeletionResult]:
    cutoff = (now or utcnow()) - timedelta(days=settings.conversation_retention_days)
    expired = list(
        db.scalars(
            select(Conversation).where(
                Conversation.account_id == account_id,
                Conversation.kind == "public",
                Conversation.last_message_at < cutoff,
            )
        ).all()
    )
    results = [
        delete_conversation_data(
            db,
            settings,
            conversation=conversation,
            actor_type="system",
            actor_id=None,
            trigger="retention_policy",
            only_if_last_message_before=cutoff,
        )
        for conversation in expired
    ]
    return [result for result in results if result is not None]


def purge_all_expired_conversations(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[DeletionResult]:
    """Apply the configured public-conversation retention policy across every account.

    The account identifiers are discovered from already-expired rows, so an idle tenant does not
    create work. Each deletion retains the same tenant-scoped row lock, file cleanup, and
    content-free audit outcome used by explicit visitor/professional deletion.
    """

    effective_now = now or utcnow()
    cutoff = effective_now - timedelta(days=settings.conversation_retention_days)
    account_ids = list(
        db.scalars(
            select(Conversation.account_id)
            .where(
                Conversation.kind == "public",
                Conversation.last_message_at < cutoff,
            )
            .distinct()
        ).all()
    )
    results: list[DeletionResult] = []
    for account_id in account_ids:
        results.extend(
            purge_expired_conversations(
                db,
                settings,
                account_id=account_id,
                now=effective_now,
            )
        )
    return results


def discard_stale_transcription_reservations(
    db: Session,
    *,
    now: datetime | None = None,
    account_id: str | None = None,
    conversation_id: str | None = None,
    commit: bool = True,
) -> int:
    """Release audio attachment slots left by cancellation or process loss.

    Raw audio is never stored in the backed-up upload tree. A stale ``transcribing`` row therefore
    represents only an unusable quota reservation. The account-level transcription-attempt event
    remains so cleanup cannot reset the rolling OpenAI-spend limit.
    """

    cutoff = (now or utcnow()) - STALE_TRANSCRIPTION_RESERVATION_TTL
    predicates = [
        Attachment.status == "transcribing",
        Attachment.created_at < cutoff,
    ]
    if account_id is not None:
        predicates.append(Attachment.account_id == account_id)
    if conversation_id is not None:
        predicates.append(Attachment.conversation_id == conversation_id)
    stale = list(db.scalars(select(Attachment).where(*predicates)).all())
    for attachment in stale:
        db.add(
            Event(
                account_id=attachment.account_id,
                space_id=attachment.space_id,
                conversation_id=attachment.conversation_id,
                actor_type="system",
                event_type="audio_transcription_reservation_expired",
                payload={"attachment_id": attachment.id},
            )
        )
        db.delete(attachment)
    if stale and commit:
        db.commit()
    return len(stale)


def discard_stale_unbound_attachments(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
    account_id: str | None = None,
    conversation_id: str | None = None,
    commit: bool = True,
) -> int:
    """Delete abandoned upload records without racing a visitor who is binding one.

    An upload is deliberately created before its message so the visitor can review a photograph
    or edit an audio transcript. Once that unbound record is an hour old, it is no longer a useful
    draft and must not occupy the 20-record or durable-byte quota forever. This also covers a bot
    or abandoned first interaction whose conversation has never become engaged.

    Candidate discovery is only advisory. Each conversation is locked and attachment state is
    re-read under that lock, matching the lock used by message binding. Image payloads are unlinked
    from the private upload tree before their row is deleted. Raw audio is never stored there, so
    stale audio cleanup deletes only the attachment row. Account-level transcription-attempt events
    are intentionally untouched.
    """

    cutoff = (now or utcnow()) - STALE_UNBOUND_ATTACHMENT_TTL
    predicates = [
        Attachment.message_id.is_(None),
        Attachment.status != "transcribing",
        Attachment.created_at < cutoff,
    ]
    if account_id is not None:
        predicates.append(Attachment.account_id == account_id)
    if conversation_id is not None:
        predicates.append(Attachment.conversation_id == conversation_id)
    candidates = list(
        db.execute(
            select(
                Attachment.id,
                Attachment.account_id,
                Attachment.space_id,
                Attachment.conversation_id,
            )
            .where(*predicates)
            .order_by(Attachment.conversation_id, Attachment.created_at, Attachment.id)
        ).all()
    )

    deleted_count = 0
    for candidate in candidates:
        conversation = db.scalar(
            select(Conversation)
            .where(
                Conversation.id == candidate.conversation_id,
                Conversation.account_id == candidate.account_id,
                Conversation.space_id == candidate.space_id,
                Conversation.kind == "public",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not conversation:
            continue

        attachment = db.scalar(
            select(Attachment)
            .where(
                Attachment.id == candidate.id,
                Attachment.account_id == conversation.account_id,
                Attachment.space_id == conversation.space_id,
                Attachment.conversation_id == conversation.id,
                Attachment.message_id.is_(None),
                Attachment.status != "transcribing",
                Attachment.created_at < cutoff,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not attachment:
            continue
        if attachment.media_type.startswith("image/"):
            target = _private_attachment_path(settings, attachment.storage_key)
            if target.exists():
                if not target.is_file():
                    raise RuntimeError("Attachment target is not a regular file")
                target.unlink()
        elif not attachment.media_type.startswith("audio/"):
            # Unknown future media needs an explicit lifecycle rather than accidental deletion.
            continue
        db.delete(attachment)
        deleted_count += 1

    if deleted_count and commit:
        db.commit()
    return deleted_count
