import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const styles = readFileSync(join(process.cwd(), "src/styles.css"), "utf8");

describe("mobile Studio overflow", () => {
  it("keeps long inbox and revision pages scrollable inside the fixed mobile frame", () => {
    const mobileRules = styles.slice(styles.indexOf("@media (max-width: 740px)"));
    expect(mobileRules).toMatch(
      /\.inbox-page, \.space-page\s*\{[^}]*height:\s*100%;[^}]*min-height:\s*0;[^}]*overflow-y:\s*auto;[^}]*overscroll-behavior:\s*contain;/s,
    );
  });
});
