function defaultClientMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `message-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface ClientMessageAttemptTracker {
  idFor(content: string, attachmentId?: string): string;
  invalidate(): void;
  complete(id: string): void;
}

export function createClientMessageAttemptTracker(
  makeId: () => string = defaultClientMessageId,
): ClientMessageAttemptTracker {
  let active: { fingerprint: string; id: string } | null = null;
  return {
    idFor(content, attachmentId) {
      const fingerprint = JSON.stringify([content.trim(), attachmentId || null]);
      if (active?.fingerprint === fingerprint) return active.id;
      active = { fingerprint, id: makeId() };
      return active.id;
    },
    invalidate() {
      active = null;
    },
    complete(id) {
      if (active?.id === id) active = null;
    },
  };
}
