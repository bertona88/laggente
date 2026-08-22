import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = path.resolve(import.meta.dirname, "..");
const readWebFile = (relativePath: string) => readFileSync(path.join(webRoot, relativePath), "utf8");

describe("brand landing and crawl contract", () => {
  it("targets real-estate professionals without leaking the seeded pilot identity", () => {
    const landing = readWebFile("components/landing-page.tsx");
    const header = readWebFile("components/brand-header.tsx");
    const legalPages = readWebFile("src/legal-pages.tsx");

    expect(landing).toContain("Assistente AI per agenti immobiliari");
    expect(landing).toContain("spazio digitale personale per professionisti immobiliari");
    expect(`${header}\n${landing}\n${legalPages}`).not.toContain("Mauro");
    expect(`${header}\n${landing}`).not.toContain('publicSpaceHref("mauro")');
  });

  it("ships one indexable brand URL with valid crawler assets", () => {
    const index = readWebFile("index.html");
    const robots = readWebFile("public/robots.txt");
    const sitemap = readWebFile("public/sitemap.xml");

    expect(index).toContain("<title>Assistente AI per agenti immobiliari | LAGGENTE</title>");
    expect(index).toContain('<link rel="canonical" href="https://laggente.com/" />');
    expect(robots).toContain("Sitemap: https://laggente.com/sitemap.xml");
    expect(sitemap.match(/<loc>/g)).toHaveLength(1);
    expect(sitemap).toContain("<loc>https://laggente.com/</loc>");
  });
});
