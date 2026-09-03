import { describe, expect, it } from "vitest";
import { canonicalUrlForRoute, documentTitleForRoute } from "@/src/app";

describe("SPA route titles", () => {
  it("keeps Studio routes distinct in browser history", () => {
    expect(documentTitleForRoute("/login", null)).toBe("Accesso allo Studio");
    expect(documentTitleForRoute("/studio", null)).toBe("Studio privato");
    expect(documentTitleForRoute("/studio/conversazioni", null)).toBe("Conversazioni — Studio");
    expect(documentTitleForRoute("/studio/conversazioni/conversation-1", null)).toBe("Conversazione — Studio");
    expect(documentTitleForRoute("/studio/grafo", null)).toBe("Grafo — Studio");
    expect(documentTitleForRoute("/studio/documenti", null)).toBe("Documenti — Studio");
    expect(documentTitleForRoute("/studio/spazio", null)).toBe("Spazio pubblico — Studio");
  });

  it("names the private product preview without publishing a canonical URL", () => {
    expect(documentTitleForRoute("/short123", null)).toBe("Prova LAGGENTE");
    expect(canonicalUrlForRoute("/short123", null, "laggente.com")).toBeNull();
  });

  it("names public path previews and tenant-host roots", () => {
    expect(documentTitleForRoute("/mauro", null)).toBe("Spazio di Mauro");
    expect(documentTitleForRoute("/", "mauro")).toBe("Spazio di Mauro");
    expect(documentTitleForRoute("/", null)).toBe("");
  });

  it("does not label an unknown tenant-host path as a valid public space", () => {
    expect(documentTitleForRoute("/typo", "mauro")).toBe("Spazio non trovato");
  });

  it("keeps canonical URLs on the surface that owns each public page", () => {
    expect(canonicalUrlForRoute("/", null, "laggente.com")).toBe("https://laggente.com/");
    expect(canonicalUrlForRoute("/privacy", null, "laggente.com")).toBe("https://laggente.com/privacy");
    expect(canonicalUrlForRoute("/", "mauro", "mauro.laggente.com"))
      .toBe("https://mauro.laggente.com/");
    expect(canonicalUrlForRoute("/studio", null, "app.laggente.com")).toBeNull();
    expect(canonicalUrlForRoute("/missing", null, "laggente.com")).toBeNull();
  });
});
