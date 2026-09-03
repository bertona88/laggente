from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from weakref import WeakValueDictionary

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..conversations import active_revision, list_memories, list_messages, serialize_messages
from ..database import get_db
from ..documents import DocumentExtractionError, validate_knowledge_document_references
from ..dependencies import (
    ProfessionalContext,
    current_professional,
    professional_space,
    runtime_settings,
)
from ..media import (
    ALLOWED_MEDIA_TYPES,
    MAX_ACCOUNT_AUDIO_TRANSCRIPTIONS_PER_HOUR,
    media_magic_matches,
)
from ..models import (
    Account,
    ConfigRevision,
    Conversation,
    Document,
    Event,
    Member,
    MemoryItem,
    Message,
    OutreachCampaign,
    ProfessionalEmail,
    Space,
    utcnow,
)
from ..positioning import load_product_positioning
from ..rate_limit import client_ip
from ..relationship_graph import build_relationship_graph
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
    RelationshipGraphOut,
    RevisionCreate,
    RevisionOut,
    SlugAvailabilityOut,
    SlugClaim,
    SpaceDetail,
    SpaceOut,
    StudioDictationOut,
    StudioTurnOut,
)
from ..tenant import normalize_claimed_slug
from .outreach import campaign_out, latest_campaign

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
    if body.attachment_id or body.document_id or not body.content:
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
            ProfessionalEmail.outreach_campaign_id.is_(None),
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


def _owned_space_role(db: Session, context: ProfessionalContext, space_id: str) -> str:
    role = db.scalar(
        select(Space.public_role).where(
            Space.id == space_id,
            Space.account_id == context.account_id,
        )
    )
    if not role:
        raise HTTPException(status_code=404, detail="Spazio non trovato")
    return role


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


