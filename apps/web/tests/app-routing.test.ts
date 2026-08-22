import { describe, expect, it } from "vitest";
import { documentTitleForRoute } from "@/src/app";

describe("SPA route titles", () => {
  it("keeps Studio routes distinct in browser history", () => {
    expect(documentTitleForRoute("/login", null)).toBe("Accesso allo Studio");
    expect(documentTitleForRoute("/studio", null)).toBe("Studio privato");
    expect(documentTitleForRoute("/studio/conversazioni", null)).toBe("Conversazioni — Studio");
    expect(documentTitleForRoute("/studio/conversazioni/conversation-1", null)).toBe("Conversazione — Studio");
    expect(documentTitleForRoute("/studio/spazio", null)).toBe("Spazio pubblico — Studio");
  });

  it("names public path previews and tenant-host roots", () => {
    expect(documentTitleForRoute("/mauro", null)).toBe("Spazio di Mauro");
    expect(documentTitleForRoute("/", "mauro")).toBe("Spazio di Mauro");
    expect(documentTitleForRoute("/", null)).toBe("");
  });

  it("does not label an unknown tenant-host path as a valid public space", () => {
    expect(documentTitleForRoute("/typo", "mauro")).toBe("Spazio non trovato");
  });
});
