import { normalizeProfessionalEmail } from "@/lib/professional-email";
import type { OutreachCampaign, OutreachRecipient } from "@/lib/types";

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? value as Record<string, unknown> : null;
}

function normalizeRecipient(value: unknown): OutreachRecipient | null {
  const item = record(value);
  if (!item || typeof item.id !== "string" || typeof item.name !== "string" || typeof item.source_url !== "string") return null;
  return {
    id: item.id,
    campaign_id: String(item.campaign_id || ""),
    name: item.name,
    email: typeof item.email === "string" ? item.email : null,
    source_url: item.source_url,
    source_label: typeof item.source_label === "string" ? item.source_label : null,
    personalization_note: typeof item.personalization_note === "string" ? item.personalization_note : null,
    permission_basis: String(item.permission_basis || "not_recorded"),
    permission_evidence: typeof item.permission_evidence === "string" ? item.permission_evidence : null,
    status: String(item.status || "research_only"),
    unsubscribe_requested_at: typeof item.unsubscribe_requested_at === "string" ? item.unsubscribe_requested_at : null,
    retention_until: String(item.retention_until || ""),
    professional_email: normalizeProfessionalEmail(item.professional_email),
    created_at: String(item.created_at || ""),
    updated_at: String(item.updated_at || ""),
  };
}

export function normalizeOutreachCampaign(value: unknown): OutreachCampaign | null {
  const item = record(value);
  if (!item || typeof item.id !== "string" || typeof item.name !== "string" || typeof item.landing_url !== "string") return null;
  const recipients = Array.isArray(item.recipients)
    ? item.recipients.map(normalizeRecipient).filter((entry): entry is OutreachRecipient => Boolean(entry))
    : [];
  return {
    id: item.id,
    name: item.name,
    landing_url: item.landing_url,
    status: String(item.status || "research"),
    recipient_cap: Number(item.recipient_cap || 0),
    authorized_at: typeof item.authorized_at === "string" ? item.authorized_at : null,
    completed_at: typeof item.completed_at === "string" ? item.completed_at : null,
    recipients,
    created_at: String(item.created_at || ""),
    updated_at: String(item.updated_at || ""),
  };
}
