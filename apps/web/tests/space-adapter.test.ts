import { describe, expect, it } from "vitest";
import { normalizeSpace } from "@/lib/space-adapter";

describe("normalizeSpace", () => {
  it("renders activated document identity and welcome ahead of stale space metadata", () => {
    const result = normalizeSpace({
      slug: "mauro",
      professional_name: "Vecchio nome",
      public_role: "Vecchio ruolo",
      territory: "Vecchio territorio",
      ai_label: "LAGGENTE — assistente AI di Mauro",
      privacy_notice_version: "2026-09-01",
      capabilities: { text: true, voice_notes: false, photographs: false },
      configuration: {
        identity: {
          name: "Mauro Bianchi",
          role: "Consulente immobiliare",
          agency: "Atelier Casa",
          territory: "Roma Nord e Flaminio",
        },
        public: { welcome: "Una nuova accoglienza attivata." },
      },
    }, "mauro");

    expect(result).toMatchObject({
      professional_name: "Mauro Bianchi",
      professional_role: "Consulente immobiliare",
      agency: "Atelier Casa",
      territory: "Roma Nord e Flaminio",
      welcome_message: "Una nuova accoglienza attivata.",
      assistant_disclosure: "LAGGENTE — assistente AI di Mauro",
      privacy_notice_version: "2026-09-01",
      capabilities: { text: true, voice_notes: false, photographs: false },
    });
  });

  it("never leaks Mauro identity into an unknown tenant placeholder", () => {
    const result = normalizeSpace(null, "sconosciuto");
    expect(result.slug).toBe("sconosciuto");
    expect(result.professional_name).toBe("Spazio professionale");
    expect(JSON.stringify(result)).not.toContain("Mauro");
  });
});
