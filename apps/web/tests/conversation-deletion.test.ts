import { describe, expect, it, vi } from "vitest";
import {
  confirmConversationDeletion,
  conversationDeletionPrompt,
  shouldDisableConversationDeletion,
} from "@/lib/conversation-deletion";

describe("conversation deletion confirmation", () => {
  it("names the irreversible visitor data scope before deletion", () => {
    const confirm = vi.fn().mockReturnValue(true);
    expect(confirmConversationDeletion("visitor", confirm)).toBe(true);
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/messaggi e le fotografie/i));
    expect(conversationDeletionPrompt("visitor")).toMatch(/non può essere annullata/i);
  });

  it("names derived memory and attachments for the professional", () => {
    expect(conversationDeletionPrompt("professional")).toMatch(/memoria derivata e gli allegati/i);
  });

  it("blocks deletion while any message, upload, or capture can still write", () => {
    expect(shouldDisableConversationDeletion({ deleting: false, sending: false, uploading: false, captureActive: false })).toBe(false);
    expect(shouldDisableConversationDeletion({ deleting: false, sending: false, uploading: false, captureActive: true })).toBe(true);
    expect(shouldDisableConversationDeletion({ deleting: false, sending: false, uploading: true, captureActive: false })).toBe(true);
    expect(shouldDisableConversationDeletion({ deleting: false, sending: true, uploading: false, captureActive: false })).toBe(true);
  });
});
