from __future__ import annotations

import asyncio
import json
from weakref import WeakValueDictionary

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..config import Settings
from ..conversations import active_revision, list_memories, list_messages, serialize_messages
from ..database import get_db
from ..dependencies import ProfessionalContext, current_professional, professional_space, runtime_settings
from ..models import (
    ConfigRevision,
    Conversation,
    Event,
    Member,
    MemoryItem,
    Message,
    ProfessionalEmail,
    Space,
    utcnow,
)
from ..retention import delete_conversation_data, purge_expired_conversations
from ..schemas import (
    MAX_CONFIGURATION_DOCUMENT_BYTES,
    AutoReplyUpdate,
    ConversationDetail,
    ConversationOut,
    MemoryOut,
    MemoryUpdate,
    MessageCreate,
    ProfessionalEmailOut,
    RevisionCreate,
    RevisionOut,
    SpaceDetail,
    SpaceOut,
    StudioTurnOut,
)

router = APIRouter(prefix="/studio", tags=["studio"])

# The production API runs one Uvicorn worker. Serializing a retried Studio attempt prevents
# two model calls in that worker; the persisted reply link also lets a fresh worker resume a
# professional message that survived a cancelled request.
_studio_turn_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


def _studio_turn_lock(account_id: str, conversation_id: str) -> asyncio.Lock:
    key = f"{account_id}:{conversation_id}"
    lock = _studio_turn_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _studio_turn_locks[key] = lock
    return lock


def _require_text_only_message(body: MessageCreate) -> None:
    if body.attachment_id or not body.content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="In questo spazio è supportato soltanto un messaggio di testo",
        )


def _studio_conversation(db: Session, account_id: str, space_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.account_id == account_id,
            Conversation.space_id == space_id,
            Conversation.kind == "studio",
        )
    )
    if not conversation:
        conversation = Conversation(
            account_id=account_id,
            space_id=space_id,
            kind="studio",
            title="Il tuo Studio",
        )
        db.add(conversation)
        db.commit()
    return conversation


def _latest_draft(db: Session, account_id: str, space_id: str) -> ConfigRevision | None:
    return db.scalar(
        select(ConfigRevision)
        .where(
            ConfigRevision.account_id == account_id,
            ConfigRevision.space_id == space_id,
            ConfigRevision.status == "draft",
        )
        .order_by(ConfigRevision.revision_number.desc())
        .limit(1)
    )


def _latest_email(db: Session, account_id: str, space_id: str) -> ProfessionalEmail | None:
    return db.scalar(
        select(ProfessionalEmail)
        .where(
            ProfessionalEmail.account_id == account_id,
            ProfessionalEmail.space_id == space_id,
            ProfessionalEmail.direction == "outbound",
        )
        .order_by(ProfessionalEmail.created_at.desc())
        .limit(1)
    )


def _owned_public_conversation(
    db: Session, context: ProfessionalContext, conversation_id: str
) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.account_id == context.account_id,
            Conversation.kind == "public",
        )
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    return conversation


def _professional_detail(db: Session, settings: Settings, conversation: Conversation) -> dict:
    messages = list_messages(
        db, account_id=conversation.account_id, conversation_id=conversation.id
    )
    memories = list_memories(
        db, account_id=conversation.account_id, conversation_id=conversation.id
    )
    signals = [
        (item.corrected_content or item.content)
        for item in memories
        if item.status != "dismissed" and item.kind in {"signal", "suggested_action"}
    ]
    summaries = [
        (item.corrected_content or item.content)
        for item in memories
        if item.status != "dismissed" and item.kind == "summary"
    ]
    return {
        "conversation": ConversationOut.model_validate(conversation),
        "messages": serialize_messages(
            db,
            settings,
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            messages=messages,
        ),
        "memory_items": [MemoryOut.model_validate(item) for item in memories],
        "attention_reason": signals[0] if signals else None,
        "summary": summaries[0] if summaries else None,
        "professional_present": conversation.professional_joined,
        "automatic_replies_enabled": conversation.automatic_ai_enabled,
    }


