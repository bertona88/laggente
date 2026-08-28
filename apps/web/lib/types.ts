export type AuthorType =
  | "visitor"
  | "public_assistant"
  | "studio_assistant"
  | "professional"
  | "system";

export interface ConversationAttachment {
  id: string;
  kind: "image" | "audio";
  name?: string;
  url?: string;
}

export interface ProfessionalSpace {
  slug: string;
  professional_name: string;
  professional_role: string;
  agency?: string | null;
  territory?: string | null;
  portrait_url?: string | null;
  hero_image_url?: string | null;
  welcome_message: string;
  assistant_disclosure: string;
  privacy_notice_version: string;
  capabilities: {
    text: boolean;
    voice_notes: boolean;
    photographs: boolean;
  };
  suggested_prompts?: string[];
  active_revision_id?: string | null;
}

export interface FeaturedVertical {
  id: string;
  label: string;
  weight: number;
  status: "pilot" | "example" | "available";
  template_id?: string | null;
  example_answer: string;
  headline: string;
  description: string;
}

export interface ProductPositioning {
  audience: string;
  opening_question: string;
  featured_verticals: FeaturedVertical[];
}

export interface RelationshipGraphNode {
  id: string;
  type: "professional" | "person" | "set";
  label: string;
  summary: string;
  conversation_id?: string | null;
  member_count: number;
  weight: number;
  origin: "primary" | "derived";
}

export interface RelationshipGraphEdge {
  id: string;
  source: string;
  target: string;
  relation: "conversation" | "member_of";
  weight: number;
}

export interface RelationshipGraph {
  center_id: string;
  nodes: RelationshipGraphNode[];
  edges: RelationshipGraphEdge[];
  profile: {
    vertical_id?: string | null;
    vertical_label?: string | null;
    template_id?: string | null;
    source: "backend_positioning" | "generic";
  };
  bounds: Record<string, number>;
}

export interface ConversationMessage {
  id: string;
  author_type: AuthorType;
  author_name: string;
  content: string;
  created_at: string;
  pending?: boolean;
  attachment?: ConversationAttachment | null;
}

export interface PublicConversation {
  id: string;
  space_slug: string;
  messages: ConversationMessage[];
  automatic_replies_enabled?: boolean;
  professional_present?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ConversationSummary {
  id: string;
  visitor_name?: string | null;
  visitor_label?: string | null;
  summary?: string | null;
  last_message?: string | null;
  last_message_at: string;
  attention_reason?: string | null;
  professional_present?: boolean;
  automatic_replies_enabled?: boolean;
}

export interface MemoryItem {
  id: string;
  kind: "fact" | "preference" | "question" | "signal" | "summary" | string;
  label?: string | null;
  content: string;
  corrected_content?: string | null;
  confidence?: number | null;
  source_message_ids?: string[];
  updated_at?: string;
}

export interface StudioConversationDetail extends PublicConversation {
  visitor_name?: string | null;
  summary?: string | null;
  attention_reason?: string | null;
  memory_items: MemoryItem[];
  professional_present: boolean;
  automatic_replies_enabled: boolean;
}

export type RevisionStatus = "draft" | "active" | "historical" | "proposed";

export interface ConfigSection {
  key: string;
  title: string;
  value: string | string[] | Record<string, unknown>;
  changed?: boolean;
}

export interface ConfigRevision {
  id: string;
  number?: number;
  status: RevisionStatus;
  title: string;
  summary?: string | null;
  created_at: string;
  sections: ConfigSection[];
  preview?: Partial<ProfessionalSpace> | null;
}

export type ProfessionalEmailStatus =
  | "draft"
  | "sending"
  | "sent"
  | "delivery_delayed"
  | "delivered"
  | "bounced"
  | "complained"
  | "suppressed"
  | "simulated"
  | "failed"
  | "superseded"
  | "received";

export interface ProfessionalEmail {
  id: string;
  direction: "outbound" | "inbound";
  status: ProfessionalEmailStatus | string;
  from_address: string;
  to_address: string;
  reply_to_address?: string | null;
  subject: string;
  body_text: string;
  raw_sha256: string;
  content_sha256: string;
  provider?: string | null;
  provider_message_id?: string | null;
  authorized_at?: string | null;
  sent_at?: string | null;
  received_at?: string | null;
  created_at: string;
}

export interface OutreachRecipient {
  id: string;
  campaign_id: string;
  name: string;
  email?: string | null;
  source_url: string;
  source_label?: string | null;
  personalization_note?: string | null;
  permission_basis: "not_recorded" | "explicit_consent" | "existing_customer_similar_services" | string;
  permission_evidence?: string | null;
  status: string;
  unsubscribe_requested_at?: string | null;
  retention_until: string;
  professional_email?: ProfessionalEmail | null;
  created_at: string;
  updated_at: string;
}

export interface OutreachCampaign {
  id: string;
  name: string;
  landing_url: string;
  status: "research" | "preparing" | "ready" | "sending" | "sent" | "simulated" | "partial" | "failed" | string;
  recipient_cap: number;
  authorized_at?: string | null;
  completed_at?: string | null;
  recipients: OutreachRecipient[];
  created_at: string;
  updated_at: string;
}

export interface StudioBootstrap {
  professional_name: string;
  space_slug: string;
  studio_conversation_id: string;
  studio_messages: ConversationMessage[];
  active_revision?: ConfigRevision | null;
  proposed_revision?: ConfigRevision | null;
  latest_email?: ProfessionalEmail | null;
  latest_campaign?: OutreachCampaign | null;
}

export interface StudioMember {
  id: string;
  account_id: string;
  email: string;
  display_name: string;
  role: string;
  can_invite: boolean;
}

export interface StudioSpaceState {
  id: string;
  account_id: string;
  slug: string;
  professional_name: string;
  agency?: string | null;
  territory?: string | null;
  public_role: string;
  locale: string;
  is_active: boolean;
  slug_claimed: boolean;
  onboarding_state: "invited" | "building" | "published" | string;
  active_revision_id?: string | null;
}

export interface StudioSession {
  authenticated: boolean;
  member: StudioMember;
  space: StudioSpaceState | null;
}

export interface ApiErrorBody {
  detail?: string | { msg?: string }[];
  message?: string;
}
