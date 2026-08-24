import type { ProfessionalSpace } from "@/lib/types";
import { PRIVACY_NOTICE_VERSION } from "@/lib/privacy";

export function emptySpace(slug: string): ProfessionalSpace {
  return {
    slug,
    professional_name: "Spazio professionale",
    professional_role: "Professionista",
    agency: null,
    territory: null,
    hero_image_url: "/images/laggente-hero.webp",
    welcome_message: "",
    assistant_disclosure: "LAGGENTE — assistente AI",
    privacy_notice_version: PRIVACY_NOTICE_VERSION,
    capabilities: { text: true, voice_notes: false, photographs: false },
    suggested_prompts: [],
  };
}

export function normalizeSpace(value: unknown, slug: string): ProfessionalSpace {
  const object = (value || {}) as Record<string, unknown>;
  const candidate = (object.space && typeof object.space === "object" ? object.space : object) as Partial<ProfessionalSpace>;
  const configuration = (object.configuration && typeof object.configuration === "object" ? object.configuration : {}) as Record<string, unknown>;
  const identity = (configuration.identity && typeof configuration.identity === "object" ? configuration.identity : {}) as Record<string, unknown>;
  const presentation = (configuration.public && typeof configuration.public === "object" ? configuration.public : {}) as Record<string, unknown>;
  const capabilities = (configuration.capabilities && typeof configuration.capabilities === "object" ? configuration.capabilities : {}) as Record<string, unknown>;
  const fallback = emptySpace(slug);
  return {
    ...fallback,
    ...candidate,
    slug: candidate.slug || slug,
    professional_name: String(identity.name || candidate.professional_name || fallback.professional_name),
    professional_role: String(identity.role || candidate.professional_role || object.public_role || fallback.professional_role),
    agency: String(identity.agency || candidate.agency || object.agency || fallback.agency || "") || null,
    territory: String(identity.territory || candidate.territory || object.territory || fallback.territory || "") || null,
    welcome_message: String(candidate.welcome_message || presentation.welcome || fallback.welcome_message),
    assistant_disclosure: String(candidate.assistant_disclosure || object.ai_label || fallback.assistant_disclosure),
    privacy_notice_version: String(candidate.privacy_notice_version || object.privacy_notice_version || fallback.privacy_notice_version),
    capabilities: {
      text: capabilities.text !== false && candidate.capabilities?.text !== false,
      voice_notes: Boolean(capabilities.voice_notes ?? candidate.capabilities?.voice_notes ?? fallback.capabilities.voice_notes),
      photographs: Boolean(capabilities.photographs ?? candidate.capabilities?.photographs ?? fallback.capabilities.photographs),
    },
  };
}
