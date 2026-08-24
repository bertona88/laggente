import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = path.resolve(import.meta.dirname, "..");
const readWebFile = (relativePath: string) => readFileSync(path.join(webRoot, relativePath), "utf8");

describe("brand landing and crawl contract", () => {
  it("keeps the base profession-agnostic while featuring real estate first", () => {
    const landing = readWebFile("components/landing-page.tsx");
    const header = readWebFile("components/brand-header.tsx");
    const legalPages = readWebFile("src/legal-pages.tsx");

    expect(landing).toContain("La gente incontra <em>l’agente.</em>");
    expect(landing).toContain("nome</i>.laggente.com");
    expect(landing).toContain("Modella il tuo stile");
    expect(landing).toContain("decidi quando aprirlo");
    expect(landing).toContain("La gente non compila");
    expect(landing).toContain("Poi la gente incontra l’agente");
    expect(`${header}\n${landing}`).toContain("Studio per professionisti");
    expect(landing).not.toContain("Il backend seleziona");
    expect(landing).toContain("Che lavoro fai?");
    expect(landing).toContain("Agenti immobiliari");
    expect(landing).toContain("/product/positioning");
    expect(`${header}\n${landing}\n${legalPages}`).not.toContain("Mauro");
    expect(`${header}\n${landing}`).not.toContain('publicSpaceHref("mauro")');
  });

  it("ships one indexable brand URL with valid crawler assets", () => {
    const index = readWebFile("index.html");
    const robots = readWebFile("public/robots.txt");
    const sitemap = readWebFile("public/sitemap.xml");

    expect(index).toContain("<title>Uno spazio AI per professionisti | LAGGENTE</title>");
    expect(index).toContain('<link rel="canonical" href="https://laggente.com/" />');
    expect(robots).toContain("Sitemap: https://laggente.com/sitemap.xml");
    expect(sitemap.match(/<loc>/g)).toHaveLength(1);
    expect(sitemap).toContain("<loc>https://laggente.com/</loc>");
  });
});
