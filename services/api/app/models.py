from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Member(Base, TimestampMixin):
    __tablename__ = "members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    # Pilot authentication is email-first before tenant context exists, so email is globally unique.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="professional", nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Invitation is a platform permission. Existing pilot operators receive it through the
    # provisioning migration; professionals created by an invitation do not inherit it.
    can_invite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    account: Mapped[Account] = relationship()


class Space(Base, TimestampMixin):
    __tablename__ = "spaces"
    __table_args__ = (UniqueConstraint("slug", name="uq_space_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    professional_name: Mapped[str] = mapped_column(String(200), nullable=False)
    agency: Mapped[str | None] = mapped_column(String(200))
    territory: Mapped[str | None] = mapped_column(String(300))
    public_role: Mapped[str] = mapped_column(String(100), default="professionista", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="it-IT", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    slug_claimed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    onboarding_state: Mapped[str] = mapped_column(
        String(24), default="published", nullable=False
    )
    active_revision_id: Mapped[str | None] = mapped_column(String(36), index=True)


class ConfigRevision(Base, TimestampMixin):
    __tablename__ = "config_revisions"
    __table_args__ = (
        UniqueConstraint("space_id", "revision_number", name="uq_space_revision_number"),
        Index("ix_config_revision_account_space", "account_id", "space_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    proposed_by_member_id: Mapped[str | None] = mapped_column(String(36))
    activated_by_member_id: Mapped[str | None] = mapped_column(String(36))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversation_account_space", "account_id", "space_id"),
        Index("ix_conversation_account_kind", "account_id", "kind"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str | None] = mapped_column(String(240))
    visitor_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    automatic_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    professional_joined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_message_account_conversation", "account_id", "conversation_id"),
        UniqueConstraint("conversation_id", "client_message_id", name="uq_conversation_client_message"),
        UniqueConstraint("reply_to_message_id", name="uq_message_reply_to"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    author_type: Mapped[str] = mapped_column(String(32), nullable=False)
    author_label: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), default="text", nullable=False)
    client_message_id: Mapped[str | None] = mapped_column(String(100))
    model_response_id: Mapped[str | None] = mapped_column(String(100))
    assistant_reply_state: Mapped[str | None] = mapped_column(String(24))
    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MemoryItem(Base, TimestampMixin):
    __tablename__ = "memory_items"
    __table_args__ = (Index("ix_memory_account_conversation", "account_id", "conversation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    corrected_content: Mapped[str | None] = mapped_column(Text)
    corrected_by_member_id: Mapped[str | None] = mapped_column(String(36))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_event_account_created", "account_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    space_id: Mapped[str | None] = mapped_column(String(36), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MagicLink(Base):
    __tablename__ = "magic_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(40), default="login", nullable=False, index=True)
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SignupLink(Base):
    """Pre-tenant proof that a professional controls an email address.

    No account is created until this purpose-bound link is consumed. This keeps automated signup
    requests from allocating tenant data while retaining single-use and expiry enforcement.
    """

    __tablename__ = "signup_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachment_account_conversation", "account_id", "conversation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(String(36), index=True)
    uploader_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Document(Base, TimestampMixin):
    """A private source file with an application-owned access and activation lifecycle."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_document_account_space_scope", "account_id", "space_id", "scope"),
        Index("ix_document_account_conversation", "account_id", "conversation_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    uploader_type: Mapped[str] = mapped_column(String(32), nullable=False)
    uploader_id: Mapped[str | None] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ready", nullable=False)


class OutreachCampaign(Base, TimestampMixin):
    """A bounded, human-authorized outreach action; not a lead pipeline."""

    __tablename__ = "outreach_campaigns"
    __table_args__ = (Index("ix_outreach_campaign_account_space", "account_id", "space_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="CASCADE"), index=True
    )
    studio_conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    landing_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="research", nullable=False)
    recipient_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    authorized_by_member_id: Mapped[str | None] = mapped_column(String(36))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutreachRecipient(Base, TimestampMixin):
    """One sourced campaign candidate with an independent permission gate."""

    __tablename__ = "outreach_recipients"
    __table_args__ = (
        Index("ix_outreach_recipient_account_campaign", "account_id", "campaign_id"),
        UniqueConstraint("campaign_id", "email", name="uq_outreach_campaign_email"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_label: Mapped[str | None] = mapped_column(String(300))
    personalization_note: Mapped[str | None] = mapped_column(Text)
    permission_basis: Mapped[str] = mapped_column(
        String(48), default="not_recorded", nullable=False
    )
    permission_evidence: Mapped[str | None] = mapped_column(Text)
    permission_recorded_by_member_id: Mapped[str | None] = mapped_column(String(36))
    permission_source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    permission_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="research_only", nullable=False)
    unsubscribe_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True
    )
    unsubscribe_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    professional_email_id: Mapped[str | None] = mapped_column(String(36), index=True)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutreachSuppression(Base):
    __tablename__ = "outreach_suppressions"
    __table_args__ = (
        UniqueConstraint("account_id", "email", name="uq_outreach_suppression_email"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProfessionalEmail(Base, TimestampMixin):
    """An immutable email artifact plus its application-owned delivery state."""

    __tablename__ = "professional_emails"
    __table_args__ = (
        Index("ix_professional_email_account_space", "account_id", "space_id"),
        UniqueConstraint(
            "provider", "provider_message_id", name="uq_professional_email_provider_message"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="CASCADE"), index=True
    )
    studio_conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    in_reply_to_email_id: Mapped[str | None] = mapped_column(
        ForeignKey("professional_emails.id", ondelete="SET NULL"), index=True
    )
    outreach_campaign_id: Mapped[str | None] = mapped_column(
        ForeignKey("outreach_campaigns.id", ondelete="SET NULL"), index=True
    )
    outreach_recipient_id: Mapped[str | None] = mapped_column(
        ForeignKey("outreach_recipients.id", ondelete="SET NULL"), index=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    reply_to_address: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    internet_message_id: Mapped[str | None] = mapped_column(String(998))
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(998))
    proposed_by_member_id: Mapped[str | None] = mapped_column(String(36))
    authorized_by_member_id: Mapped[str | None] = mapped_column(String(36))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(120))
