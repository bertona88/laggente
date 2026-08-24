from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..dependencies import ProfessionalContext, current_professional, runtime_settings
from ..email import EmailDeliveryError
from ..models import Account, Event, MagicLink, Member, Space
from ..onboarding import provision_private_professional_space
from ..rate_limit import client_ip
from ..schemas import ProfessionalInvitationCreate, ProfessionalInvitationOut
from ..security import TokenSigner, hash_ip, hash_token


router = APIRouter(prefix="/studio/invitations", tags=["studio-invitations"])


def _target_space(db: Session, member: Member) -> Space | None:
    return db.scalar(
        select(Space).where(Space.account_id == member.account_id).order_by(Space.created_at).limit(1)
    )


@router.post("", response_model=ProfessionalInvitationOut, status_code=status.HTTP_201_CREATED)
async def invite_professional(
    body: ProfessionalInvitationCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> ProfessionalInvitationOut:
    if not context.member.can_invite:
        raise HTTPException(status_code=403, detail="Non puoi invitare altri professionisti")
    request.app.state.rate_limiter.check(
        f"professional-invite:{context.member.id}", limit=10, window_seconds=60 * 60
    )

    email = str(body.email).strip().lower()
    target_member = db.scalar(select(Member).where(Member.email == email))
    invitation_status = "resent"
    if target_member:
        target_space = _target_space(db, target_member)
        if (
            not target_member.is_active
            or not target_space
            or target_space.onboarding_state != "invited"
        ):
            raise HTTPException(
                status_code=409,
                detail="Questo indirizzo è già associato a uno spazio LAGGENTE",
            )
        original_invitation = db.scalar(
            select(MagicLink.id)
            .where(
                MagicLink.member_id == target_member.id,
                MagicLink.account_id == target_member.account_id,
                MagicLink.purpose == "professional_invitation",
                MagicLink.created_by_member_id == context.member.id,
            )
            .limit(1)
        )
        if not original_invitation:
            # Do not let another platform inviter discover or take over a pending invitation.
            raise HTTPException(
                status_code=409,
                detail="Questo indirizzo è già associato a uno spazio LAGGENTE",
            )
        target_account = db.scalar(select(Account).where(Account.id == target_member.account_id))
        if not target_account:
            raise HTTPException(status_code=409, detail="Invito non disponibile")
    else:
        invitation_status = "sent"
        provisioned = provision_private_professional_space(
            db,
            email=email,
            onboarding_state="invited",
        )
        target_account = provisioned.account
        target_member = provisioned.member
        target_space = provisioned.space

    expires_at = datetime.now(UTC) + timedelta(seconds=settings.invitation_ttl_seconds)
    token = TokenSigner(settings.session_secret).issue(
        "professional_invitation",
        settings.invitation_ttl_seconds,
        member_id=target_member.id,
        account_id=target_member.account_id,
        invited_by_member_id=context.member.id,
    )
    link_record = MagicLink(
        account_id=target_member.account_id,
        member_id=target_member.id,
        purpose="professional_invitation",
        created_by_member_id=context.member.id,
        token_hash=hash_token(token),
        expires_at=expires_at,
        requested_ip_hash=hash_ip(client_ip(request), settings.session_secret),
    )
    db.add(link_record)
    db.flush()
    db.add(
        Event(
            account_id=context.account_id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="professional_invitation_created",
            payload={
                "target_account_id": target_member.account_id,
                "target_member_id": target_member.id,
                "delivery": invitation_status,
            },
        )
    )
    db.add(
        Event(
            account_id=target_member.account_id,
            space_id=target_space.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="professional_invited",
            payload={"invitation_id": link_record.id},
        )
    )
    db.commit()

    invitation_link = f"{settings.app_origin.rstrip('/')}/login#invite={quote(token)}"
    try:
        await request.app.state.email_sender.send_professional_invitation(
            email, invitation_link, context.member.display_name
        )
    except EmailDeliveryError:
        db.add(
            Event(
                account_id=target_member.account_id,
                space_id=target_space.id,
                actor_type="system",
                event_type="professional_invitation_delivery_failed",
                payload={"invitation_id": link_record.id},
            )
        )
        db.commit()
        raise HTTPException(status_code=503, detail="Invio email temporaneamente non disponibile")

    return ProfessionalInvitationOut(
        email=email,
        status=invitation_status,
        expires_at=expires_at,
        development_magic_link=invitation_link if not settings.is_production else None,
    )
