import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ConversationDocument } from "@/components/conversation-document";

afterEach(cleanup);

describe("conversation document rendering", () => {
  it("renders a same-origin authorized download with useful metadata", () => {
    render(
      <ConversationDocument document={{
        id: "document-1",
        name: "situazione.pdf",
        media_type: "application/pdf",
        size_bytes: 2048,
        url: "/api/v1/documents/document-1/content",
      }} />,
    );
    const link = screen.getByRole("link", { name: "Scarica situazione.pdf" });
    expect(link).toHaveAttribute("href", "/api/v1/documents/document-1/content");
    expect(link).toHaveAttribute("download", "situazione.pdf");
    expect(screen.getByText("2 KB")).toBeInTheDocument();
  });
});
