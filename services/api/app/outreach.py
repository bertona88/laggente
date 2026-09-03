from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import (
    Conversation,
    Event,
    Message,
    OutreachCampaign,
    OutreachRecipient,
    OutreachSuppression,
    ProfessionalEmail,
    Space,
    utcnow,
)
from .professional_email import (
    ProfessionalEmailError,
    create_outbound_email_draft,
    normalize_address,
)

OUTREACH_PERMISSION_BASES = {"explicit_consent", "existing_customer_similar_services"}
TERMINAL_SUPPRESSION_STATUSES = {"bounced", "complained", "suppressed"}


class OutreachError(ValueError):
    pass


def _clean(value: str, *, maximum: int, error: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or "\x00" in cleaned:
        raise OutreachError(error)
    return cleaned


def _https_url(value: str, *, error: str, base_domain: str | None = None) -> str:
    cleaned = _clean(value, maximum=1000, error=error)
    parsed = urlsplit(cleaned)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise OutreachError(error)
    if base_domain and host != base_domain and not host.endswith(f".{base_domain}"):
        raise OutreachError(error)
    return cleaned


def _owned_campaign(
    db: Session, *, campaign_id: str, account_id: str, space_id: str
) -> OutreachCampaign | None:
    return db.scalar(
        select(OutreachCampaign).where(
            OutreachCampaign.id == campaign_id,
            OutreachCampaign.account_id == account_id,
            OutreachCampaign.space_id == space_id,
        )
    )


def campaign_recipients(db: Session, campaign: OutreachCampaign) -> list[OutreachRecipient]:
    return list(
        db.scalars(
            select(OutreachRecipient)
            .where(
                OutreachRecipient.account_id == campaign.account_id,
                OutreachRecipient.space_id == campaign.space_id,
                OutreachRecipient.campaign_id == campaign.id,
            )
            .order_by(OutreachRecipient.created_at, OutreachRecipient.id)
        ).all()
    )


def refresh_campaign_status(db: Session, campaign: OutreachCampaign) -> str:
    if campaign.status in {"sending", "sent", "simulated", "partial", "failed", "cancelled"}:
        return campaign.status
    recipients = campaign_recipients(db, campaign)
    if not recipients or any(item.status == "research_only" for item in recipients):
        campaign.status = "research"
    elif all(item.status == "drafted" and item.professional_email_id for item in recipients):
        campaign.status = "ready"
    else:
        campaign.status = "preparing"
    return campaign.status


def create_outreach_campaign(
    db: Session,
    *,
    settings: Settings,
    account_id: str,
    space_id: str,
    member_id: str,
    source_message_id: str | None,
    name: str,
    landing_url: str,
    candidates: list[dict],
) -> OutreachCampaign:
    if not settings.outreach_enabled:
        raise OutreachError("outreach_not_enabled")
    if not candidates or len(candidates) > settings.outreach_max_recipients:
        raise OutreachError("invalid_recipient_count")
    space = db.scalar(select(Space).where(Space.id == space_id, Space.account_id == account_id))
    studio = db.scalar(
        select(Conversation).where(
            Conversation.account_id == account_id,
            Conversation.space_id == space_id,
            Conversation.kind == "studio",
        )
    )
    if not space or not studio:
        raise OutreachError("space_not_found")

    campaign = OutreachCampaign(
        account_id=account_id,
        space_id=space_id,
        studio_conversation_id=studio.id,
        source_message_id=source_message_id,
        name=_clean(name, maximum=200, error="invalid_campaign_name"),
        landing_url=_https_url(
            landing_url,
            error="invalid_laggente_landing_url",
            base_domain=settings.base_domain,
        ),
        status="research",
        recipient_cap=settings.outreach_max_recipients,
    )
    db.add(campaign)
    db.flush()
    seen: set[str] = set()
    retention_until = utcnow() + timedelta(days=settings.outreach_candidate_retention_days)
    for raw in candidates:
        if not isinstance(raw, dict):
            raise OutreachError("invalid_candidate")
        email_value = raw.get("email")
        email = normalize_address(str(email_value)).lower() if email_value else None
        dedupe_key = email.lower() if email else _clean(
            str(raw.get("source_url") or ""), maximum=1000, error="invalid_source_url"
        )
        if dedupe_key in seen:
            raise OutreachError("duplicate_candidate")
        seen.add(dedupe_key)
        recipient = OutreachRecipient(
            account_id=account_id,
            space_id=space_id,
            campaign_id=campaign.id,
            name=_clean(str(raw.get("name") or ""), maximum=200, error="invalid_candidate_name"),
            email=email,
            source_url=_https_url(
                str(raw.get("source_url") or ""), error="invalid_source_url"
            ),
            source_label=(
                _clean(
                    str(raw["source_label"]),
                    maximum=300,
                    error="invalid_source_label",
                )
                if raw.get("source_label")
                else None
            ),
            personalization_note=(
                _clean(
                    str(raw["personalization_note"]),
                    maximum=2000,
                    error="invalid_personalization_note",
                )
                if raw.get("personalization_note")
                else None
            ),
            permission_basis="not_recorded",
            status="research_only",
            retention_until=retention_until,
        )
        db.add(recipient)
    db.flush()
    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            conversation_id=studio.id,
            actor_type="studio_assistant",
            actor_id="studio_assistant",
            event_type="outreach_campaign_researched",
            payload={
                "campaign_id": campaign.id,
                "candidate_count": len(candidates),
                "send_allowed": False,
                "requires_recorded_permission": True,
            },
        )
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def record_outreach_permission(
    db: Session,
    *,
    account_id: str,
    space_id: str,
    member_id: str,
    source_message_id: str | None,
    recipient_id: str,
    basis: str,
    evidence: str,
) -> OutreachCampaign:
    normalized_basis = basis.strip().lower()
    if normalized_basis not in OUTREACH_PERMISSION_BASES:
        raise OutreachError("invalid_permission_basis")
    recipient = db.scalar(
        select(OutreachRecipient).where(
            OutreachRecipient.id == recipient_id,
            OutreachRecipient.account_id == account_id,
            OutreachRecipient.space_id == space_id,
        )
    )
    if not recipient or not recipient.email:
        raise OutreachError("recipient_email_required")
    campaign = _owned_campaign(
        db,
        campaign_id=recipient.campaign_id,
        account_id=account_id,
        space_id=space_id,
    )
    if not campaign:
        raise OutreachError("campaign_not_found")
    attestation = db.scalar(
        select(Message).where(
            Message.id == source_message_id,
            Message.account_id == account_id,
            Message.conversation_id == campaign.studio_conversation_id,
            Message.author_type == "professional",
        )
    )
    if not attestation:
        raise OutreachError("current_professional_attestation_required")
    evidence = _clean(evidence, maximum=2000, error="permission_evidence_required")
    if len(evidence) < 12:
        raise OutreachError("permission_evidence_required")
    recipient.permission_basis = normalized_basis
    recipient.permission_evidence = evidence
    recipient.permission_recorded_by_member_id = member_id
    recipient.permission_source_message_id = source_message_id
    recipient.permission_recorded_at = utcnow()
    recipient.status = "eligible"
    recipient.retention_until = utcnow() + timedelta(days=365)
    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            conversation_id=campaign.studio_conversation_id,
            actor_type="professional",
            actor_id=member_id,
            event_type="outreach_permission_recorded",
            payload={
                "campaign_id": campaign.id,
                "recipient_id": recipient.id,
                "basis": normalized_basis,
                "source_message_id": source_message_id,
            },
        )
    )
    refresh_campaign_status(db, campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def address_is_suppressed(db: Session, *, account_id: str, email: str) -> bool:
    if db.scalar(
        select(OutreachSuppression.id).where(
            OutreachSuppression.account_id == account_id,
            OutreachSuppression.email == email,
        )
    ):
        return True
    return bool(
        db.scalar(
            select(ProfessionalEmail.id)
            .where(
                ProfessionalEmail.account_id == account_id,
                ProfessionalEmail.to_address == email,
                ProfessionalEmail.status.in_(TERMINAL_SUPPRESSION_STATUSES),
            )
            .limit(1)
        )
    )


def prepare_outreach_email(
    db: Session,
    *,
    settings: Settings,
    account_id: str,
    space_id: str,
    member_id: str,
    source_message_id: str | None,
    recipient_id: str,
    subject: str,
    body: str,
) -> OutreachCampaign:
    recipient = db.scalar(
        select(OutreachRecipient).where(
            OutreachRecipient.id == recipient_id,
            OutreachRecipient.account_id == account_id,
            OutreachRecipient.space_id == space_id,
        )
    )
    if not recipient or not recipient.email:
        raise OutreachError("recipient_not_found")
    if recipient.permission_basis not in OUTREACH_PERMISSION_BASES or recipient.status not in {
        "eligible",
        "drafted",
    }:
        raise OutreachError("recipient_permission_required")
    if address_is_suppressed(db, account_id=account_id, email=recipient.email):
        recipient.status = "suppressed"
        db.commit()
        raise OutreachError("recipient_suppressed")
    campaign = _owned_campaign(
        db,
        campaign_id=recipient.campaign_id,
        account_id=account_id,
        space_id=space_id,
    )
    if not campaign or campaign.status in {"sending", "sent", "simulated", "partial"}:
        raise OutreachError("campaign_not_editable")
    if campaign.landing_url not in body:
        raise OutreachError("landing_url_required_in_body")

    token = secrets.token_urlsafe(32)
    recipient.unsubscribe_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    unsubscribe_url = f"{settings.app_origin.rstrip('/')}/outreach/unsubscribe#token={token}"
    try:
        email = create_outbound_email_draft(
            db,
            account_id=account_id,
            space_id=space_id,
            member_id=member_id,
            source_message_id=source_message_id,
            recipient=recipient.email,
            subject=subject,
            body=body,
            from_domain=settings.agent_mail_from_domain,
            reply_domain=settings.agent_mail_reply_domain,
            footer_lines=[
                "Comunicazione promozionale con base di contatto registrata dal professionista.",
                f"Per non ricevere altri messaggi: {unsubscribe_url}",
                f"Informativa: https://{settings.base_domain}/privacy",
            ],
            supersede_pending=False,
            outreach_campaign_id=campaign.id,
            outreach_recipient_id=recipient.id,
            commit=False,
        )
    except ProfessionalEmailError as exc:
        raise OutreachError(str(exc)) from exc
    previous_id = recipient.professional_email_id
    if previous_id and previous_id != email.id:
        previous = db.get(ProfessionalEmail, previous_id)
        if previous and previous.status == "draft":
            previous.status = "superseded"
    recipient.professional_email_id = email.id
    recipient.status = "drafted"
    refresh_campaign_status(db, campaign)
    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            conversation_id=campaign.studio_conversation_id,
            actor_type="studio_assistant",
            actor_id="studio_assistant",
            event_type="outreach_email_proposed",
            payload={
                "campaign_id": campaign.id,
                "recipient_id": recipient.id,
                "email_id": email.id,
                "requires_campaign_authorization": True,
            },
        )
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def register_unsubscribe(db: Session, token: str) -> bool:
    if not token or len(token) > 200:
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    recipient = db.scalar(
        select(OutreachRecipient).where(
            OutreachRecipient.unsubscribe_token_hash == token_hash
        )
    )
    if not recipient or not recipient.email:
        return False
    existing = db.scalar(
        select(OutreachSuppression).where(
            OutreachSuppression.account_id == recipient.account_id,
            OutreachSuppression.email == recipient.email,
        )
    )
    if not existing:
        db.add(
            OutreachSuppression(
                account_id=recipient.account_id,
                email=recipient.email,
                reason="recipient_unsubscribed",
                source="opaque_token_link",
            )
        )
    recipient.unsubscribe_requested_at = utcnow()
    recipient.status = "suppressed"
    db.commit()
    return True


def purge_expired_outreach_candidates(db: Session) -> int:
    expired = list(
        db.scalars(
            select(OutreachRecipient).where(
                OutreachRecipient.status == "research_only",
                OutreachRecipient.retention_until < utcnow(),
            )
        ).all()
    )
    for recipient in expired:
        db.delete(recipient)
    if expired:
        db.commit()
    return len(expired)
