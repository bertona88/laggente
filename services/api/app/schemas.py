from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

MAX_CONFIGURATION_DOCUMENT_BYTES = 64_000


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IdentityConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=100)
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
    can_invite: bool


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkRequestOut(BaseModel):
    accepted: bool = True
    message: str = (
        "Abbiamo inviato un link per entrare o creare il tuo Studio. "
        "Controlla anche la cartella Spam."
    )
    development_magic_link: str | None = None


class MagicLinkConsume(BaseModel):
    token: str = Field(min_length=20, max_length=1000)


class ProfessionalInvitationCreate(BaseModel):
    email: EmailStr


class ProfessionalInvitationOut(BaseModel):
    accepted: bool = True
    email: EmailStr
    status: Literal["sent", "resent"]
    expires_at: datetime
    development_magic_link: str | None = None


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
    slug_claimed: bool
    onboarding_state: str
    active_revision_id: str | None


class SessionOut(APIModel):
    authenticated: bool = True
    member: MemberOut
    space: SpaceOut | None = None


class SlugAvailabilityOut(BaseModel):
    slug: str
    available: bool


class SlugClaim(BaseModel):
    slug: str = Field(min_length=1, max_length=63)


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


class CalendarConnectionOut(APIModel):
    connected: bool = True
    provider: Literal["google"] = "google"
    provider_email: EmailStr
    status: str
    booking_enabled: bool
    timezone: str
    work_days: list[int]
    day_start: str
    day_end: str
    duration_minutes: int
    slot_interval_minutes: int
    buffer_minutes: int
    minimum_notice_minutes: int
    appointment_title: str
    location: str | None
    updated_at: datetime


class CalendarStatusOut(BaseModel):
    available: bool
    connection: CalendarConnectionOut | None = None


class CalendarOAuthStartOut(BaseModel):
    authorization_url: str


class CalendarSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    booking_enabled: bool
    timezone: str = Field(min_length=1, max_length=80)
    work_days: list[int] = Field(min_length=1, max_length=7)
    day_start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    day_end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: Literal[15, 30, 45, 60, 90, 120]
    slot_interval_minutes: Literal[15, 30, 60]
    buffer_minutes: int = Field(ge=0, le=120)
    minimum_notice_minutes: int = Field(ge=0, le=10_080)
    appointment_title: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_calendar_policy(self):
        if sorted(set(self.work_days)) != sorted(self.work_days) or any(
            day < 0 or day > 6 for day in self.work_days
        ):
            raise ValueError("I giorni prenotabili devono essere unici e compresi tra 0 e 6")
        if self.day_start >= self.day_end:
            raise ValueError("L'orario finale deve essere successivo a quello iniziale")
        return self


class CalendarSlotOut(BaseModel):
    start: datetime
    end: datetime
    timezone: str


class CalendarAvailabilityOut(BaseModel):
    appointment_title: str
    location: str | None
    slots: list[CalendarSlotOut]


class CalendarBookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_name: str = Field(min_length=2, max_length=200)
    visitor_email: EmailStr
    start: datetime


class CalendarBookingOut(APIModel):
    id: str
    conversation_id: str
    visitor_name: str
    visitor_email: EmailStr
    start_at: datetime
    end_at: datetime
    timezone: str
    status: str
    created_at: datetime


AuthorType = Literal["visitor", "professional", "studio_assistant", "public_assistant", "system"]


class MessageCreate(BaseModel):
    content: str = Field(default="", max_length=12_000)
    client_message_id: str | None = Field(default=None, max_length=100)
    attachment_id: str | None = Field(default=None, max_length=36)
    document_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def content_or_attachment(self):
        self.content = self.content.strip()
        if self.attachment_id and self.document_id:
            raise ValueError("Invia un solo allegato per messaggio")
        if not self.content and not self.attachment_id and not self.document_id:
            raise ValueError("Il messaggio o un allegato è obbligatorio")
        return self


class MessageAttachmentOut(BaseModel):
    """Public-safe attachment metadata embedded in a durable message."""

    id: str
    kind: Literal["image", "audio"]
    name: str | None = None
    url: str | None = None


class MessageDocumentOut(BaseModel):
    """Conversation-safe document metadata embedded in a durable message."""

    id: str
    name: str
    media_type: str
    size_bytes: int
    url: str


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
    document: MessageDocumentOut | None = None


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
    latest_campaign: "OutreachCampaignOut | None" = None


class StudioTurnOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]
    proposed_revision: RevisionOut | None = None
    proposed_email: "ProfessionalEmailOut | None" = None
    proposed_campaign: "OutreachCampaignOut | None" = None


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
    outreach_campaign_id: str | None
    outreach_recipient_id: str | None
    authorized_at: datetime | None
    sent_at: datetime | None
    received_at: datetime | None
    failure_code: str | None
    created_at: datetime
    updated_at: datetime


class OutreachRecipientOut(APIModel):
    id: str
    campaign_id: str
    name: str
    email: EmailStr | None
    source_url: str
    source_label: str | None
    personalization_note: str | None
    permission_basis: str
    permission_evidence: str | None
    status: str
    unsubscribe_requested_at: datetime | None
    retention_until: datetime
    professional_email: ProfessionalEmailOut | None = None
    created_at: datetime
    updated_at: datetime


class OutreachCampaignOut(APIModel):
    id: str
    name: str
    landing_url: str
    status: str
    recipient_cap: int
    authorized_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    recipients: list[OutreachRecipientOut] = Field(default_factory=list)


class OutreachUnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=200)


class OutreachUnsubscribeOut(BaseModel):
    accepted: bool = True
    message: str = "La richiesta è stata registrata."


class InboundProfessionalEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: EmailStr
    receipt_id: str = Field(min_length=1, max_length=998)
    raw_base64: str = Field(min_length=1)
    received_at: datetime | None = None


class ResendEmailReceivedData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email_id: str = Field(min_length=1, max_length=998)
    to: list[EmailStr] = Field(min_length=1, max_length=50)
    created_at: datetime | None = None


class ResendEmailDeliveryData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email_id: str = Field(min_length=1, max_length=998)
    tags: Any = None


class ResendWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str = Field(min_length=1, max_length=100)
    data: dict[str, Any]


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


class RelationshipGraphNode(BaseModel):
    id: str
    type: Literal["professional", "person", "set"]
    label: str
    summary: str
    conversation_id: str | None = None
    member_count: int = 0
    weight: int = 1
    origin: Literal["primary", "derived"]


class RelationshipGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: Literal["conversation", "member_of"]
    weight: int = 1


class RelationshipGraphProfile(BaseModel):
    vertical_id: str | None = None
    vertical_label: str | None = None
    template_id: str | None = None
    source: Literal["backend_positioning", "generic"]


class RelationshipGraphOut(BaseModel):
    center_id: str
    nodes: list[RelationshipGraphNode]
    edges: list[RelationshipGraphEdge]
    profile: RelationshipGraphProfile
    bounds: dict[str, int]


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


class DocumentOut(BaseModel):
    id: str
    conversation_id: str | None
    message_id: str | None
    scope: Literal["studio", "conversation"]
    uploader_type: Literal["visitor", "professional"]
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    extracted_characters: int
    public_state: Literal["private", "draft", "active"]
    download_url: str
    created_at: datetime
    updated_at: datetime


class DocumentCreated(BaseModel):
    document: DocumentOut


class DocumentPublicationProposal(BaseModel):
    enabled: bool


class DocumentPublicationProposalOut(BaseModel):
    document: DocumentOut
    revision: RevisionOut


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
