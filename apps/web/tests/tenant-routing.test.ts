import { describe, expect, it } from "vitest";
import { canonicalProductRedirect, tenantRewriteTarget, tenantSlugFromHost } from "@/lib/tenant-routing";

describe("tenant routing", () => {
  it("rewrites a professional root to its single-deployment space", () => {
    expect(tenantRewriteTarget("mauro.laggente.com", "/")).toBe("/spazio/mauro");
    expect(tenantSlugFromHost("mauro.localhost:3000")).toBe("mauro");
  });

  it("keeps legal surfaces global on a professional hostname", () => {
    expect(tenantRewriteTarget("mauro.laggente.com", "/privacy")).toBeNull();
    expect(tenantRewriteTarget("mauro.laggente.com", "/terms")).toBeNull();
  });

  it("does not treat reserved or malformed subdomains as tenants", () => {
    expect(tenantSlugFromHost("app.laggente.com")).toBeNull();
    expect(tenantSlugFromHost("bad_slug.laggente.com")).toBeNull();
  });

  it("redirects apex and www product entry points to their cookie-owning hosts", () => {
    expect(canonicalProductRedirect("laggente.com", "/mauro", "?ref=home"))
      .toBe("https://mauro.laggente.com/?ref=home");
    expect(canonicalProductRedirect("www.laggente.com", "/mauro/conversazione"))
      .toBe("https://mauro.laggente.com/conversazione");
    expect(canonicalProductRedirect("app.laggente.com", "/mauro", "?from=studio"))
      .toBe("https://mauro.laggente.com/?from=studio");
    expect(canonicalProductRedirect("laggente.com", "/login", "?token=magic"))
      .toBe("https://app.laggente.com/login?token=magic");
    expect(canonicalProductRedirect("www.laggente.com", "/studio/conversazioni"))
      .toBe("https://app.laggente.com/studio/conversazioni");
  });

  it("does not redirect localhost, canonical hosts, or legal pages", () => {
    expect(canonicalProductRedirect("localhost:3000", "/mauro")).toBeNull();
    expect(canonicalProductRedirect("mauro.laggente.com", "/mauro")).toBeNull();
    expect(canonicalProductRedirect("app.laggente.com", "/studio")).toBeNull();
    expect(canonicalProductRedirect("laggente.com", "/privacy")).toBeNull();
    expect(canonicalProductRedirect("laggente.com", "/terms")).toBeNull();
  });
});
