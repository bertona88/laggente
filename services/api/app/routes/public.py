from __future__ import annotations

import asyncio
from datetime import timedelta
from weakref import WeakValueDictionary

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..conversations import active_revision, generate_public_reply, list_messages, serialize_messages
from ..database import get_db
from ..dependencies import authorize_public_conversation, conversation_token, runtime_settings
from ..models import Attachment, Conversation, Event, Message, Space, utcnow
from ..rate_limit import client_ip
from ..retention import delete_conversation_data
from ..schemas import (
    ConversationDetail,
    ConversationOut,
    MessageCreate,
    PublicConversationCreate,
    PublicConversationCreated,
    PublicSpaceOut,
    PublicTurnOut,
)
from ..security import hash_token, new_opaque_token
from ..tenant import require_public_space_host, resolve_public_space, slug_from_host

router = APIRouter(prefix="/public", tags=["public"])

_public_turn_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
MAX_UNENGAGED_CONVERSATIONS_PER_SPACE = 60
UNENGAGED_CONVERSATION_TTL = timedelta(hours=1)
PUBLIC_MODEL_TURNS_PER_SPACE_PER_HOUR = 60


def _public_turn_lock(account_id: str, conversation_id: str) -> asyncio.Lock:
    key = f"{account_id}:{conversation_id}"
    lock = _public_turn_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _public_turn_locks[key] = lock
    return lock


def _set_visitor_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.visitor_cookie_name,
        token,
        max_age=settings.conversation_retention_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        # __Host- cookies require Path=/; cookies remain host-only because no Domain is set.
        path="/",
    )


def _prune_and_bound_unengaged_conversations(
    db: Session, settings: Settings, space: Space
) -> None:
    has_human_message = (
        select(Message.id)
        .where(
            Message.account_id == space.account_id,
            Message.conversation_id == Conversation.id,
            Message.author_type.in_(["visitor", "professional"]),
        )
        .exists()
    )
    has_attachment = (
        select(Attachment.id)
        .where(
            Attachment.account_id == space.account_id,
            Attachment.conversation_id == Conversation.id,
            Attachment.message_id.is_not(None),
        )
        .exists()
    )
    base = (
        Conversation.account_id == space.account_id,
        Conversation.space_id == space.id,
        Conversation.kind == "public",
        Conversation.professional_joined.is_(False),
        ~has_human_message,
        ~has_attachment,
    )
    stale_cutoff = utcnow() - UNENGAGED_CONVERSATION_TTL
    stale = db.scalars(
        select(Conversation)
        .where(*base, Conversation.created_at < stale_cutoff)
        .order_by(Conversation.created_at)
        .limit(MAX_UNENGAGED_CONVERSATIONS_PER_SPACE)
    ).all()
    for conversation in stale:
        delete_conversation_data(
            db,
            settings,
            conversation=conversation,
            actor_type="system",
            actor_id=None,
            trigger="unengaged_expired",
            only_if_created_before=stale_cutoff,
            only_if_unengaged=True,
        )
    if stale:
        db.commit()
    count = db.scalar(select(func.count(Conversation.id)).where(*base))
    if int(count or 0) >= MAX_UNENGAGED_CONVERSATIONS_PER_SPACE:
        raise HTTPException(
            status_code=429,
            detail="Troppe conversazioni non ancora iniziate. Riprova più tardi.",
        )


def _public_space_output(db: Session, space: Space, settings: Settings) -> PublicSpaceOut:
    revision = active_revision(db, space)
    if not revision:
        raise HTTPException(status_code=404, detail="Spazio non trovato")
    document = revision.document
    identity = document.get("identity", {})
    public_projection = {
        "schema_version": document.get("schema_version", 1),
        "locale": document.get("locale", "it-IT"),
        "identity": {
            key: identity.get(key)
            for key in ("name", "role", "agency", "territory")
            if identity.get(key) is not None
        },
        "public": document.get("public", {}),
        "capabilities": document.get("capabilities", {"text": True}),
    }
    return PublicSpaceOut(
        slug=space.slug,
        professional_name=space.professional_name,
        agency=space.agency,
        territory=space.territory,
        public_role=space.public_role,
        locale=space.locale,
        ai_label=f"LAGGENTE — assistente AI di {space.professional_name}",
        privacy_notice_version=settings.privacy_notice_version,
        configuration=public_projection,
    )


