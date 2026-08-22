import { describe, expect, it } from "vitest";
import { normalizeRevision } from "@/lib/revisions";

describe("revision preview", () => {
  it("turns an extensible document into inspectable sections and public preview", () => {
    const revision = normalizeRevision({
      id: "r2",
      revision_number: 2,
      status: "draft",
      rationale: "Accoglienza più diretta",
      created_at: "2026-08-22T10:00:00Z",
      document: {
        schema_version: 1,
        identity: { name: "Mauro Rossi", role: "Agente immobiliare", territory: "Roma Nord" },
        public: { welcome: "Raccontami da dove vuoi partire." },
        extensions: { metodo: "ascolto prima delle proposte" },
      },
    });
    expect(revision?.number).toBe(2);
    expect(revision?.summary).toBe("Accoglienza più diretta");
    expect(revision?.preview?.welcome_message).toBe("Raccontami da dove vuoi partire.");
    expect(revision?.sections.map((section) => section.key)).toContain("extensions");
  });

  it("does not invent a pilot identity when a revision omits one", () => {
    const revision = normalizeRevision({
      id: "r3",
      status: "draft",
      created_at: "2026-08-22T11:00:00Z",
      document: { public: { welcome: "Benvenuto." } },
    });

    expect(revision?.preview?.professional_name).toBeUndefined();
  });
});
