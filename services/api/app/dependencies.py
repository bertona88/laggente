from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .database import get_db
from .models import Conversation, Member, Space, utcnow
from .security import hash_token, read_session_claims
from .tenant import require_public_space_host


@dataclass
class ProfessionalContext:
    member: Member
    account_id: str


def runtime_settings(request: Request) -> Settings:
    return request.app.state.settings


def current_professional(
    request: Request,
    db: Session = Depends(get_db),
) -> ProfessionalContext:
    settings = runtime_settings(request)
    claims = read_session_claims(request, settings)
    member = db.scalar(
        select(Member).where(
            Member.id == claims.member_id,
            Member.account_id == claims.account_id,
            Member.is_active.is_(True),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Accesso richiesto")
    return ProfessionalContext(member=member, account_id=member.account_id)


def professional_space(db: Session, context: ProfessionalContext) -> Space:
    space = db.scalar(
        select(Space).where(Space.account_id == context.account_id).order_by(Space.created_at).limit(1)
    )
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spazio non trovato")
    return space


def conversation_token(request: Request) -> str | None:
    settings = runtime_settings(request)
    return request.headers.get("X-Conversation-Token") or request.cookies.get(
        settings.visitor_cookie_name
    )


def authorize_public_conversation(
    request: Request,
    db: Session,
    conversation_id: str,
    *,
    require_active_space: bool = True,
) -> Conversation:
    settings = runtime_settings(request)
    token = conversation_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Conversazione non accessibile")
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.kind == "public",
            Conversation.visitor_token_hash == hash_token(token),
        )
    )
    if not conversation:
        # Deliberately do not reveal whether a conversation exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversazione non trovata")
    space = db.scalar(
        select(Space).where(
            Space.id == conversation.space_id,
            Space.account_id == conversation.account_id,
        )
    )
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversazione non trovata")
    require_public_space_host(request, settings, space)
    if require_active_space:
        still_within_retention = db.scalar(
            select(Conversation.id).where(
                Conversation.id == conversation.id,
                Conversation.last_message_at
                >= utcnow() - timedelta(days=settings.conversation_retention_days),
            )
        )
        if not still_within_retention:
            # The automatic retention cycle will remove the expired record. Do not leave a copied
            # bearer token readable indefinitely if that maintenance cycle is delayed.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversazione non trovata"
            )
        if (
            not space.is_active
            or not space.slug_claimed
            or space.onboarding_state != "published"
        ):
            # The valid token holder may still exercise deletion through the dedicated endpoint.
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Spazio non attivo; la conversazione può ancora essere eliminata",
            )
    return conversation
