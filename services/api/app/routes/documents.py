from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..conversations import active_revision
from ..database import get_db
from ..dependencies import (
    ProfessionalContext,
    authorize_public_conversation,
    current_professional,
    professional_space,
    runtime_settings,
)
from ..documents import (
    ALLOWED_DOCUMENT_MEDIA_TYPES,
    DocumentExtractionError,
    document_content_url,
    document_sha256,
    document_storage_key,
    extract_document_text,
    knowledge_document_ids,
    revision_document_states,
    safe_document_path,
    validate_knowledge_document_references,
)
from ..media import ALLOWED_MEDIA_TYPES
from ..models import (
    Attachment,
    ConfigRevision,
    Conversation,
    Document,
    Event,
    Member,
    Space,
    utcnow,
)
from ..onboarding import starter_space_configuration
from ..rate_limit import client_ip
from ..schemas import (
    MAX_CONFIGURATION_DOCUMENT_BYTES,
    DocumentCreated,
    DocumentOut,
    DocumentPublicationProposal,
    DocumentPublicationProposalOut,
    RevisionOut,
    SpaceConfigEnvelope,
)
from ..security import hash_token, new_opaque_token, read_session_claims
from ..tenant import require_public_space_host


router = APIRouter(tags=["documents"])

MAX_ACCOUNT_PRIVATE_FILE_BYTES = 512 * 1024 * 1024
MAX_CONVERSATION_PRIVATE_FILE_BYTES = 50 * 1024 * 1024
MAX_CONVERSATION_FILE_RECORDS = 20
MAX_STUDIO_DOCUMENTS = 100
EXTENSION_MEDIA_TYPES = {
    extension: media_type
    for media_type, extension in ALLOWED_DOCUMENT_MEDIA_TYPES.items()
}


def _declared_document_type(file: UploadFile) -> tuple[str, str]:
    declared = (file.content_type or "").lower().split(";", 1)[0].strip()
    suffix = Path(file.filename or "").suffix.lower()
    if declared not in ALLOWED_DOCUMENT_MEDIA_TYPES:
        declared = EXTENSION_MEDIA_TYPES.get(suffix, "")
    extension = ALLOWED_DOCUMENT_MEDIA_TYPES.get(declared)
    if not extension:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato non supportato. Usa PDF, DOCX, TXT, Markdown o CSV.",
        )
    return declared, extension


async def _read_document(file: UploadFile, settings: Settings) -> tuple[bytes, str, str, str]:
    media_type, extension = _declared_document_type(file)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Documento troppo grande")
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        extracted_text = extract_document_text(data, media_type)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return data, media_type, extension, extracted_text


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _public_state(document_id: str, active: set[str], draft: set[str]) -> str:
    if document_id in active:
        return "active"
    if document_id in draft:
        return "draft"
    return "private"


def _document_out(
    document: Document,
    *,
    active: set[str] | None = None,
    draft: set[str] | None = None,
) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        conversation_id=document.conversation_id,
        message_id=document.message_id,
        scope=document.scope,
        uploader_type=document.uploader_type,
        original_name=document.original_name,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        sha256=document.sha256,
        status=document.status,
        extracted_characters=len(document.extracted_text),
        public_state=_public_state(document.id, active or set(), draft or set()),
        download_url=document_content_url(document),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _account_private_bytes(db: Session, account_id: str) -> int:
    image_bytes = db.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.account_id == account_id,
            Attachment.status == "available",
            Attachment.media_type.in_(
                [
                    media_type
                    for media_type, (kind, _) in ALLOWED_MEDIA_TYPES.items()
                    if kind == "image"
                ]
            ),
        )
    )
    document_bytes = db.scalar(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.account_id == account_id,
            Document.status == "ready",
        )
    )
    return int(image_bytes or 0) + int(document_bytes or 0)


def _conversation_private_bytes(db: Session, account_id: str, conversation_id: str) -> int:
    image_bytes = db.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.account_id == account_id,
            Attachment.conversation_id == conversation_id,
            Attachment.status == "available",
        )
    )
    document_bytes = db.scalar(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.account_id == account_id,
            Document.conversation_id == conversation_id,
            Document.status == "ready",
        )
    )
    return int(image_bytes or 0) + int(document_bytes or 0)


def _conversation_file_count(db: Session, account_id: str, conversation_id: str) -> int:
    attachment_count = db.scalar(
        select(func.count(Attachment.id)).where(
            Attachment.account_id == account_id,
            Attachment.conversation_id == conversation_id,
        )
    )
    document_count = db.scalar(
        select(func.count(Document.id)).where(
            Document.account_id == account_id,
            Document.conversation_id == conversation_id,
        )
    )
    return int(attachment_count or 0) + int(document_count or 0)