@router.get("/space/slug/{slug}/availability", response_model=SlugAvailabilityOut)
def get_slug_availability(
    slug: str,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> SlugAvailabilityOut:
    normalized = normalize_claimed_slug(slug)
    owned_space = professional_space(db, context)
    existing = db.scalar(
        select(Space.id).where(Space.slug == normalized, Space.id != owned_space.id)
    )
    return SlugAvailabilityOut(slug=normalized, available=existing is None)


@router.patch("/space/slug", response_model=SpaceOut)
def claim_space_slug(
    body: SlugClaim,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> SpaceOut:
    normalized = normalize_claimed_slug(body.slug)
    authorized_space = professional_space(db, context)
    space = db.scalar(
        select(Space)
        .where(Space.id == authorized_space.id, Space.account_id == context.account_id)
        .with_for_update()
    )
    if not space:
        raise HTTPException(status_code=404, detail="Spazio non trovato")
    if space.onboarding_state == "published" and space.slug != normalized:
        raise HTTPException(
            status_code=409,
            detail="Lo spazio pubblicato non può cambiare indirizzo da questo flusso",
        )
    existing = db.scalar(
        select(Space.id).where(Space.slug == normalized, Space.id != space.id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Questo indirizzo è già stato scelto")
    previous_slug = space.slug if space.slug_claimed else None
    space.slug = normalized
    space.slug_claimed = True
    if space.onboarding_state == "invited":
        space.onboarding_state = "building"
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="public_slug_claimed",
            payload={"slug": normalized, "previous_slug": previous_slug},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Questo indirizzo è già stato scelto")
    return SpaceOut.model_validate(space)


@router.get("/relationship-graph", response_model=RelationshipGraphOut)
def get_relationship_graph(
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> RelationshipGraphOut:
    return build_relationship_graph(
        db,
        space=professional_space(db, context),
        positioning=load_product_positioning(settings.product_positioning_json),
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
    try:
        validate_knowledge_document_references(
            db,
            account_id=context.account_id,
            space_id=space.id,
            configuration=document,
        )
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    if not space.slug_claimed:
        raise HTTPException(
            status_code=409,
            detail="Scegli il tuo indirizzo pubblico prima di attivare la prima versione",
        )
    target = db.scalar(
        select(ConfigRevision).where(
            ConfigRevision.id == revision_id,
            ConfigRevision.account_id == context.account_id,
            ConfigRevision.space_id == space.id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Revisione non trovata")
    try:
        validate_knowledge_document_references(
            db,
            account_id=context.account_id,
            space_id=space.id,
            configuration=target.document,
        )
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    space.is_active = True
    space.onboarding_state = "published"
    context.member.display_name = space.professional_name
    account = db.scalar(select(Account).where(Account.id == context.account_id))
    if account:
        account.name = f"{space.professional_name} — LAGGENTE"
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
                "public_slug": space.slug,
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
            content=(
                f"La revisione {target.revision_number} è ora attiva su "
                f"{space.slug}.laggente.com."
            ),
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
    latest_outreach = latest_campaign(
        db, account_id=context.account_id, space_id=space.id
    ) if settings.outreach_enabled else None
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
        latest_campaign=(campaign_out(db, latest_outreach) if latest_outreach else None),
    )


@router.post("/dictation", response_model=StudioDictationOut)
async def transcribe_studio_dictation(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> StudioDictationOut:
    """Transcribe private Studio audio without creating a message or retaining the recording."""

    request.app.state.rate_limiter.check(
        f"studio-dictation-ip:{client_ip(request)}", limit=12, window_seconds=10 * 60
    )
    request.app.state.rate_limiter.check(
        f"studio-dictation-member:{context.member.id}", limit=12, window_seconds=60 * 60
    )
    space = professional_space(db, context)
    account_id = context.account_id
    member_id = context.member.id
    space_id = space.id
    # Authentication is complete. Do not hold its transaction while reading multipart data.
    db.commit()

    declared_type = (file.content_type or "").lower().split(";", 1)[0].strip()
    media = ALLOWED_MEDIA_TYPES.get(declared_type)
    if not media or media[0] != "audio":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Serve un file audio per la dettatura",
        )
    extension = media[1]
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File troppo grande",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data or not media_magic_matches(data[:64], declared_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Contenuto audio non valido",
        )

    transcription_count = db.scalar(
        select(func.count(Event.id)).where(
            Event.account_id == account_id,
            Event.event_type == "audio_transcription_started",
            Event.created_at >= utcnow() - timedelta(hours=1),
        )
    )
    if int(transcription_count or 0) >= MAX_ACCOUNT_AUDIO_TRANSCRIPTIONS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite temporaneo delle trascrizioni raggiunto. Riprova più tardi.",
        )

    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            conversation_id=None,
            actor_type="professional",
            actor_id=member_id,
            event_type="audio_transcription_started",
            payload={"surface": "studio", "size_bytes": total},
        )
    )
    # The attempt survives cancellation for account-wide spend control, and the synchronous
    # connection is released before the external transcription request.
    db.commit()

    target: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="laggente-studio-dictation-", suffix=extension, dir="/tmp"
        )
        os.close(descriptor)
        target = Path(temporary_name)
        target.write_bytes(data)
        target.chmod(0o600)
        transcript = await request.app.state.audio_transcriber.transcribe(target, declared_type)
    except asyncio.CancelledError:
        try:
            db.add(
                Event(
                    account_id=account_id,
                    space_id=space_id,
                    conversation_id=None,
                    actor_type="system",
                    event_type="audio_transcription_failed",
                    payload={"surface": "studio", "error_type": "CancelledError"},
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        db.add(
            Event(
                account_id=account_id,
                space_id=space_id,
                conversation_id=None,
                actor_type="system",
                event_type="audio_transcription_failed",
                payload={"surface": "studio", "error_type": type(exc).__name__},
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Trascrizione non disponibile. Riprova più tardi.",
        ) from exc
    finally:
        if target:
            target.unlink(missing_ok=True)

    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            conversation_id=None,
            actor_type="professional",
            actor_id=member_id,
            event_type="studio_dictation_transcribed",
            payload={"size_bytes": total, "raw_audio_deleted": True},
        )
    )
    db.commit()
    return StudioDictationOut(transcript=transcript)


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
                    existing_campaign = db.scalar(
                        select(OutreachCampaign)
                        .where(
                            OutreachCampaign.account_id == context.account_id,
                            OutreachCampaign.space_id == space.id,
                            OutreachCampaign.source_message_id == professional_message.id,
                        )
                        .order_by(OutreachCampaign.created_at.desc())
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
                        proposed_campaign=(
                            campaign_out(db, existing_campaign)
                            if existing_campaign
                            else None
                        ),
                    )
        if professional_message is None:
            professional_message = Message(
                account_id=context.account_id,
                conversation_id=conversation.id,
                author_type="professional",
                author_label=f"{member.display_name} — {space.public_role}",
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
        proposed_campaign = None
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
            if reply.proposed_campaign_id:
                proposed_campaign = db.scalar(
                    select(OutreachCampaign).where(
                        OutreachCampaign.id == reply.proposed_campaign_id,
                        OutreachCampaign.account_id == context.account_id,
                        OutreachCampaign.space_id == space.id,
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
            proposed_campaign=(
                campaign_out(db, proposed_campaign) if proposed_campaign else None
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
    if body.attachment_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Per questa conversazione usa un documento oppure un messaggio di testo",
        )
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
    document = None
    if body.document_id:
        document = db.scalar(
            select(Document).where(
                Document.id == body.document_id,
                Document.account_id == context.account_id,
                Document.space_id == conversation.space_id,
                Document.conversation_id == conversation.id,
                Document.scope == "conversation",
                Document.uploader_type == "professional",
                Document.message_id.is_(None),
                Document.status == "ready",
            )
        )
        if not document:
            raise HTTPException(status_code=404, detail="Documento non trovato")
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
        author_label=(
            f"{context.member.display_name} — "
            f"{_owned_space_role(db, context, conversation.space_id)}"
        ),
        content=body.content or f"Ho condiviso il documento “{document.original_name}”.",
        content_type="document" if document else "text",
        client_message_id=body.client_message_id,
    )
    db.add(message)
    db.flush()
    if document:
        document.message_id = message.id
    conversation.last_message_at = utcnow()
    db.add(
        Event(
            account_id=context.account_id,
            space_id=conversation.space_id,
            conversation_id=conversation.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="professional_message_sent",
            payload={
                "automatic_ai_paused": was_enabled,
                "document_id": document.id if document else None,
            },
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
