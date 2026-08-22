import { describe, expect, it } from "vitest";
import { isLocalHostname, publicSpaceHref, studioHref } from "@/lib/hosts";

describe("canonical product hosts", () => {
  it("keeps routes local during localhost development", () => {
    expect(isLocalHostname("localhost")).toBe(true);
    expect(publicSpaceHref("mauro", "localhost")).toBe("/mauro");
    expect(publicSpaceHref("mauro", "app.localhost")).toBe("/mauro");
    expect(studioHref("/login", "127.0.0.1")).toBe("/login");
    expect(studioHref("studio", "::1")).toBe("/studio");
  });

  it("routes production entry points to their cookie-owning hosts", () => {
    expect(publicSpaceHref("mauro", "laggente.com")).toBe("https://mauro.laggente.com");
    expect(publicSpaceHref("anna", "app.laggente.com")).toBe("https://anna.laggente.com");
    expect(studioHref("/login", "laggente.com")).toBe("https://app.laggente.com/login");
    expect(studioHref("/studio", "mauro.laggente.com")).toBe("https://app.laggente.com/studio");
  });
});
