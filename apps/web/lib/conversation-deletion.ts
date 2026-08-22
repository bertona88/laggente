export type ConversationDeletionSurface = "visitor" | "professional";

export function shouldDisableConversationDeletion({
  deleting,
  sending,
  uploading,
  captureActive,
}: {
  deleting: boolean;
  sending: boolean;
  uploading: boolean;
  captureActive: boolean;
}): boolean {
  return deleting || sending || uploading || captureActive;
}

export function conversationDeletionPrompt(surface: ConversationDeletionSurface): string {
  return surface === "visitor"
    ? "Eliminare definitivamente questa conversazione, i messaggi e le fotografie? L’operazione non può essere annullata."
    : "Eliminare definitivamente questa conversazione pubblica, i messaggi, la memoria derivata e gli allegati? L’operazione non può essere annullata.";
}

export function confirmConversationDeletion(
  surface: ConversationDeletionSurface,
  confirm: (message: string) => boolean = (message) => window.confirm(message),
): boolean {
  return confirm(conversationDeletionPrompt(surface));
}
