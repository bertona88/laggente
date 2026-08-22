import { describe, expect, it } from "vitest";
import {
  publicConversationCreateEndpoint,
  publicSpaceEndpoint,
} from "@/lib/public-routing";

describe("public API routing", () => {
  it("lets FastAPI resolve real tenant hosts from the request hostname", () => {
    expect(publicSpaceEndpoint("mauro", "mauro.laggente.com")).toBe("/public/resolve");
    expect(publicConversationCreateEndpoint("mauro", "mauro.laggente.com"))
      .toBe("/public/resolve/conversations");
  });

  it("keeps explicit slug routes for localhost previews", () => {
    expect(publicSpaceEndpoint("mauro", "localhost:3000")).toBe("/public/mauro");
    expect(publicSpaceEndpoint("mauro", "mauro.localhost:3000")).toBe("/public/mauro");
    expect(publicConversationCreateEndpoint("mauro", "mauro.localhost:3000"))
      .toBe("/public/mauro/conversations");
  });

  it("never sends reserved or malformed hosts through tenant resolution", () => {
    expect(publicSpaceEndpoint("mauro", "app.laggente.com")).toBe("/public/mauro");
    expect(publicSpaceEndpoint("mauro", "bad_slug.laggente.com")).toBe("/public/mauro");
    expect(publicSpaceEndpoint("mauro", "laggente.com")).toBe("/public/mauro");
  });
});
