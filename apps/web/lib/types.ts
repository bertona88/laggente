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

export interface StudioBootstrap {
  professional_name: string;
  space_slug: string;
  studio_conversation_id: string;
  studio_messages: ConversationMessage[];
  active_revision?: ConfigRevision | null;
  proposed_revision?: ConfigRevision | null;
  latest_email?: ProfessionalEmail | null;
}

export interface ApiErrorBody {
  detail?: string | { msg?: string }[];
  message?: string;
}
