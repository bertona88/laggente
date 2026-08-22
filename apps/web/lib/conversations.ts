import type { ConversationSummary } from "@/lib/types";

export function normalizeConversationSummary(value: unknown): ConversationSummary {
  const object = (value || {}) as Record<string, unknown>;
  const conversation = (object.conversation && typeof object.conversation === "object" ? object.conversation : object) as Record<string, unknown>;
  const visitor = object.visitor as Record<string, unknown> | undefined;
  const lastMessage = (object.last_message && typeof object.last_message === "object" ? object.last_message : null) as Record<string, unknown> | null;
  return {
    id: String(conversation.id || object.conversation_id || ""),
    visitor_name: String(object.visitor_name || visitor?.name || "") || null,
    visitor_label: String(object.visitor_label || conversation.title || object.title || "") || null,
    summary: String(object.summary || "") || null,
    last_message: String(lastMessage?.content || (typeof object.last_message === "string" ? object.last_message : object.latest_message) || "") || null,
    last_message_at: String(lastMessage?.created_at || conversation.last_message_at || object.updated_at || conversation.created_at || new Date().toISOString()),
    attention_reason: String(object.attention_reason || "") || null,
    professional_present: Boolean(object.professional_present ?? conversation.professional_joined),
    automatic_replies_enabled: (object.automatic_replies_enabled ?? conversation.automatic_ai_enabled) !== false,
  };
}
