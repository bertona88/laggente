from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..dependencies import current_professional, runtime_settings
from ..email import AuthEmailSender, EmailDeliveryError
from ..models import Event, MagicLink, Member, utcnow
from ..rate_limit import client_ip
from ..schemas import (
    MagicLinkConsume,
    MagicLinkRequest,
    MagicLinkRequestOut,
    MemberOut,
    PilotPasswordLogin,
    SessionOut,
)
from ..security import (
    TokenError,
    TokenSigner,
    clear_session_cookie,
    hash_ip,
    hash_token,
    issue_session_token,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/mode")
def auth_mode(settings: Settings = Depends(runtime_settings)) -> dict[str, str]:
    return {"mode": settings.auth_mode}


@router.post("/magic-link/request", response_model=MagicLinkRequestOut)
async def request_magic_link(
    body: MagicLinkRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> MagicLinkRequestOut:
    request.app.state.rate_limiter.check(
        f"magic:{client_ip(request)}", limit=8, window_seconds=15 * 60
    )
    if settings.auth_mode != "magic_link":
        raise HTTPException(status_code=409, detail="Accesso con password pilot attivo")
    member = db.scalar(
        select(Member).where(Member.email == body.email.lower(), Member.is_active.is_(True))
    )
    development_link = None
    if member:
        signer = TokenSigner(settings.session_secret)
        token = signer.issue(
            "magic_link",
            settings.magic_link_ttl_seconds,
            member_id=member.id,
            account_id=member.account_id,
        )
        record = MagicLink(
            account_id=member.account_id,
            member_id=member.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.magic_link_ttl_seconds),
            requested_ip_hash=hash_ip(client_ip(request), settings.session_secret),
        )
        db.add(record)
        db.commit()
        # Fragments are consumed client-side and never reach reverse-proxy or application logs.
        magic_link = f"{settings.app_origin.rstrip('/')}/login#token={quote(token)}"
        try:
            await request.app.state.email_sender.send_magic_link(member.email, magic_link)
        except EmailDeliveryError:
            raise HTTPException(status_code=503, detail="Invio email temporaneamente non disponibile")
        if not settings.is_production:
            development_link = magic_link
    return MagicLinkRequestOut(development_magic_link=development_link)


@router.post("/magic-link/consume", response_model=SessionOut)
def consume_magic_link(
    body: MagicLinkConsume,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> SessionOut:
    if settings.auth_mode != "magic_link":
        raise HTTPException(status_code=409, detail="Accesso con password pilot attivo")
    try:
        claims = TokenSigner(settings.session_secret).verify(body.token, "magic_link")
    except TokenError:
        raise HTTPException(status_code=401, detail="Link non valido o scaduto")
    member_id = claims.get("member_id")
    account_id = claims.get("account_id")
    consumed_at = utcnow()
    consume_result = db.execute(
        update(MagicLink)
        .where(
            MagicLink.token_hash == hash_token(body.token),
            MagicLink.member_id == member_id,
            MagicLink.account_id == account_id,
            MagicLink.consumed_at.is_(None),
            MagicLink.expires_at > consumed_at,
        )
        .values(consumed_at=consumed_at)
        .execution_options(synchronize_session=False)
    )
    if consume_result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=401, detail="Link non valido, scaduto o già usato")
    member = db.scalar(
        select(Member).where(
            Member.id == member_id,
            Member.account_id == account_id,
            Member.is_active.is_(True),
        )
    )
    if not member:
        db.rollback()
        raise HTTPException(status_code=401, detail="Accesso non disponibile")
    db.add(
        Event(
            account_id=member.account_id,
            actor_type="professional",
            actor_id=member.id,
            event_type="studio_session_started",
            payload={"method": "magic_link"},
        )
    )
    db.commit()
    set_session_cookie(
        response, settings, issue_session_token(settings, member.id, member.account_id)
    )
    return SessionOut(member=MemberOut.model_validate(member))


@router.post("/pilot-login", response_model=SessionOut)
def pilot_login(
    body: PilotPasswordLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> SessionOut:
    request.app.state.rate_limiter.check(
        f"login:{client_ip(request)}", limit=8, window_seconds=15 * 60
    )
    if settings.auth_mode != "pilot_password":
        raise HTTPException(status_code=404, detail="Metodo di accesso non disponibile")
    member = db.scalar(
        select(Member).where(Member.email == body.email.lower(), Member.is_active.is_(True))
    )
    if not member or not verify_password(body.password, member.password_hash):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    db.add(
        Event(
            account_id=member.account_id,
            actor_type="professional",
            actor_id=member.id,
            event_type="studio_session_started",
            payload={"method": "pilot_password"},
        )
    )
    db.commit()
    set_session_cookie(
        response, settings, issue_session_token(settings, member.id, member.account_id)
    )
    return SessionOut(member=MemberOut.model_validate(member))


@router.get("/session", response_model=SessionOut)
def session(context=Depends(current_professional)) -> SessionOut:
    return SessionOut(member=MemberOut.model_validate(context.member))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    settings: Settings = Depends(runtime_settings),
) -> Response:
    clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
