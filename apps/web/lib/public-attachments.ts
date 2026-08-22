import { attachmentFromUploadResponse, attachmentIdFromResponse } from "@/lib/api";
import type { ConversationAttachment } from "@/lib/types";

export interface PendingAudioDraft {
  attachmentId: string;
  transcript: string;
}

export function shouldDisablePublicComposerSubmit({
  hasContent,
  hasPendingAttachment,
  recording,
  requestingMicrophone,
  sending,
  uploading,
}: {
  hasContent: boolean;
  hasPendingAttachment: boolean;
  recording: boolean;
  requestingMicrophone: boolean;
  sending: boolean;
  uploading: boolean;
}): boolean {
  return (!hasContent && !hasPendingAttachment)
    || recording
    || requestingMicrophone
    || sending
    || uploading;
}

export function shouldBlockPublicMessageSubmission({
  hasContent,
  hasAttachment,
  sending,
  uploading,
  captureActive,
  isResolvedUploadContinuation,
}: {
  hasContent: boolean;
  hasAttachment: boolean;
  sending: boolean;
  uploading: boolean;
  captureActive: boolean;
  isResolvedUploadContinuation: boolean;
}): boolean {
  return (!hasContent && !hasAttachment)
    || sending
    || captureActive
    || (uploading && !isResolvedUploadContinuation);
}

export function pendingAudioDraftFromUpload(value: unknown): PendingAudioDraft | null {
  const object = value && typeof value === "object" ? value as Record<string, unknown> : null;
  const attachmentId = attachmentIdFromResponse(value);
  if (!object || !attachmentId || typeof object.transcript !== "string" || !object.transcript) {
    return null;
  }
  return { attachmentId, transcript: object.transcript };
}

export async function submitUploadedImage(
  value: unknown,
  resolvedConversationId: string,
  submit: (
    content: string,
    attachmentId: string,
    attachment: ConversationAttachment,
    resolvedConversationId: string,
  ) => Promise<void>,
): Promise<void> {
  const attachment = attachmentFromUploadResponse(value);
  const attachmentId = attachmentIdFromResponse(value);
  if (!attachment || attachment.kind !== "image" || !attachmentId) {
    throw new Error("Il caricamento non ha restituito una fotografia valida.");
  }
  await submit(
    "Ti invio questa fotografia.",
    attachmentId,
    attachment,
    resolvedConversationId,
  );
}