@router.get("/resolve", response_model=PublicSpaceOut)
def resolve_space_from_host(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> PublicSpaceOut:
    """Resolve a production tenant hostname; hostname remains routing input, never authorization."""
    return _public_space_output(
        db, resolve_public_space(db, slug_from_host(request, settings)), settings
    )


@router.post("/resolve/conversations", response_model=PublicConversationCreated)
async def create_public_conversation_from_host(
    body: PublicConversationCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> PublicConversationCreated:
    return await create_public_conversation(
        slug_from_host(request, settings), body, request, response, db, settings
    )


@router.get("/{slug}", response_model=PublicSpaceOut)
def get_public_space(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> PublicSpaceOut:
    space = resolve_public_space(db, slug)
    require_public_space_host(request, settings, space)
    return _public_space_output(db, space, settings)


@router.post("/{slug}/conversations", response_model=PublicConversationCreated)
async def create_public_conversation(
    slug: str,
    body: PublicConversationCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> PublicConversationCreated:
    request.app.state.rate_limiter.check(
        f"new-conversation:{client_ip(request)}", limit=12, window_seconds=60 * 60
    )
    space = resolve_public_space(db, slug)
    require_public_space_host(request, settings, space)
    request.app.state.rate_limiter.check(
        f"new-conversation-space:{space.id}", limit=60, window_seconds=60 * 60
    )
    _prune_and_bound_unengaged_conversations(db, settings, space)
    token = new_opaque_token()
    conversation = Conversation(
        account_id=space.account_id,
        space_id=space.id,
        kind="public",
        visitor_token_hash=hash_token(token),
        title="Nuova conversazione",
    )
    db.add(conversation)
    db.flush()
    revision = active_revision(db, space)
    if not revision:
        raise HTTPException(status_code=404, detail="Spazio non trovato")
    configured_welcome = str(revision.document.get("public", {}).get("welcome", "")).strip()
    disclosure = Message(
        account_id=space.account_id,
        conversation_id=conversation.id,
        author_type="public_assistant",
        author_label=f"LAGGENTE — assistente AI di {space.professional_name}",
        # The active welcome is configurable; the author label and surrounding public surface keep
        # the platform-owned AI identity explicit and cannot be overridden by tenant configuration.
        content=configured_welcome,
    )
    db.add(disclosure)
    db.add(
        Event(
            account_id=space.account_id,
            space_id=space.id,
            conversation_id=conversation.id,
            actor_type="visitor",
            event_type="public_conversation_created",
            payload={"ai_disclosure_shown": True},
        )
    )
    acknowledgement_recorded = (
        body.privacy_notice_acknowledged
        and body.privacy_notice_version == settings.privacy_notice_version
    )
    db.add(
        Event(
            account_id=space.account_id,
            space_id=space.id,
            conversation_id=conversation.id,
            actor_type="visitor",
            event_type=(
                "privacy_notice_acknowledged"
                if acknowledgement_recorded
                else "privacy_notice_presented"
            ),
            payload={
                "notice_version": settings.privacy_notice_version,
                "submitted_version": body.privacy_notice_version,
                "acknowledgement_recorded": acknowledgement_recorded,
                "event_scope": "privacy_notice_receipt_only_not_marketing_consent",
            },
        )
    )
    db.commit()
    _set_visitor_cookie(response, settings, token)
    messages = list_messages(db, account_id=space.account_id, conversation_id=conversation.id)
    return PublicConversationCreated(
        conversation=ConversationOut.model_validate(conversation),
        messages=serialize_messages(
            db,
            settings,
            account_id=space.account_id,
            conversation_id=conversation.id,
            messages=messages,
        ),
        continuation_token=token,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_public_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> ConversationDetail:
    conversation = authorize_public_conversation(request, db, conversation_id)
    token = conversation_token(request)
    if token:
        _set_visitor_cookie(response, settings, token)
    messages = list_messages(
        db, account_id=conversation.account_id, conversation_id=conversation.id
    )
    return ConversationDetail(
        conversation=ConversationOut.model_validate(conversation),
        messages=serialize_messages(
            db,
            settings,
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            messages=messages,
        ),
        memories=[],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_public_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> None:
    conversation = authorize_public_conversation(
        request, db, conversation_id, require_active_space=False
    )
    delete_conversation_data(
        db,
        settings,
        conversation=conversation,
        actor_type="visitor",
        actor_id=None,
        trigger="visitor_request",
    )
    response.delete_cookie(
        settings.visitor_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/conversations/{conversation_id}/messages", response_model=PublicTurnOut)
async def post_public_message(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> PublicTurnOut:
    request.app.state.rate_limiter.check(
        f"public-message-ip:{client_ip(request)}", limit=12, window_seconds=60
    )
    conversation = authorize_public_conversation(request, db, conversation_id)
    token = conversation_token(request)
    if token:
        _set_visitor_cookie(response, settings, token)
    request.app.state.rate_limiter.check(
        f"public-message-conversation:{conversation.id}", limit=30, window_seconds=60 * 60
    )
    request.app.state.rate_limiter.check(
        f"public-message-space:{conversation.space_id}", limit=600, window_seconds=60 * 60
    )
    lock_account_id = conversation.account_id
    lock_conversation_id = conversation.id
    # Authorization performs synchronous SQL reads. End that transaction before awaiting the
    # per-conversation lock so queued requests cannot occupy the whole connection pool while the
    # request holding the lock is waiting on the model.
    db.commit()
    async with _public_turn_lock(lock_account_id, lock_conversation_id):
        db.expire_all()
        conversation = authorize_public_conversation(request, db, conversation_id)
        conversation = db.scalar(
            select(Conversation)
            .where(
                Conversation.id == conversation.id,
                Conversation.account_id == conversation.account_id,
                Conversation.space_id == conversation.space_id,
                Conversation.kind == "public",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversazione non trovata")
        visitor_message = None
        if body.client_message_id:
            visitor_message = db.scalar(
                select(Message).where(
                    Message.account_id == conversation.account_id,
                    Message.conversation_id == conversation.id,
                    Message.client_message_id == body.client_message_id,
                )
            )
            if visitor_message:
                existing_reply = db.scalar(
                    select(Message).where(
                        Message.account_id == conversation.account_id,
                        Message.conversation_id == conversation.id,
                        Message.reply_to_message_id == visitor_message.id,
                    )
                )
                if existing_reply:
                    return PublicTurnOut(
                        conversation=ConversationOut.model_validate(conversation),
                        messages=serialize_messages(
                            db,
                            settings,
                            account_id=conversation.account_id,
                            conversation_id=conversation.id,
                            messages=[visitor_message, existing_reply],
                        ),
                        # The linked reply is replayed, not generated by this HTTP request.
                        automatic_reply_generated=False,
                    )

        if visitor_message is None:
            attachment = None
            if body.attachment_id:
                attachment = db.scalar(
                    select(Attachment).where(
                        Attachment.id == body.attachment_id,
                        Attachment.account_id == conversation.account_id,
                        Attachment.space_id == conversation.space_id,
                        Attachment.conversation_id == conversation.id,
                        Attachment.message_id.is_(None),
                        Attachment.status.in_(["available", "transcribed"]),
                    )
                )
                if not attachment:
                    raise HTTPException(status_code=404, detail="Allegato non trovato")
            message_content = body.content
            if not message_content and attachment:
                message_content = (
                    attachment.transcript
                    if attachment.transcript
                    else "[La persona ha condiviso una fotografia privata.]"
                )
            if conversation.automatic_ai_enabled:
                request.app.state.rate_limiter.check(
                    f"public-model-space:{conversation.space_id}",
                    limit=PUBLIC_MODEL_TURNS_PER_SPACE_PER_HOUR,
                    window_seconds=60 * 60,
                )
            visitor_message = Message(
                account_id=conversation.account_id,
                conversation_id=conversation.id,
                author_type="visitor",
                author_label="Tu",
                content=message_content,
                content_type="audio_transcript" if attachment and attachment.transcript else "text",
                client_message_id=body.client_message_id,
                assistant_reply_state=(
                    "pending" if conversation.automatic_ai_enabled else "not_requested"
                ),
            )
            db.add(visitor_message)
            db.flush()
            if attachment:
                attachment.message_id = visitor_message.id
                if attachment.transcript:
                    # The visitor edits the generated transcript before sending. Keep only that
                    # corrected, inspectable text instead of retaining a stale hidden interpretation.
                    attachment.transcript = message_content
            conversation.last_message_at = utcnow()
            if not conversation.title or conversation.title == "Nuova conversazione":
                conversation.title = message_content[:120]
            db.commit()

        new_messages = [visitor_message]
        generated = False
        reply_is_final = visitor_message.assistant_reply_state in {
            "not_requested",
            "suppressed",
        }
        if conversation.automatic_ai_enabled and not reply_is_final:
            space = db.scalar(
                select(Space).where(
                    Space.id == conversation.space_id,
                    Space.account_id == conversation.account_id,
                    Space.slug_claimed.is_(True),
                    Space.onboarding_state == "published",
                    Space.is_active.is_(True),
                )
            )
            if not space:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Spazio non trovato"
                )
            reply = await generate_public_reply(
                db,
                request.app.state.assistant_service,
                conversation=conversation,
                space=space,
                trigger_message=visitor_message,
            )
            if reply:
                new_messages.append(reply)
                generated = True
        elif not reply_is_final:
            visitor_message.assistant_reply_state = "suppressed"
            db.commit()
        return PublicTurnOut(
            conversation=ConversationOut.model_validate(conversation),
            messages=serialize_messages(
                db,
                settings,
                account_id=conversation.account_id,
                conversation_id=conversation.id,
                messages=new_messages,
            ),
            automatic_reply_generated=generated,
        )
