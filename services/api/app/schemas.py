from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

MAX_CONFIGURATION_DOCUMENT_BYTES = 64_000


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IdentityConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="agente immobiliare", max_length=100)
    agency: str | None = Field(default=None, max_length=200)
    territory: str | None = Field(default=None, max_length=300)


class PublicPresentationConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    headline: str = Field(min_length=1, max_length=500)
    welcome: str = Field(min_length=1, max_length=1200)


class AssistantBehaviorConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    tone: list[str] = Field(default_factory=list, max_length=20)
    guidance: list[str] = Field(default_factory=list, max_length=50)
    boundaries: list[str] = Field(default_factory=list, max_length=50)
    invitation_preferences: list[str] = Field(default_factory=list, max_length=30)


class CapabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Text conversation is a platform invariant, not a tenant-disableable capability.
    text: Literal[True] = True
    voice_notes: bool = False
    photographs: bool = False


class SpaceConfigEnvelope(BaseModel):
    """Typed platform envelope with extensible professional meaning."""

    model_config = ConfigDict(extra="allow")
    schema_version: Literal[1] = 1
    locale: Literal["it-IT"] = "it-IT"
    identity: IdentityConfig
    public: PublicPresentationConfig
    assistant: AssistantBehaviorConfig
    capabilities: CapabilityConfig = Field(default_factory=CapabilityConfig)
    knowledge: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    notice: list[str] = Field(default_factory=list, max_length=50)
    template: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


class MemberOut(APIModel):
    id: str
    account_id: str
    email: EmailStr
    display_name: str
    role: str


class SessionOut(APIModel):
    authenticated: bool = True
    member: MemberOut


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkRequestOut(BaseModel):
    accepted: bool = True
    message: str = "Se l'indirizzo è autorizzato, riceverai un link di accesso."
    development_magic_link: str | None = None


class MagicLinkConsume(BaseModel):
    token: str = Field(min_length=20, max_length=1000)


class PilotPasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=300)


class SpaceOut(APIModel):
    id: str
    account_id: str
    slug: str
    professional_name: str
    agency: str | None
    territory: str | None
    public_role: str
    locale: str
    is_active: bool
    active_revision_id: str | None


class RevisionCreate(BaseModel):
    document: SpaceConfigEnvelope
    rationale: str | None = Field(default=None, max_length=2000)


class RevisionOut(APIModel):
    id: str
    account_id: str
    space_id: str
    revision_number: int
    status: str
    document: dict[str, Any]
    rationale: str | None
    proposed_by_member_id: str | None
    activated_by_member_id: str | None
    activated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SpaceDetail(BaseModel):
    space: SpaceOut
    active_revision: RevisionOut | None
    latest_draft: RevisionOut | None


AuthorType = Literal["visitor", "professional", "studio_assistant", "public_assistant", "system"]


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=12_000)
    client_message_id: str | None = Field(default=None, max_length=100)
    attachment_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def content_or_attachment(self):
        self.content = self.content.strip()
        if not self.content and not self.attachment_id:
            raise ValueError("Il messaggio o un allegato è obbligatorio")
        return self


class MessageAttachmentOut(BaseModel):
    """Public-safe attachment metadata embedded in a durable message."""

    id: str
    kind: Literal["image", "audio"]
    name: str | None = None
    url: str | None = None


class MessageOut(APIModel):
    id: str
    account_id: str
    conversation_id: str
    author_type: str
    author_label: str
    content: str
    content_type: str
    client_message_id: str | None
    created_at: datetime
    attachment: MessageAttachmentOut | None = None


class ConversationOut(APIModel):
    id: str
    account_id: str
    space_id: str
    kind: str
    title: str | None
    automatic_ai_enabled: bool
    professional_joined: bool
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
    memories: list["MemoryOut"] = Field(default_factory=list)
    latest_email: "ProfessionalEmailOut | None" = None


class StudioTurnOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
    proposed_revision: RevisionOut | None = None
    proposed_email: "ProfessionalEmailOut | None" = None


class ProfessionalEmailOut(APIModel):
    id: str
    direction: Literal["outbound", "inbound"]
    status: str
    from_address: EmailStr
    to_address: EmailStr
    reply_to_address: EmailStr | None
    subject: str
    body_text: str
    raw_sha256: str
    content_sha256: str
    internet_message_id: str | None
    provider: str | None
    provider_message_id: str | None
    in_reply_to_email_id: str | None
    authorized_at: datetime | None
    sent_at: datetime | None
    received_at: datetime | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime


class InboundProfessionalEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: EmailStr
    receipt_id: str = Field(min_length=1, max_length=998)
    raw_base64: str = Field(min_length=1)
    received_at: datetime | None = None


class PublicSpaceOut(BaseModel):
    slug: str
    professional_name: str
    agency: str | None
    territory: str | None
    public_role: str
    locale: str
    ai_label: str
    privacy_notice_version: str
    configuration: dict[str, Any]


class PublicConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    privacy_notice_version: str | None = Field(default=None, max_length=50)
    privacy_notice_acknowledged: bool = False


class PublicConversationCreated(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
    continuation_token: str


class PublicTurnOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
    automatic_reply_generated: bool


MemoryKind = Literal["summary", "fact", "preference", "open_question", "signal", "suggested_action"]


class MemoryOut(APIModel):
    id: str
    account_id: str
    space_id: str
    conversation_id: str
    kind: str
    content: str
    source_message_ids: list[str]
    status: str
    corrected_content: str | None
    created_at: datetime
    updated_at: datetime


class MemoryUpdate(BaseModel):
    corrected_content: str | None = Field(
        default=None,
        validation_alias=AliasChoices("corrected_content", "content"),
        min_length=1,
        max_length=4000,
    )
    status: Literal["active", "corrected", "dismissed"] = "corrected"


class AutoReplyUpdate(BaseModel):
    enabled: bool = Field(validation_alias=AliasChoices("enabled", "automatic_replies_enabled"))


class PublicMemoryProposal(BaseModel):
    kind: MemoryKind
    content: str = Field(min_length=1, max_length=2000)
    source_message_ids: list[str] = Field(default_factory=list, max_length=20)


class PublicAgentOutput(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)
    summary: str = Field(min_length=1, max_length=2000)
    memory_items: list[PublicMemoryProposal] = Field(default_factory=list, max_length=8)


class AttachmentOut(APIModel):
    id: str
    conversation_id: str
    original_name: str
    media_type: str
    size_bytes: int
    transcript: str | None
    status: str
    created_at: datetime


class AttachmentCreated(BaseModel):
    attachment: AttachmentOut
    transcript: str | None = None
    download_url: str | None = None


class VersionOut(BaseModel):
    service: str = "laggente-api"
    version: str
    git_sha: str
