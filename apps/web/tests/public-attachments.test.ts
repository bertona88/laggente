import { describe, expect, it, vi } from "vitest";
import {
  pendingAudioDraftFromUpload,
  shouldDisablePublicComposerSubmit,
  shouldBlockPublicMessageSubmission,
  submitUploadedImage,
} from "@/lib/public-attachments";

describe("public attachment continuation", () => {
  it("keeps the composer submit control enabled for an attachment-only retry", () => {
    expect(shouldDisablePublicComposerSubmit({
      hasContent: false,
      hasPendingAttachment: true,
      recording: false,
      requestingMicrophone: false,
      sending: false,
      uploading: false,
    })).toBe(false);
    expect(shouldDisablePublicComposerSubmit({
      hasContent: false,
      hasPendingAttachment: false,
      recording: false,
      requestingMicrophone: false,
      sending: false,
      uploading: false,
    })).toBe(true);
  });

  it("allows the resolved photo continuation while blocking an unrelated send during upload", () => {
    expect(shouldBlockPublicMessageSubmission({
      hasContent: true,
      hasAttachment: true,
      sending: false,
      uploading: true,
      captureActive: false,
      isResolvedUploadContinuation: true,
    })).toBe(false);
    expect(shouldBlockPublicMessageSubmission({
      hasContent: true,
      hasAttachment: false,
      sending: false,
      uploading: true,
      captureActive: false,
      isResolvedUploadContinuation: false,
    })).toBe(true);
    expect(shouldBlockPublicMessageSubmission({
      hasContent: true,
      hasAttachment: false,
      sending: false,
      uploading: false,
      captureActive: true,
      isResolvedUploadContinuation: false,
    })).toBe(true);
  });

  it("posts the first-ever photo into the same conversation that received the upload", async () => {
    const postMessage = vi.fn();
    const submit = vi.fn(async (content, attachmentId, attachment, resolvedConversationId) => {
      // Exercise the same state/guard path as PublicSpace: controls remain locked by
      // `uploading`, but the completed upload may continue with its resolved thread.
      if (shouldBlockPublicMessageSubmission({
        hasContent: Boolean(content),
        hasAttachment: Boolean(attachmentId),
        sending: false,
        uploading: true,
        captureActive: false,
        isResolvedUploadContinuation: Boolean(resolvedConversationId),
      })) return;
      postMessage(content, attachmentId, attachment, resolvedConversationId);
    });
    await submitUploadedImage({
      attachment: { id: "photo-1", original_name: "casa.png", media_type: "image/png" },
      download_url: "/api/v1/attachments/photo-1/content",
    }, "conversation-created-for-upload", submit);
    expect(submit).toHaveBeenCalledWith(
      "Ti invio questa fotografia.",
      "photo-1",
      expect.objectContaining({ id: "photo-1", kind: "image" }),
      "conversation-created-for-upload",
    );
    expect(postMessage).toHaveBeenCalledWith(
      "Ti invio questa fotografia.",
      "photo-1",
      expect.objectContaining({ id: "photo-1", kind: "image" }),
      "conversation-created-for-upload",
    );
  });

  it("keeps the audio attachment id with the editable transcript draft", () => {
    expect(pendingAudioDraftFromUpload({
      attachment: { id: "audio-1", original_name: "nota.webm", media_type: "audio/webm" },
      transcript: "Vorrei raccontare la situazione con calma.",
      download_url: null,
    })).toEqual({
      attachmentId: "audio-1",
      transcript: "Vorrei raccontare la situazione con calma.",
    });
  });
});
