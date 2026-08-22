import { describe, expect, it } from "vitest";
import { normalizeConversationSummary } from "@/lib/conversations";

describe("conversation inbox adapter", () => {
  it("unwraps the final studio list envelope for a valid detail link and preview", () => {
    const result = normalizeConversationSummary({
      conversation: {
        id: "conversation-42",
        title: "Casa ereditata a Flaminio",
        last_message_at: "2026-08-22T11:02:00Z",
        automatic_ai_enabled: false,
        professional_joined: true,
      },
      summary: "Sta valutando una vendita con gli altri proprietari.",
      attention_reason: "Il giudizio di Mauro può chiarire il prossimo passo.",
      last_message: {
        id: "message-9",
        content: "Preferirei parlarne con Mauro.",
        created_at: "2026-08-22T11:03:00Z",
      },
    });
    expect(result.id).toBe("conversation-42");
    expect(result.last_message).toBe("Preferirei parlarne con Mauro.");
    expect(result.last_message_at).toBe("2026-08-22T11:03:00Z");
    expect(result.professional_present).toBe(true);
    expect(result.automatic_replies_enabled).toBe(false);
  });
});