def _write_document_file(settings: Settings, document: Document, data: bytes) -> Path:
    target = safe_document_path(settings.upload_dir, document.storage_key)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for directory in (target.parent.parent, target.parent):
        directory.chmod(0o700)
    target.write_bytes(data)
    target.chmod(0o600)
    return target


def _create_document(
    db: Session,
    settings: Settings,
    *,
    account_id: str,
    space_id: str,
    conversation_id: str | None,
    scope: str,
    uploader_type: str,
    uploader_id: str | None,
    original_name: str,
    media_type: str,
    extension: str,
    extracted_text: str,
    data: bytes,
) -> Document:
    if _account_private_bytes(db, account_id) + len(data) > MAX_ACCOUNT_PRIVATE_FILE_BYTES:
        raise HTTPException(status_code=409, detail="Spazio privato disponibile esaurito")
    if conversation_id:
        if _conversation_file_count(db, account_id, conversation_id) >= MAX_CONVERSATION_FILE_RECORDS:
            raise HTTPException(status_code=409, detail="Limite allegati della conversazione raggiunto")
        if (
            _conversation_private_bytes(db, account_id, conversation_id) + len(data)
            > MAX_CONVERSATION_PRIVATE_FILE_BYTES
        ):
            raise HTTPException(
                status_code=409,
                detail="Limite spazio documenti della conversazione raggiunto",
            )
    else:
        studio_count = db.scalar(
            select(func.count(Document.id)).where(
                Document.account_id == account_id,
                Document.space_id == space_id,
                Document.scope == "studio",
            )
        )
        if int(studio_count or 0) >= MAX_STUDIO_DOCUMENTS:
            raise HTTPException(status_code=409, detail="Limite documenti dello Studio raggiunto")

    opaque_name = f"{new_opaque_token()}{extension}"
    document = Document(
        account_id=account_id,
        space_id=space_id,
        conversation_id=conversation_id,
        scope=scope,
        uploader_type=uploader_type,
        uploader_id=uploader_id,
        storage_key=document_storage_key(
            account_id=account_id,
            space_id=space_id,
            conversation_id=conversation_id,
            opaque_name=opaque_name,
        ),
        original_name=Path(original_name or f"documento{extension}").name[:255],
        media_type=media_type,
        size_bytes=len(data),
        sha256=document_sha256(data),
        extracted_text=extracted_text,
        status="ready",
    )
    db.add(document)
    target: Path | None = None
    try:
        db.flush()
        target = _write_document_file(settings, document, data)
        db.add(
            Event(
                account_id=account_id,
                space_id=space_id,
                conversation_id=conversation_id,
                actor_type=uploader_type,
                actor_id=uploader_id,
                event_type="document_uploaded",
                payload={
                    "document_id": document.id,
                    "scope": scope,
                    "media_type": media_type,
                    "size_bytes": len(data),
                },
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        if target:
            target.unlink(missing_ok=True)
        raise
    return document


def _professional_document(
    db: Session, context: ProfessionalContext, document_id: str
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.account_id == context.account_id,
        )
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return document


def _professional_conversation(
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


def _authorized_document(request: Request, db: Session, document_id: str) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.status == "ready"))
    if not document:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    settings = runtime_settings(request)
    if document.scope == "conversation" and document.conversation_id:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == document.conversation_id,
                Conversation.account_id == document.account_id,
                Conversation.space_id == document.space_id,
            )
        )
        space = db.scalar(
            select(Space).where(
                Space.id == document.space_id,
                Space.account_id == document.account_id,
            )
        )
        visitor_token = request.headers.get("X-Conversation-Token") or request.cookies.get(
            settings.visitor_cookie_name
        )
        if conversation and space and visitor_token:
            if conversation.visitor_token_hash == hash_token(visitor_token):
                try:
                    require_public_space_host(request, settings, space)
                except HTTPException:
                    pass
                else:
                    within_retention = _utc_datetime(
                        conversation.last_message_at
                    ) >= utcnow() - timedelta(days=settings.conversation_retention_days)
                    if space.is_active and within_retention:
                        return document
    try:
        claims = read_session_claims(request, settings)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    member = db.scalar(
        select(Member).where(
            Member.id == claims.member_id,
            Member.account_id == claims.account_id,
            Member.account_id == document.account_id,
            Member.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return document


@router.get("/studio/documents", response_model=list[DocumentOut])
def list_studio_documents(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> list[DocumentOut]:
    space = professional_space(db, context)
    active, draft = revision_document_states(
        db, account_id=context.account_id, space_id=space.id
    )
    documents = db.scalars(
        select(Document)
        .where(
            Document.account_id == context.account_id,
            Document.space_id == space.id,
            Document.scope == "studio",
            Document.status == "ready",
        )
        .order_by(Document.created_at.desc())
    ).all()
    return [_document_out(item, active=active, draft=draft) for item in documents]


@router.post("/studio/documents", response_model=DocumentCreated, status_code=201)
async def upload_studio_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> DocumentCreated:
    request.app.state.rate_limiter.check(
        f"studio-document:{context.member.id}", limit=20, window_seconds=60 * 60
    )
    data, media_type, extension, extracted_text = await _read_document(file, settings)
    space = professional_space(db, context)
    locked_space = db.scalar(
        select(Space)
        .where(Space.id == space.id, Space.account_id == context.account_id)
        .with_for_update()
    )
    if not locked_space:
        raise HTTPException(status_code=404, detail="Studio non trovato")
    document = _create_document(
        db,
        settings,
        account_id=context.account_id,
        space_id=space.id,
        conversation_id=None,
        scope="studio",
        uploader_type="professional",
        uploader_id=context.member.id,
        original_name=file.filename or f"documento{extension}",
        media_type=media_type,
        extension=extension,
        extracted_text=extracted_text,
        data=data,
    )
    return DocumentCreated(document=_document_out(document))


@router.post(
    "/studio/documents/{document_id}/public-proposal",
    response_model=DocumentPublicationProposalOut,
)
def propose_document_publication(
    document_id: str,
    body: DocumentPublicationProposal,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> DocumentPublicationProposalOut:
    space = professional_space(db, context)
    document = _professional_document(db, context, document_id)
    if document.scope != "studio" or document.space_id != space.id:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    locked_space = db.scalar(
        select(Space)
        .where(Space.id == space.id, Space.account_id == context.account_id)
        .with_for_update()
    )
    if not locked_space:
        raise HTTPException(status_code=404, detail="Studio non trovato")
    latest_draft = db.scalar(
        select(ConfigRevision)
        .where(
            ConfigRevision.account_id == context.account_id,
            ConfigRevision.space_id == space.id,
            ConfigRevision.status == "draft",
        )
        .order_by(ConfigRevision.revision_number.desc())
        .limit(1)
    )
    source = latest_draft or active_revision(db, space)
    configuration = deepcopy(source.document if source else starter_space_configuration())
    current_knowledge = configuration.get("knowledge")
    knowledge = list(current_knowledge) if isinstance(current_knowledge, list) else []
    knowledge = [
        item
        for item in knowledge
        if not (
            isinstance(item, dict)
            and item.get("type") == "document"
            and item.get("document_id") == document.id
        )
    ]
    if body.enabled:
        knowledge.append(
            {
                "type": "document",
                "document_id": document.id,
                "title": document.original_name,
                "sha256": document.sha256,
            }
        )
    configuration["knowledge"] = knowledge
    try:
        configuration = SpaceConfigEnvelope.model_validate(configuration).model_dump(mode="json")
        validate_knowledge_document_references(
            db,
            account_id=context.account_id,
            space_id=space.id,
            configuration=configuration,
        )
    except (DocumentExtractionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(json.dumps(configuration, ensure_ascii=False).encode("utf-8")) > MAX_CONFIGURATION_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Configurazione troppo grande")
    latest_number = db.scalar(
        select(func.max(ConfigRevision.revision_number)).where(
            ConfigRevision.account_id == context.account_id,
            ConfigRevision.space_id == space.id,
        )
    )
    revision = ConfigRevision(
        account_id=context.account_id,
        space_id=space.id,
        revision_number=(latest_number or 0) + 1,
        status="draft",
        document=configuration,
        rationale=(
            f"Rendi {document.original_name} disponibile all'assistente pubblico"
            if body.enabled
            else f"Rimuovi {document.original_name} dalla conoscenza pubblica attiva"
        ),
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
            event_type="document_publication_proposed",
            payload={
                "document_id": document.id,
                "revision_id": revision.id,
                "enabled": body.enabled,
            },
        )
    )
    db.commit()
    active, draft = revision_document_states(
        db, account_id=context.account_id, space_id=space.id
    )
    return DocumentPublicationProposalOut(
        document=_document_out(document, active=active, draft=draft),
        revision=RevisionOut.model_validate(revision),
    )


@router.post(
    "/public/conversations/{conversation_id}/documents",
    response_model=DocumentCreated,
    status_code=201,
)
async def upload_public_document(
    conversation_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> DocumentCreated:
    request.app.state.rate_limiter.check(
        f"public-document:{client_ip(request)}", limit=12, window_seconds=10 * 60
    )
    authorized = authorize_public_conversation(request, db, conversation_id)
    data, media_type, extension, extracted_text = await _read_document(file, settings)
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.id == authorized.id,
            Conversation.account_id == authorized.account_id,
            Conversation.space_id == authorized.space_id,
            Conversation.kind == "public",
        )
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    document = _create_document(
        db,
        settings,
        account_id=conversation.account_id,
        space_id=conversation.space_id,
        conversation_id=conversation.id,
        scope="conversation",
        uploader_type="visitor",
        uploader_id=None,
        original_name=file.filename or f"documento{extension}",
        media_type=media_type,
        extension=extension,
        extracted_text=extracted_text,
        data=data,
    )
    return DocumentCreated(document=_document_out(document))


@router.post(
    "/studio/conversations/{conversation_id}/documents",
    response_model=DocumentCreated,
    status_code=201,
)
async def upload_professional_conversation_document(
    conversation_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> DocumentCreated:
    request.app.state.rate_limiter.check(
        f"professional-document:{context.member.id}", limit=30, window_seconds=60 * 60
    )
    authorized = _professional_conversation(db, context, conversation_id)
    data, media_type, extension, extracted_text = await _read_document(file, settings)
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.id == authorized.id,
            Conversation.account_id == context.account_id,
            Conversation.kind == "public",
        )
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")
    document = _create_document(
        db,
        settings,
        account_id=context.account_id,
        space_id=conversation.space_id,
        conversation_id=conversation.id,
        scope="conversation",
        uploader_type="professional",
        uploader_id=context.member.id,
        original_name=file.filename or f"documento{extension}",
        media_type=media_type,
        extension=extension,
        extracted_text=extracted_text,
        data=data,
    )
    return DocumentCreated(document=_document_out(document))


@router.get(
    "/public/conversations/{conversation_id}/documents", response_model=list[DocumentOut]
)
def list_public_conversation_documents(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    conversation = authorize_public_conversation(request, db, conversation_id)
    documents = db.scalars(
        select(Document)
        .where(
            Document.account_id == conversation.account_id,
            Document.space_id == conversation.space_id,
            Document.conversation_id == conversation.id,
            Document.scope == "conversation",
            Document.message_id.is_not(None),
            Document.status == "ready",
        )
        .order_by(Document.created_at)
    ).all()
    return [_document_out(item) for item in documents]


@router.get(
    "/studio/conversations/{conversation_id}/documents", response_model=list[DocumentOut]
)
def list_professional_conversation_documents(
    conversation_id: str,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> list[DocumentOut]:
    conversation = _professional_conversation(db, context, conversation_id)
    documents = db.scalars(
        select(Document)
        .where(
            Document.account_id == context.account_id,
            Document.conversation_id == conversation.id,
            Document.scope == "conversation",
            Document.message_id.is_not(None),
            Document.status == "ready",
        )
        .order_by(Document.created_at)
    ).all()
    return [_document_out(item) for item in documents]


@router.get("/documents/{document_id}/content", include_in_schema=False)
def document_content(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> FileResponse:
    document = _authorized_document(request, db, document_id)
    target = safe_document_path(settings.upload_dir, document.storage_key)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Documento non trovato")
    return FileResponse(
        target,
        media_type=document.media_type,
        filename=document.original_name,
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> None:
    document = _authorized_document(request, db, document_id)
    actor_type = "visitor"
    actor_id = None
    try:
        claims = read_session_claims(request, settings)
    except HTTPException:
        claims = None
    if claims and claims.account_id == document.account_id:
        actor_type = "professional"
        actor_id = claims.member_id
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings.app_origin.rstrip("/"):
            raise HTTPException(status_code=403, detail="Origine non autorizzata")
    if document.scope == "studio" and actor_type != "professional":
        raise HTTPException(status_code=404, detail="Documento non trovato")
    if document.scope == "studio":
        space = db.scalar(
            select(Space).where(
                Space.id == document.space_id,
                Space.account_id == document.account_id,
            )
        )
        active = active_revision(db, space) if space else None
        if active and document.id in knowledge_document_ids(active.document):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Rimuovi prima il documento dalla conoscenza pubblica e attiva la nuova versione"
                ),
            )
    target = safe_document_path(settings.upload_dir, document.storage_key)
    if target.exists():
        if not target.is_file():
            raise HTTPException(status_code=500, detail="Archivio privato non valido")
        target.unlink()
    db.add(
        Event(
            account_id=document.account_id,
            space_id=document.space_id,
            conversation_id=document.conversation_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type="document_deleted",
            payload={
                "document_id": document.id,
                "scope": document.scope,
                "was_bound": document.message_id is not None,
            },
        )
    )
    db.delete(document)
    db.commit()
