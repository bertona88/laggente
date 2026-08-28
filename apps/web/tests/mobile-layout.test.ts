import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const styles = readFileSync(join(process.cwd(), "src/styles.css"), "utf8");

describe("mobile Studio overflow", () => {
  it("shows the compact professional identity only inside the mobile chat header", () => {
    expect(styles).toMatch(
      /\.public-chat__header > \.public-chat__professional, \.public-professional-context\s*\{[^}]*display:\s*none;/s,
    );
    const mobileRules = styles.slice(styles.indexOf("@media (max-width: 899px)"));
    expect(mobileRules).toMatch(
      /\.public-chat__header > \.public-chat__professional\s*\{[^}]*display:\s*flex;/s,
    );
  });

  it("keeps long inbox and revision pages scrollable inside the fixed mobile frame", () => {
    const mobileRules = styles.slice(styles.indexOf("@media (max-width: 740px)"));
    expect(mobileRules).toMatch(
      /\.inbox-page, \.space-page\s*\{[^}]*height:\s*100%;[^}]*min-height:\s*0;[^}]*overflow-y:\s*auto;[^}]*overscroll-behavior:\s*contain;/s,
    );
  });

  it("keeps the document library scrollable inside the fixed mobile frame", () => {
    const documentRules = styles.slice(styles.indexOf("/* Private source library"));
    expect(documentRules).toMatch(
      /@media \(max-width: 899px\)[\s\S]*\.documents-page\s*\{[^}]*height:\s*100%;[^}]*min-height:\s*0;[^}]*overflow-y:\s*auto;[^}]*overscroll-behavior:\s*contain;/s,
    );
  });
});
