import { describe, expect, it } from "vitest";
import {
  invitationTokenFromFragment,
  magicLinkTokenFromFragment,
  signupTokenFromFragment,
} from "@/lib/magic-link";

describe("magic-link fragment transport", () => {
  it("extracts the token without putting it in the server-visible query string", () => {
    expect(magicLinkTokenFromFragment("#token=signed-token%2Epart")).toBe("signed-token.part");
    expect(magicLinkTokenFromFragment("")).toBeNull();
  });

  it("keeps professional invitation tokens in a distinct fragment field", () => {
    expect(invitationTokenFromFragment("#invite=invitation%2Etoken")).toBe("invitation.token");
    expect(invitationTokenFromFragment("#token=login-token")).toBeNull();
  });

  it("keeps open-signup proofs in their own fragment field", () => {
    expect(signupTokenFromFragment("#signup=signup%2Etoken")).toBe("signup.token");
    expect(signupTokenFromFragment("#token=login-token")).toBeNull();
  });
});
