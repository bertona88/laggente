from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .assistants import AssistantService, AssistantUnavailable, PublicImageInput
from .config import Settings
from .media import ALLOWED_MEDIA_TYPES, attachment_content_url
from .models import Attachment, ConfigRevision, Conversation, Event, MemoryItem, Message, Space, utcnow
from .schemas import MessageAttachmentOut, MessageOut, PublicAgentOutput


def list_messages(db: Session, *, account_id: str, conversation_id: str) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(
                Message.account_id == account_id,
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.created_at, Message.id)
        ).all()
    )


def list_public_image_inputs(
    db: Session,
    *,
    account_id: str,
    space_id: str,
    conversation_id: str,
    messages: list[Message],
) -> list[PublicImageInput]:
    visitor_message_ids = [
        message.id for message in messages[-40:] if message.author_type == "visitor"
    ]
    if not visitor_message_ids:
        return []
    image_media_types = [
        media_type
        for media_type, (kind, _) in ALLOWED_MEDIA_TYPES.items()
        if kind == "image"
    ]
    attachments = db.scalars(
        select(Attachment)
        .where(
            Attachment.account_id == account_id,
            Attachment.space_id == space_id,
            Attachment.conversation_id == conversation_id,
            Attachment.message_id.in_(visitor_message_ids),
            Attachment.uploader_type == "visitor",
            Attachment.status == "available",
            Attachment.media_type.in_(image_media_types),
        )
        .order_by(Attachment.created_at, Attachment.id)
    ).all()
    result: list[PublicImageInput] = []
    seen_message_ids: set[str] = set()
    for attachment in attachments:
        if not attachment.message_id or attachment.message_id in seen_message_ids:
            continue
        seen_message_ids.add(attachment.message_id)
        result.append(
            PublicImageInput(
                message_id=attachment.message_id,
                media_type=attachment.media_type,
                storage_key=attachment.storage_key,
                size_bytes=attachment.size_bytes,
                sha256=attachment.sha256,
            )
        )
    return result


def serialize_messages(
    db: Session,
    settings: Settings,
    *,
    account_id: str,
    conversation_id: str,
    messages: list[Message] | None = None,
) -> list[MessageOut]:
    """Serialize messages with only account/conversation-scoped, public-safe media data.

    Images receive a stable same-origin URL whose endpoint re-authorizes every request. Raw
    audio is deliberately not projected: after transcription the original file is deleted and
    the transcript is the durable message content.
    """

    scoped_messages = messages
    if scoped_messages is None:
        scoped_messages = list_messages(
            db, account_id=account_id, conversation_id=conversation_id
        )
    if not scoped_messages:
        return []
    message_ids = [message.id for message in scoped_messages]
    attachments = db.scalars(
        select(Attachment)
        .where(
            Attachment.account_id == account_id,
            Attachment.conversation_id == conversation_id,
            Attachment.message_id.in_(message_ids),
            Attachment.status == "available",
            Attachment.media_type.in_(
                [media_type for media_type, (kind, _) in ALLOWED_MEDIA_TYPES.items() if kind == "image"]
            ),
        )
        .order_by(Attachment.created_at, Attachment.id)
    ).all()
    by_message: dict[str, Attachment] = {}
    for attachment in attachments:
        if attachment.message_id:
            by_message.setdefault(attachment.message_id, attachment)

    result: list[MessageOut] = []
    for message in scoped_messages:
        attachment = by_message.get(message.id)
        projection = None
        if attachment:
            projection = MessageAttachmentOut(
                id=attachment.id,
                kind="image",
                name=attachment.original_name,
                url=attachment_content_url(attachment),
            )
        result.append(
            MessageOut.model_validate(message).model_copy(update={"attachment": projection})
        )
    return result


def list_memories(db: Session, *, account_id: str, conversation_id: str) -> list[MemoryItem]:
    return list(
        db.scalars(
            select(MemoryItem)
            .where(
                MemoryItem.account_id == account_id,
                MemoryItem.conversation_id == conversation_id,
            )
            .order_by(MemoryItem.created_at.desc())
        ).all()
    )


