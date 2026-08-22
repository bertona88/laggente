import { describe, expect, it } from "vitest";
import { magicLinkTokenFromFragment } from "@/lib/magic-link";

describe("magic-link fragment transport", () => {
  it("extracts the token without putting it in the server-visible query string", () => {
    expect(magicLinkTokenFromFragment("#token=signed-token%2Epart")).toBe("signed-token.part");
    expect(magicLinkTokenFromFragment("")).toBeNull();
  });
});
