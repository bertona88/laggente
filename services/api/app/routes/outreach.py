from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..dependencies import (
    ProfessionalContext,
    current_professional,
    professional_space,
    runtime_settings,
)
from ..models import (
    Event,
    Message,
    OutreachCampaign,
    OutreachRecipient,
    ProfessionalEmail,
    utcnow,
)
from ..outreach import (
    OUTREACH_PERMISSION_BASES,
    address_is_suppressed,
    campaign_recipients,
    refresh_campaign_status,
    register_unsubscribe,
)
from ..professional_email import PreparedProfessionalEmail
from ..schemas import (
    OutreachCampaignOut,
    OutreachRecipientOut,
    OutreachUnsubscribeOut,
    OutreachUnsubscribeRequest,
    ProfessionalEmailOut,
)

router = APIRouter(tags=["outreach"])


def campaign_out(db: Session, campaign: OutreachCampaign) -> OutreachCampaignOut:
    recipients = campaign_recipients(db, campaign)
    email_ids = [item.professional_email_id for item in recipients if item.professional_email_id]
    emails = {
        item.id: item
        for item in db.scalars(
            select(ProfessionalEmail).where(
                ProfessionalEmail.account_id == campaign.account_id,
                ProfessionalEmail.space_id == campaign.space_id,
                ProfessionalEmail.id.in_(email_ids),
            )
        ).all()
    } if email_ids else {}
    return OutreachCampaignOut(
        id=campaign.id,
        name=campaign.name,
        landing_url=campaign.landing_url,
        status=campaign.status,
        recipient_cap=campaign.recipient_cap,
        authorized_at=campaign.authorized_at,
        completed_at=campaign.completed_at,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        recipients=[
            OutreachRecipientOut(
                id=item.id,
                campaign_id=item.campaign_id,
                name=item.name,
                email=item.email,
                source_url=item.source_url,
                source_label=item.source_label,
                personalization_note=item.personalization_note,
                permission_basis=item.permission_basis,
                permission_evidence=item.permission_evidence,
                status=item.status,
                unsubscribe_requested_at=item.unsubscribe_requested_at,
                retention_until=item.retention_until,
                professional_email=(
                    ProfessionalEmailOut.model_validate(emails[item.professional_email_id])
                    if item.professional_email_id in emails
                    else None
                ),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in recipients
        ],
    )


def latest_campaign(
    db: Session, *, account_id: str, space_id: str
) -> OutreachCampaign | None:
    return db.scalar(
        select(OutreachCampaign)
        .where(
            OutreachCampaign.account_id == account_id,
            OutreachCampaign.space_id == space_id,
        )
        .order_by(OutreachCampaign.created_at.desc())
        .limit(1)
    )


@router.get("/studio/outreach", response_model=list[OutreachCampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> list[OutreachCampaignOut]:
    if not settings.outreach_enabled:
        raise HTTPException(status_code=404, detail="Outreach non attivo")
    space = professional_space(db, context)
    campaigns = list(
        db.scalars(
            select(OutreachCampaign)
            .where(
                OutreachCampaign.account_id == context.account_id,
                OutreachCampaign.space_id == space.id,
            )
            .order_by(OutreachCampaign.created_at.desc())
            .limit(20)
        ).all()
    )
    return [campaign_out(db, item) for item in campaigns]


@router.get("/studio/outreach/{campaign_id}", response_model=OutreachCampaignOut)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> OutreachCampaignOut:
    if not settings.outreach_enabled:
        raise HTTPException(status_code=404, detail="Outreach non attivo")
    space = professional_space(db, context)
    campaign = db.scalar(
        select(OutreachCampaign).where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.account_id == context.account_id,
            OutreachCampaign.space_id == space.id,
        )
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagna non trovata")
    refresh_campaign_status(db, campaign)
    db.commit()
    return campaign_out(db, campaign)


@router.post(
    "/studio/outreach/{campaign_id}/authorize", response_model=OutreachCampaignOut
)
async def authorize_campaign(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
    context: ProfessionalContext = Depends(current_professional),
) -> OutreachCampaignOut:
    if not settings.outreach_enabled or not settings.agent_mail_enabled:
        raise HTTPException(status_code=409, detail="Outreach non attivo")
    request.app.state.rate_limiter.check(
        f"outreach-campaign-send:{context.member.id}", limit=2, window_seconds=3600
    )
    space = professional_space(db, context)
    campaign = db.scalar(
        select(OutreachCampaign)
        .where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.account_id == context.account_id,
            OutreachCampaign.space_id == space.id,
        )
        .with_for_update()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagna non trovata")
    if campaign.status in {"sent", "simulated", "partial", "failed"}:
        return campaign_out(db, campaign)
    refresh_campaign_status(db, campaign)
    recipients = campaign_recipients(db, campaign)
    if campaign.status != "ready" or not recipients:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Ogni destinatario deve avere una base di contatto registrata e "
                "un'email esatta sigillata."
            ),
        )
    if len(recipients) > min(campaign.recipient_cap, settings.outreach_max_recipients):
        db.rollback()
        raise HTTPException(status_code=409, detail="La campagna supera il limite del pilot")

    emails: list[tuple[OutreachRecipient, ProfessionalEmail]] = []
    for recipient in recipients:
        email = db.scalar(
            select(ProfessionalEmail).where(
                ProfessionalEmail.id == recipient.professional_email_id,
                ProfessionalEmail.account_id == context.account_id,
                ProfessionalEmail.space_id == space.id,
                ProfessionalEmail.outreach_campaign_id == campaign.id,
                ProfessionalEmail.outreach_recipient_id == recipient.id,
            )
        )
        if (
            recipient.permission_basis not in OUTREACH_PERMISSION_BASES
            or recipient.unsubscribe_requested_at is not None
            or not recipient.email
            or address_is_suppressed(
                db, account_id=context.account_id, email=recipient.email
            )
            or recipient.status != "drafted"
            or not email
            or email.status != "draft"
        ):
            db.rollback()
            raise HTTPException(status_code=409, detail="Campagna non più autorizzabile")
        emails.append((recipient, email))

    campaign.status = "sending"
    campaign.authorized_by_member_id = context.member.id
    campaign.authorized_at = utcnow()
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            conversation_id=campaign.studio_conversation_id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="outreach_campaign_authorized",
            payload={
                "campaign_id": campaign.id,
                "email_ids": [item.id for _, item in emails],
                "content_sha256": [item.content_sha256 for _, item in emails],
            },
        )
    )
    db.commit()

    delivered = 0
    simulated = 0
    failed = 0
    for recipient, email in emails:
        email = db.scalar(
            select(ProfessionalEmail)
            .where(
                ProfessionalEmail.id == email.id,
                ProfessionalEmail.account_id == context.account_id,
                ProfessionalEmail.space_id == space.id,
            )
            .with_for_update()
        )
        if not email or email.status != "draft":
            failed += 1
            break
        email.status = "sending"
        email.authorized_by_member_id = context.member.id
        email.authorized_at = campaign.authorized_at
        db.commit()
        prepared = PreparedProfessionalEmail(
            id=email.id,
            from_address=email.from_address,
            to_address=email.to_address,
            raw_content=bytes(email.raw_content),
        )
        try:
            result = await request.app.state.professional_mail_transport.send(prepared)
        except Exception as exc:
            db.rollback()
            email = db.get(ProfessionalEmail, email.id)
            recipient = db.get(OutreachRecipient, recipient.id)
            if email:
                email.status = "failed"
                email.failure_code = type(exc).__name__[:120]
            if recipient:
                recipient.status = "failed"
            failed += 1
            db.add(
                Event(
                    account_id=context.account_id,
                    space_id=space.id,
                    conversation_id=campaign.studio_conversation_id,
                    actor_type="system",
                    event_type="outreach_email_delivery_failed",
                    payload={"campaign_id": campaign.id, "email_id": email.id if email else None},
                )
            )
            db.commit()
            break

        email = db.get(ProfessionalEmail, email.id)
        recipient = db.get(OutreachRecipient, recipient.id)
        if not email or not recipient:
            failed += 1
            break
        email.provider = result.provider
        email.provider_message_id = result.provider_message_id
        provider_state_already_recorded = email.status != "sending"
        if not provider_state_already_recorded:
            email.status = "sent" if result.delivered else "simulated"
            email.failure_code = None
        if result.delivered and not email.sent_at:
            email.sent_at = utcnow()
        recipient.status = email.status
        delivered += int(result.delivered)
        simulated += int(not result.delivered)
        if not provider_state_already_recorded:
            db.add(
                Event(
                    account_id=context.account_id,
                    space_id=space.id,
                    conversation_id=campaign.studio_conversation_id,
                    actor_type="system",
                    event_type=(
                        "outreach_email_sent"
                        if result.delivered
                        else "outreach_email_simulated"
                    ),
                    payload={
                        "campaign_id": campaign.id,
                        "recipient_id": recipient.id,
                        "email_id": email.id,
                        "provider": result.provider,
                        "provider_message_id": result.provider_message_id,
                    },
                )
            )
        db.commit()

    campaign = db.get(OutreachCampaign, campaign.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagna non trovata")
    if failed:
        campaign.status = "partial" if delivered or simulated else "failed"
    elif delivered:
        campaign.status = "sent"
    else:
        campaign.status = "simulated"
    campaign.completed_at = utcnow()
    db.add(
        Message(
            account_id=context.account_id,
            conversation_id=campaign.studio_conversation_id,
            author_type="system",
            author_label="LAGGENTE",
            content=(
                f"Campagna “{campaign.name}”: {delivered} invii accettati, "
                f"{simulated} simulati, {failed} non confermati. Nessun errore viene ritentato "
                "automaticamente."
            ),
        )
    )
    db.commit()
    db.refresh(campaign)
    return campaign_out(db, campaign)


@router.post("/outreach/unsubscribe", response_model=OutreachUnsubscribeOut)
def unsubscribe(
    body: OutreachUnsubscribeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OutreachUnsubscribeOut:
    # Always return the same response so a token probe cannot enumerate campaign records.
    client_host = request.client.host if request.client else "unknown"
    request.app.state.rate_limiter.check(
        f"outreach-unsubscribe:{client_host}", limit=30, window_seconds=60
    )
    register_unsubscribe(db, body.token)
    return OutreachUnsubscribeOut()