@router.get("/space", response_model=SpaceDetail)
def get_space(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> SpaceDetail:
    space = professional_space(db, context)
    active = active_revision(db, space)
    draft = _latest_draft(db, context.account_id, space.id)
    return SpaceDetail(
        space=SpaceOut.model_validate(space),
        active_revision=RevisionOut.model_validate(active) if active else None,
        latest_draft=RevisionOut.model_validate(draft) if draft else None,
    )


@router.get("/config/revisions", response_model=list[RevisionOut])
def list_revisions(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> list[RevisionOut]:
    space = professional_space(db, context)
    revisions = db.scalars(
        select(ConfigRevision)
        .where(
            ConfigRevision.account_id == context.account_id,
            ConfigRevision.space_id == space.id,
        )
        .order_by(ConfigRevision.revision_number.desc())
    ).all()
    return [RevisionOut.model_validate(item) for item in revisions]


@router.post("/config/revisions", response_model=RevisionOut, status_code=201)
def create_revision(
    body: RevisionCreate,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> RevisionOut:
    document = body.document.model_dump(mode="json")
    document_bytes = len(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    if document_bytes > MAX_CONFIGURATION_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Configurazione troppo grande",
        )
    authorized_space = professional_space(db, context)
    space = db.scalar(
        select(Space)
        .where(
            Space.id == authorized_space.id,
            Space.account_id == context.account_id,
        )
        .with_for_update()
    )
    if not space:
        raise HTTPException(status_code=404, detail="Spazio non trovato")
    latest = db.scalar(
        select(func.max(ConfigRevision.revision_number)).where(
            ConfigRevision.account_id == context.account_id,
            ConfigRevision.space_id == space.id,
        )
    )
    revision = ConfigRevision(
        account_id=context.account_id,
        space_id=space.id,
        revision_number=(latest or 0) + 1,
        status="draft",
        document=document,
        rationale=body.rationale,
        proposed_by_member_id=context.member.id,
    )
    db.add(revision)
    db.flush()
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="configuration_revision_proposed",
            payload={"revision_id": revision.id, "revision_number": revision.revision_number},
        )
    )
    db.commit()
    return RevisionOut.model_validate(revision)


@router.post("/config/revisions/{revision_id}/activate", response_model=RevisionOut)
def activate_revision(
    revision_id: str,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> RevisionOut:
    authorized_space = professional_space(db, context)
    space = db.scalar(
        select(Space)
        .where(
            Space.id == authorized_space.id,
            Space.account_id == context.account_id,
        )
        .with_for_update()
    )
    if not space:
        raise HTTPException(status_code=404, detail="Spazio non trovato")
    target = db.scalar(
        select(ConfigRevision).where(
            ConfigRevision.id == revision_id,
            ConfigRevision.account_id == context.account_id,
            ConfigRevision.space_id == space.id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Revisione non trovata")
    current = active_revision(db, space)
    if current and current.id != target.id:
        current.status = "historical"
    target.status = "active"
    target.activated_by_member_id = context.member.id
    target.activated_at = utcnow()
    space.active_revision_id = target.id
    identity = target.document.get("identity", {})
    space.professional_name = identity.get("name", space.professional_name)
    space.agency = identity.get("agency")
    space.territory = identity.get("territory")
    space.public_role = identity.get("role", space.public_role)
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="configuration_revision_activated",
            payload={
                "revision_id": target.id,
                "revision_number": target.revision_number,
                "previous_revision_id": current.id if current else None,
            },
        )
    )
    studio = _studio_conversation(db, context.account_id, space.id)
    db.add(
        Message(
            account_id=context.account_id,
            conversation_id=studio.id,
            author_type="system",
            author_label="LAGGENTE",
            content=f"La revisione {target.revision_number} è ora attiva nello spazio pubblico.",
        )
    )
    db.commit()
    return RevisionOut.model_validate(target)


@router.get("/messages", response_model=ConversationDetail)
def get_studio_messages(
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> ConversationDetail:
    space = professional_space(db, context)
    conversation = _studio_conversation(db, context.account_id, space.id)
    messages = list_messages(db, account_id=context.account_id, conversation_id=conversation.id)
    latest_email = _latest_email(db, context.account_id, space.id)
    return ConversationDetail(
        conversation=ConversationOut.model_validate(conversation),
        messages=serialize_messages(
            db,
            settings,
            account_id=context.account_id,
            conversation_id=conversation.id,
            messages=messages,
        ),
        memories=[],
        latest_email=(
            ProfessionalEmailOut.model_validate(latest_email) if latest_email else None
        ),
    )


@router.post("/messages", response_model=StudioTurnOut)
async def post_studio_message(
    body: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> StudioTurnOut:
    _require_text_only_message(body)
    request.app.state.rate_limiter.check(
        f"studio-message:{context.member.id}", limit=30, window_seconds=60
    )
    space = professional_space(db, context)
    conversation = _studio_conversation(db, context.account_id, space.id)
    account_id = context.account_id
    member_id = context.member.id
    space_id = space.id
    conversation_id = conversation.id
    # End the dependency/authentication transaction before awaiting the Studio turn lock. The
    # authorization boundary is re-read inside the lock so queued requests do not pin connections.
    db.commit()
    async with _studio_turn_lock(account_id, conversation_id):
        db.expire_all()
        member = db.scalar(
            select(Member).where(
                Member.id == member_id,
                Member.account_id == account_id,
                Member.is_active.is_(True),
            )
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Accesso richiesto")
        space = db.scalar(
            select(Space).where(Space.id == space_id, Space.account_id == account_id)
        )
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.account_id == account_id,
                Conversation.space_id == space_id,
                Conversation.kind == "studio",
            )
        )
        if not space or not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Studio non trovato")
        professional_message = None
        if body.client_message_id:
            professional_message = db.scalar(
                select(Message).where(
                    Message.account_id == context.account_id,
                    Message.conversation_id == conversation.id,
                    Message.client_message_id == body.client_message_id,
                )
            )
            if professional_message:
                existing_reply = db.scalar(
                    select(Message).where(
                        Message.account_id == context.account_id,
                        Message.conversation_id == conversation.id,
                        Message.reply_to_message_id == professional_message.id,
                    )
                )
                if existing_reply:
                    existing_email = db.scalar(
                        select(ProfessionalEmail)
                        .where(
                            ProfessionalEmail.account_id == context.account_id,
                            ProfessionalEmail.space_id == space.id,
                            ProfessionalEmail.source_message_id == professional_message.id,
                        )
                        .order_by(ProfessionalEmail.created_at.desc())
                        .limit(1)
                    )
                    return StudioTurnOut(
                        conversation=ConversationOut.model_validate(conversation),
                        messages=serialize_messages(
                            db,
                            settings,
                            account_id=context.account_id,
                            conversation_id=conversation.id,
                            messages=[professional_message, existing_reply],
                        ),
                        proposed_email=(
                            ProfessionalEmailOut.model_validate(existing_email)
                            if existing_email
                            else None
                        ),
                    )
        if professional_message is None:
            professional_message = Message(
                account_id=context.account_id,
                conversation_id=conversation.id,
                author_type="professional",
                author_label=f"{context.member.display_name} — agente immobiliare",
                content=body.content,
                client_message_id=body.client_message_id,
                assistant_reply_state="pending",
            )
            db.add(professional_message)
            conversation.last_message_at = utcnow()
            db.commit()

        history = list_messages(db, account_id=context.account_id, conversation_id=conversation.id)
        # No synchronous DB connection may remain checked out while the model is running.
        db.commit()
        proposed_revision = None
        proposed_email = None
        try:
            reply = await request.app.state.assistant_service.studio_turn(
                db,
                account_id=context.account_id,
                space_id=space.id,
                member_id=context.member.id,
                messages=history,
            )
            reply_text = reply.text
            response_id = reply.response_id
            if reply.proposed_revision_id:
                proposed_revision = db.scalar(
                    select(ConfigRevision).where(
                        ConfigRevision.id == reply.proposed_revision_id,
                        ConfigRevision.account_id == context.account_id,
                        ConfigRevision.space_id == space.id,
                    )
                )
            if reply.proposed_email_id:
                proposed_email = db.scalar(
                    select(ProfessionalEmail).where(
                        ProfessionalEmail.id == reply.proposed_email_id,
                        ProfessionalEmail.account_id == context.account_id,
                        ProfessionalEmail.space_id == space.id,
                    )
                )
        except Exception as exc:
            db.rollback()
            reply_text = (
                "Ho conservato il tuo messaggio, ma in questo momento non riesco a elaborarlo. "
                "Riprova tra poco: nessuna configurazione pubblica è stata cambiata."
            )
            response_id = None
            db.add(
                Event(
                    account_id=context.account_id,
                    space_id=space.id,
                    conversation_id=conversation.id,
                    actor_type="system",
                    event_type="studio_assistant_failed",
                    payload={"error_type": type(exc).__name__},
                )
            )
        assistant_message = Message(
            account_id=context.account_id,
            conversation_id=conversation.id,
            author_type="studio_assistant",
            author_label="Studio — assistente AI",
            content=reply_text,
            model_response_id=response_id,
            reply_to_message_id=professional_message.id,
        )
        db.add(assistant_message)
        professional_message.assistant_reply_state = "completed"
        conversation.last_message_at = utcnow()
        db.commit()
        return StudioTurnOut(
            conversation=ConversationOut.model_validate(conversation),
            messages=serialize_messages(
                db,
                settings,
                account_id=context.account_id,
                conversation_id=conversation.id,
                messages=[professional_message, assistant_message],
            ),
            proposed_revision=(
                RevisionOut.model_validate(proposed_revision) if proposed_revision else None
            ),
            proposed_email=(
                ProfessionalEmailOut.model_validate(proposed_email) if proposed_email else None
            ),
        )


@router.get("/conversations")
def list_public_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
):
    total = int(
        db.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.account_id == context.account_id,
                Conversation.kind == "public",
            )
        )
        or 0
    )
    items = db.scalars(
        select(Conversation)
        .where(
            Conversation.account_id == context.account_id,
            Conversation.kind == "public",
        )
        .order_by(Conversation.last_message_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    result = []
    for item in items:
        messages = list_messages(db, account_id=context.account_id, conversation_id=item.id)
        memories = list_memories(db, account_id=context.account_id, conversation_id=item.id)
        summary = next(
            (
                memory.corrected_content or memory.content
                for memory in memories
                if memory.status != "dismissed" and memory.kind == "summary"
            ),
            None,
        )
        attention_reason = next(
            (
                memory.corrected_content or memory.content
                for memory in memories
                if memory.status != "dismissed"
                and memory.kind in {"signal", "suggested_action"}
            ),
            None,
        )
        result.append(
            {
                "conversation": ConversationOut.model_validate(item),
                "summary": summary,
                "attention_reason": attention_reason,
                "last_message": (
                    serialize_messages(
                        db,
                        settings,
                        account_id=context.account_id,
                        conversation_id=item.id,
                        messages=[messages[-1]],
                    )[0]
                    if messages
                    else None
                ),
            }
        )
    next_offset = offset + len(result)
    return {
        "items": result,
        "total": total,
        "next_offset": next_offset if next_offset < total else None,
    }


@router.get("/conversations/{conversation_id}")
def get_professional_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
):
    return _professional_detail(
        db, settings, _owned_public_conversation(db, context, conversation_id)
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_professional_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> None:
    conversation = _owned_public_conversation(db, context, conversation_id)
    delete_conversation_data(
        db,
        settings,
        conversation=conversation,
        actor_type="professional",
        actor_id=context.member.id,
        trigger="professional_request",
    )


@router.post("/retention/purge")
def purge_retained_conversations(
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
):
    deleted = purge_expired_conversations(
        db,
        settings,
        account_id=context.account_id,
    )
    return {
        "deleted": len(deleted),
        "retention_days": settings.conversation_retention_days,
        "conversation_refs": [item.conversation_ref for item in deleted],
    }


@router.post("/conversations/{conversation_id}/join")
def join_professional_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
):
    conversation = _owned_public_conversation(db, context, conversation_id)
    if not conversation.professional_joined:
        conversation.professional_joined = True
        db.add(
            Message(
                account_id=context.account_id,
                conversation_id=conversation.id,
                author_type="system",
                author_label="LAGGENTE",
                content=f"{context.member.display_name} è entrato nella conversazione.",
            )
        )
        db.add(
            Event(
                account_id=context.account_id,
                space_id=conversation.space_id,
                conversation_id=conversation.id,
                actor_type="professional",
                actor_id=context.member.id,
                event_type="professional_joined_conversation",
                payload={"automatic_ai_enabled": conversation.automatic_ai_enabled},
            )
        )
        db.commit()
    return _professional_detail(db, settings, conversation)


@router.post("/conversations/{conversation_id}/messages")
def post_professional_message(
    conversation_id: str,
    body: MessageCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
):
    _require_text_only_message(body)
    conversation = _owned_public_conversation(db, context, conversation_id)
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation.id,
            Conversation.account_id == context.account_id,
            Conversation.kind == "public",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    if body.client_message_id:
        existing = db.scalar(
            select(Message).where(
                Message.account_id == context.account_id,
                Message.conversation_id == conversation.id,
                Message.client_message_id == body.client_message_id,
                Message.author_type == "professional",
            )
        )
        if existing:
            return _professional_detail(db, settings, conversation)
    first_join = not conversation.professional_joined
    conversation.professional_joined = True
    was_enabled = conversation.automatic_ai_enabled
    conversation.automatic_ai_enabled = False
    if first_join:
        db.add(
            Message(
                account_id=context.account_id,
                conversation_id=conversation.id,
                author_type="system",
                author_label="LAGGENTE",
                content=f"{context.member.display_name} è entrato nella conversazione.",
            )
        )
    message = Message(
        account_id=context.account_id,
        conversation_id=conversation.id,
        author_type="professional",
        author_label=f"{context.member.display_name} — agente immobiliare",
        content=body.content,
        client_message_id=body.client_message_id,
    )
    db.add(message)
    conversation.last_message_at = utcnow()
    db.add(
        Event(
            account_id=context.account_id,
            space_id=conversation.space_id,
            conversation_id=conversation.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="professional_message_sent",
            payload={"automatic_ai_paused": was_enabled},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if body.client_message_id:
            existing = db.scalar(
                select(Message).where(
                    Message.account_id == context.account_id,
                    Message.conversation_id == conversation_id,
                    Message.client_message_id == body.client_message_id,
                    Message.author_type == "professional",
                )
            )
            if existing:
                return _professional_detail(
                    db,
                    settings,
                    _owned_public_conversation(db, context, conversation_id),
                )
        raise
    return _professional_detail(db, settings, conversation)


@router.post("/conversations/{conversation_id}/assistant-control", response_model=ConversationOut)
def update_assistant_control(
    conversation_id: str,
    body: AutoReplyUpdate,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> ConversationOut:
    conversation = _owned_public_conversation(db, context, conversation_id)
    conversation.automatic_ai_enabled = body.enabled
    db.add(
        Event(
            account_id=context.account_id,
            space_id=conversation.space_id,
            conversation_id=conversation.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="automatic_ai_control_changed",
            payload={"enabled": body.enabled},
        )
    )
    db.add(
        Message(
            account_id=context.account_id,
            conversation_id=conversation.id,
            author_type="system",
            author_label="LAGGENTE",
            content=(
                "Le risposte automatiche dell'assistente AI sono state riattivate."
                if body.enabled
                else "Le risposte automatiche dell'assistente AI sono in pausa."
            ),
        )
    )
    db.commit()
    return ConversationOut.model_validate(conversation)


@router.patch("/conversations/{conversation_id}/memory/{memory_id}", response_model=MemoryOut)
def correct_memory(
    conversation_id: str,
    memory_id: str,
    body: MemoryUpdate,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> MemoryOut:
    conversation = _owned_public_conversation(db, context, conversation_id)
    memory = db.scalar(
        select(MemoryItem).where(
            MemoryItem.id == memory_id,
            MemoryItem.account_id == context.account_id,
            MemoryItem.conversation_id == conversation.id,
            MemoryItem.space_id == conversation.space_id,
        )
    )
    if not memory:
        raise HTTPException(status_code=404, detail="Memoria non trovata")
    memory.status = body.status
    memory.corrected_content = body.corrected_content
    memory.corrected_by_member_id = context.member.id
    db.add(
        Event(
            account_id=context.account_id,
            space_id=conversation.space_id,
            conversation_id=conversation.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="memory_item_corrected",
            payload={"memory_item_id": memory.id, "status": memory.status},
        )
    )
    db.commit()
    return MemoryOut.model_validate(memory)
