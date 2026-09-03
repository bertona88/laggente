import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  shouldShowPublicAddressPicker,
  shouldShowStudioStarterPrompts,
  studioStarterPrompts,
  suggestPublicSlug,
} from "@/components/studio-workspace";

const webRoot = path.resolve(import.meta.dirname, "..");

describe("invited professional provisioning", () => {
  const buildingSpace = {
    id: "space",
    account_id: "account",
    slug: "pending-space",
    professional_name: "Giulia Bianchi",
    public_role: "Architetta",
    locale: "it-IT",
    is_active: false,
    slug_claimed: false,
    onboarding_state: "building",
  };

  it("suggests a short stable public username from an Italian professional name", () => {
    expect(suggestPublicSlug("Giulia Bianchi")).toBe("giulia");
    expect(suggestPublicSlug("Èlia D’Amico")).toBe("elia");
  });

  it("offers private web-research starters until the professional begins", () => {
    expect(studioStarterPrompts).toContain("Cerca cosa si trova già su di me online");
    expect(studioStarterPrompts).toContain("Trova il mio sito e i miei profili professionali");

    const welcome = {
      id: "welcome",
      author_type: "studio_assistant" as const,
      author_name: "Studio LAGGENTE",
      content: "Che lavoro fai?",
      created_at: "2026-08-24T00:00:00Z",
    };
    expect(shouldShowStudioStarterPrompts([welcome])).toBe(true);
    expect(
      shouldShowStudioStarterPrompts([
        welcome,
        {
          id: "reply",
          author_type: "professional",
          author_name: "Giulia",
          content: "Sono architetta.",
          created_at: "2026-08-24T00:01:00Z",
        },
      ]),
    ).toBe(false);
  });

  it("removes the public address picker as soon as the professional selects a name", () => {
    expect(shouldShowPublicAddressPicker(buildingSpace)).toBe(true);
    expect(shouldShowPublicAddressPicker({
      ...buildingSpace,
      slug_claimed: true,
    })).toBe(false);
  });

  it("keeps shared Studio and tenant adapters free of seeded-professional assumptions", () => {
    const sharedRuntimeFiles = [
      "components/studio-shell.tsx",
      "components/studio-workspace.tsx",
      "components/space-revisions.tsx",
      "components/revision-inspector.tsx",
      "components/conversation-inbox.tsx",
      "components/conversation-detail.tsx",
      "components/public-space.tsx",
      "components/invite-professional.tsx",
      "lib/space-adapter.ts",
      "lib/hosts.ts",
      "lib/tenant-routing.ts",
    ];
    const source = sharedRuntimeFiles
      .map((file) => readFileSync(path.join(webRoot, file), "utf8"))
      .join("\n");
    expect(source.toLocaleLowerCase("it-IT")).not.toContain("mauro");
  });
});
