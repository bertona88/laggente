import type { ProfessionalEmail } from "@/lib/types";

export function normalizeProfessionalEmail(value: unknown): ProfessionalEmail | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const direction = record.direction;
  if (
    typeof record.id !== "string"
    || (direction !== "outbound" && direction !== "inbound")
    || typeof record.status !== "string"
    || typeof record.from_address !== "string"
    || typeof record.to_address !== "string"
    || typeof record.subject !== "string"
    || typeof record.body_text !== "string"
    || typeof record.raw_sha256 !== "string"
    || typeof record.content_sha256 !== "string"
  ) return null;
  return {
    id: record.id,
    direction,
    status: record.status,
    from_address: record.from_address,
    to_address: record.to_address,
    reply_to_address: typeof record.reply_to_address === "string" ? record.reply_to_address : null,
    subject: record.subject,
    body_text: record.body_text,
    raw_sha256: record.raw_sha256,
    content_sha256: record.content_sha256,
    provider: typeof record.provider === "string" ? record.provider : null,
    provider_message_id: typeof record.provider_message_id === "string" ? record.provider_message_id : null,
    authorized_at: typeof record.authorized_at === "string" ? record.authorized_at : null,
    sent_at: typeof record.sent_at === "string" ? record.sent_at : null,
    received_at: typeof record.received_at === "string" ? record.received_at : null,
    created_at: typeof record.created_at === "string" ? record.created_at : new Date(0).toISOString(),
  };
}
