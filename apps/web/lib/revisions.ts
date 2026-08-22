import type { ConfigRevision, ConfigSection, ProfessionalSpace } from "@/lib/types";

export function normalizeRevision(value: unknown): ConfigRevision | null {
  if (!value || typeof value !== "object") return null;
  const object = value as Record<string, unknown>;
  const document = (object.document && typeof object.document === "object" ? object.document : null) as Record<string, unknown> | null;
  const rawSections = object.sections || document || (object.configuration && typeof object.configuration === "object" ? object.configuration : []);
  const sections: ConfigSection[] = Array.isArray(rawSections)
    ? rawSections as ConfigSection[]
    : Object.entries(rawSections as Record<string, unknown>).map(([key, sectionValue]) => ({
        key,
        title: key.replaceAll("_", " "),
        value: sectionValue as ConfigSection["value"],
      }));
  const identity = (document?.identity && typeof document.identity === "object" ? document.identity : {}) as Record<string, unknown>;
  const presentation = (document?.public && typeof document.public === "object" ? document.public : {}) as Record<string, unknown>;
  const suppliedPreview = (object.preview && typeof object.preview === "object" ? object.preview : {}) as Partial<ProfessionalSpace>;
  return {
    id: String(object.id || ""),
    number: typeof object.revision_number === "number" ? object.revision_number : typeof object.number === "number" ? object.number : undefined,
    status: (object.status as ConfigRevision["status"]) || "proposed",
    title: String(object.title || object.name || (object.revision_number ? `Versione ${object.revision_number}` : "Revisione dello spazio")),
    summary: typeof object.summary === "string" ? object.summary : typeof object.rationale === "string" ? object.rationale : null,
    created_at: String(object.created_at || new Date().toISOString()),
    sections,
    preview: {
      ...suppliedPreview,
      professional_name: suppliedPreview.professional_name || (identity.name ? String(identity.name) : undefined),
      professional_role: suppliedPreview.professional_role || String(identity.role || "Agente immobiliare"),
      agency: suppliedPreview.agency || String(identity.agency || "") || null,
      territory: suppliedPreview.territory || String(identity.territory || "") || null,
      welcome_message: suppliedPreview.welcome_message || String(presentation.welcome || ""),
    },
  };
}
