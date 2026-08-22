import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Router } from "wouter";
import { ConversationInbox } from "@/components/conversation-inbox";

function inboxItem(id: string, title: string) {
  return {
    conversation: {
      id,
      title,
      last_message_at: "2026-08-22T10:00:00Z",
      automatic_ai_enabled: true,
      professional_joined: false,
    },
    summary: title,
  };
}

describe("Studio conversation inbox pagination", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads older conversations without duplicating an item already visible", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [inboxItem("conversation-1", "Casa al Flaminio")],
        total: 2,
        next_offset: 1,
      }), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [
          inboxItem("conversation-1", "Casa al Flaminio"),
          inboxItem("conversation-2", "Appartamento a Prati"),
        ],
        total: 2,
        next_offset: null,
      }), { status: 200, headers: { "content-type": "application/json" } }));

    render(<Router><ConversationInbox /></Router>);

    expect(await screen.findByRole("link", { name: /Casa al Flaminio/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Carica conversazioni precedenti" }));

    expect(await screen.findByRole("link", { name: /Appartamento a Prati/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Casa al Flaminio/ })).toHaveLength(1);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls.map(([path]) => String(path))).toEqual([
      "/api/v1/studio/conversations?limit=50&offset=0",
      "/api/v1/studio/conversations?limit=50&offset=1",
    ]);
    expect(screen.queryByRole("button", { name: "Carica conversazioni precedenti" })).not.toBeInTheDocument();
  });
});
