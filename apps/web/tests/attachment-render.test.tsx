import { cleanup, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { ConversationPhoto } from "@/components/conversation-photo";
import type { ConversationAttachment } from "@/lib/types";

const photo: ConversationAttachment = {
  id: "photo-1",
  kind: "image",
  name: "facciata della casa.webp",
  url: "/api/v1/attachments/photo-1/content",
};

afterEach(cleanup);

describe("conversation photo rendering", () => {
  it("renders the authorized photo in the visitor-facing thread", () => {
    render(createElement(ConversationPhoto, { attachment: photo, surface: "public" }));
    expect(screen.getByRole("img", { name: "facciata della casa.webp" }))
      .toHaveAttribute("src", "/api/v1/attachments/photo-1/content");
    expect(screen.getByRole("img")).not.toHaveClass("detail-message__attachment");
  });

  it("renders the same authorized photo in the professional thread", () => {
    render(createElement(ConversationPhoto, { attachment: photo, surface: "studio" }));
    expect(screen.getByRole("img", { name: "facciata della casa.webp" }))
      .toHaveAttribute("src", "/api/v1/attachments/photo-1/content");
    expect(screen.getByRole("img")).toHaveClass("detail-message__attachment");
  });
});