def active_revision(db: Session, space: Space) -> ConfigRevision | None:
    if not space.active_revision_id:
        return None
    return db.scalar(
        select(ConfigRevision).where(
            ConfigRevision.id == space.active_revision_id,
            ConfigRevision.account_id == space.account_id,
            ConfigRevision.space_id == space.id,
            ConfigRevision.status == "active",
        )
    )


def persist_public_interpretations(
    db: Session,
    *,
    conversation: Conversation,
    output: PublicAgentOutput,
    fallback_source_id: str,
    valid_source_ids: set[str],
) -> None:
    summary_sources = [fallback_source_id] if fallback_source_id in valid_source_ids else []
    db.add(
        MemoryItem(
            account_id=conversation.account_id,
            space_id=conversation.space_id,
            conversation_id=conversation.id,
            kind="summary",
            content=output.summary,
            source_message_ids=summary_sources,
        )
    )
    for proposal in output.memory_items:
        sources = [item for item in proposal.source_message_ids if item in valid_source_ids]
        if not sources and fallback_source_id in valid_source_ids:
            sources = [fallback_source_id]
        db.add(
            MemoryItem(
                account_id=conversation.account_id,
                space_id=conversation.space_id,
                conversation_id=conversation.id,
                kind=proposal.kind,
                content=proposal.content,
                source_message_ids=sources,
            )
        )


async def generate_public_reply(
    db: Session,
    assistant: AssistantService,
    *,
    conversation: Conversation,
    space: Space,
    trigger_message: Message,
) -> Message | None:
    revision = active_revision(db, space)
    if not revision:
        raise AssistantUnavailable("No active configuration")
    history = list_messages(db, account_id=conversation.account_id, conversation_id=conversation.id)
    image_inputs = list_public_image_inputs(
        db,
        account_id=conversation.account_id,
        space_id=conversation.space_id,
        conversation_id=conversation.id,
        messages=history,
    )
    # Release the synchronous SQLAlchemy connection before the external model await. The
    # detached inputs remain usable because SessionLocal uses expire_on_commit=False.
    db.commit()
    try:
        result = await assistant.public_turn(
            account_id=conversation.account_id,
            space_id=space.id,
            professional_name=space.professional_name,
            configuration=revision.document,
            messages=history,
            image_inputs=image_inputs,
        )
        answer = result.output.answer
        response_id = result.response_id
        output = result.output
    except Exception as exc:
        answer = (
            "Grazie per il messaggio. In questo momento non riesco a rispondere come dovrei. "
            f"Ho comunque conservato la conversazione per {space.professional_name}; puoi riprovare "
            "tra poco o chiedere che intervenga direttamente."
        )
        response_id = None
        output = PublicAgentOutput(
            answer=answer,
            summary="La persona ha scritto; la risposta automatica non era temporaneamente disponibile.",
            memory_items=[],
        )
        db.add(
            Event(
                account_id=conversation.account_id,
                space_id=conversation.space_id,
                conversation_id=conversation.id,
                actor_type="system",
                event_type="public_assistant_failed",
                payload={"error_type": type(exc).__name__},
            )
        )
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
        raise AssistantUnavailable("Conversation disappeared before reply finalization")
    conversation = locked_conversation
    if not conversation.automatic_ai_enabled:
        trigger_message.assistant_reply_state = "suppressed"
        db.add(
            Event(
                account_id=conversation.account_id,
                space_id=conversation.space_id,
                conversation_id=conversation.id,
                actor_type="system",
                event_type="stale_public_assistant_reply_suppressed",
                payload={
                    "model_response_id": response_id,
                    "trigger_message_id": trigger_message.id,
                },
            )
        )
        db.commit()
        return None
    message = Message(
        account_id=conversation.account_id,
        conversation_id=conversation.id,
        author_type="public_assistant",
        author_label=f"LAGGENTE — assistente AI di {space.professional_name}",
        content=answer,
        model_response_id=response_id,
        reply_to_message_id=trigger_message.id,
    )
    db.add(message)
    db.flush()
    valid_source_ids = {item.id for item in history}
    persist_public_interpretations(
        db,
        conversation=conversation,
        output=output,
        fallback_source_id=trigger_message.id,
        valid_source_ids=valid_source_ids,
    )
    trigger_message.assistant_reply_state = "completed"
    conversation.last_message_at = utcnow()
    db.commit()
    return message
