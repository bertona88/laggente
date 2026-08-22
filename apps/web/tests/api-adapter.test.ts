import { describe, expect, it } from "vitest";
import {
  ApiError,
  attachmentFromUploadResponse,
  attachmentIdFromResponse,
  normalizeMessage,
  reconcileMessages,
  resolveMessageResponse,
  shouldForgetSavedConversation,
} from "@/lib/api";

describe("API adapters", () => {
  it("maps backend author_label to the explicit UI speaker name", () => {
    expect(normalizeMessage({
      id: "m1",
      author_type: "public_assistant",
      author_label: "LAGGENTE — assistente AI di Mauro",
      content: "Ciao",
      created_at: "2026-08-22T10:00:00Z",
    })).toMatchObject({
      author_name: "LAGGENTE — assistente AI di Mauro",
      author_type: "public_assistant",
      content: "Ciao",
    });
  });

  it("normalizes the visitor and AI messages returned by one public turn", () => {
    const messages = resolveMessageResponse({ messages: [
      { id: "v1", author_type: "visitor", author_label: "Tu", content: "Vorrei parlare", created_at: "2026-08-22T10:00:00Z" },
      { id: "a1", author_type: "public_assistant", author_label: "LAGGENTE — assistente AI di Mauro", content: "Ti ascolto", created_at: "2026-08-22T10:00:01Z" },
    ] });
    expect(messages).toHaveLength(2);
    expect(messages.map((message) => message.author_type)).toEqual(["visitor", "public_assistant"]);
  });

  it("reads the attachment id from the final multipart response contract", () => {
    expect(attachmentIdFromResponse({
      attachment: { id: "attachment-1", original_name: "casa.webp", media_type: "image/webp", status: "ready" },
      transcript: null,
      download_url: "/signed/example",
    })).toBe("attachment-1");
  });

  it("normalizes a safe durable image projection without backend storage metadata", () => {
    const message = normalizeMessage({
      id: "v-photo",
      author_type: "visitor",
      author_label: "Tu",
      content: "Ti invio questa fotografia.",
      attachment: {
        id: "attachment-1",
        kind: "image",
        name: "facciata.webp",
        url: "/api/v1/attachments/attachment-1/content",
      },
    });
    expect(message.attachment).toEqual({
      id: "attachment-1",
      kind: "image",
      name: "facciata.webp",
      url: "/api/v1/attachments/attachment-1/content",
    });
  });

  it("adapts image and audio multipart responses", () => {
    expect(attachmentFromUploadResponse({
      attachment: { id: "image-1", original_name: "casa.webp", media_type: "image/webp" },
      download_url: "/api/v1/attachments/image-1/content",
    })).toEqual({
      id: "image-1",
      kind: "image",
      name: "casa.webp",
      url: "/api/v1/attachments/image-1/content",
    });
    expect(attachmentFromUploadResponse({
      attachment: { id: "audio-1", original_name: "nota.webm", media_type: "audio/webm" },
      transcript: "Vorrei parlare della casa.",
      download_url: null,
    })).toEqual({ id: "audio-1", kind: "audio", name: "nota.webm" });
  });

  it("keeps optimistic messages and an already-rendered photo URL during reconciliation", () => {
    const previous = normalizeMessage({
      id: "photo-message",
      author_type: "visitor",
      attachment: { id: "photo", kind: "image", url: "/stable/content" },
    });
    const pending = { ...normalizeMessage({ id: "pending", author_type: "visitor" }), pending: true };
    const incoming = normalizeMessage({
      id: "photo-message",
      author_type: "visitor",
      attachment: { id: "photo", kind: "image", url: "/replacement/content" },
    });
    const reconciled = reconcileMessages([previous, pending], [incoming]);
    expect(reconciled[0].attachment?.url).toBe("/stable/content");
    expect(reconciled[1]).toMatchObject({ id: "pending", pending: true });
  });

  it("forgets a saved thread only when authorization says it is definitively gone", () => {
    expect(shouldForgetSavedConversation(new ApiError("missing", 404, { detail: "Conversazione non trovata" }))).toBe(true);
    expect(shouldForgetSavedConversation(new ApiError("unauthorized", 401))).toBe(true);
    expect(shouldForgetSavedConversation(new ApiError("inactive", 410, { detail: "Spazio non attivo" }))).toBe(false);
    expect(shouldForgetSavedConversation(new ApiError("tenant missing", 404, { detail: "Spazio non trovato" }))).toBe(false);
    expect(shouldForgetSavedConversation(new ApiError("generic missing", 404))).toBe(false);
    expect(shouldForgetSavedConversation(new ApiError("temporary", 503))).toBe(false);
    expect(shouldForgetSavedConversation(new TypeError("network offline"))).toBe(false);
  });
});
