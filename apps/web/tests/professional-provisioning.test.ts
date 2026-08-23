import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { suggestPublicSlug } from "@/components/studio-workspace";

const webRoot = path.resolve(import.meta.dirname, "..");

describe("invited professional provisioning", () => {
  it("suggests a short stable public username from an Italian professional name", () => {
    expect(suggestPublicSlug("Giulia Bianchi")).toBe("giulia");
    expect(suggestPublicSlug("Èlia D’Amico")).toBe("elia");
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
