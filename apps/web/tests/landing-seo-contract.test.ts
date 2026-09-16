import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = path.resolve(import.meta.dirname, "..");
const readWebFile = (relativePath: string) => readFileSync(path.join(webRoot, relativePath), "utf8");

describe("brand landing and crawl contract", () => {
  it("keeps the base profession-agnostic while featuring real estate first", () => {
    const landing = readWebFile("components/landing-page.tsx");
    const header = readWebFile("components/brand-header.tsx");
    const legalPages = readWebFile("src/legal-pages.tsx");

    expect(landing).toContain("/product/positioning");
    expect(landing).toContain("positioning.homepage");
    expect(landing).not.toContain("real_estate_it");
    expect(`${header}\n${landing}\n${legalPages}`).not.toContain('publicSpaceHref("mauro")');
  });

  it("ships one indexable brand URL with valid crawler assets", () => {
    const index = readWebFile("index.html");
    const robots = readWebFile("public/robots.txt");
    const sitemap = readWebFile("public/sitemap.xml");

    expect(index).toContain("<title>Il tuo assistente AI per i clienti | LAGGENTE</title>");
    expect(index).toContain("https://laggente.com/media/laggente-hero.webp");
    expect(readWebFile("components/landing-page.tsx")).toContain('src="/media/laggente-hero.webp"');
    expect(existsSync(path.join(webRoot, "public/media/laggente-hero.webp"))).toBe(true);
    expect(index).toContain('<link rel="canonical" href="https://laggente.com/" />');
    expect(robots).toContain("Sitemap: https://laggente.com/sitemap.xml");
    expect(sitemap.match(/<loc>/g)).toHaveLength(1);
    expect(sitemap).toContain("<loc>https://laggente.com/</loc>");
  });
});
