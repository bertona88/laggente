import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = path.resolve(import.meta.dirname, "..");
const readWebFile = (relativePath: string) => readFileSync(path.join(webRoot, relativePath), "utf8");

describe("short product invitation", () => {
  it("explains the product linearly and links to the real Studio entry", () => {
    const page = readWebFile("components/short-invitation-page.tsx");

    expect(page).toContain("Un assistente online che lavora come gli insegni tu");
    expect(page).toContain("Accoglie le persone");
    expect(page).toContain("Impara come lavori");
    expect(page).toContain("Ti lascia entrare");
    expect(page).toContain("Scegli tu l’indirizzo disponibile");
    expect(page).toContain('studioHref("/login")');
    expect(page).toContain("/media/laggente-extension-it.mp4");
  });

  it("keeps the private sharing path out of the crawler allow-list", () => {
    expect(readWebFile("public/robots.txt")).toContain("Disallow: /short123");
  });
});
