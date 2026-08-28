import type {
  ApiErrorBody,
  ConversationAttachment,
  ConversationDocument,
  ConversationMessage,
  StudioDocument,
} from "@/lib/types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailFrom(body: ApiErrorBody | null, fallback: string) {
  if (!body) return fallback;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail.map((item) => item.msg).filter(Boolean).join(", ") || fallback;
  }
  return body.message || fallback;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  headers.set("accept", "application/json");

  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");

  if (!response.ok) {
    throw new ApiError(
      detailFrom(body as ApiErrorBody | null, `Richiesta non riuscita (${response.status})`),
      response.status,
      body,
    );
  }

  return body as T;
}

export function isUnauthorized(error: unknown) {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export function shouldForgetSavedConversation(error: unknown) {
  if (!(error instanceof ApiError)) return false;
  if (error.status === 401) return true;
  if (error.status !== 404 || !error.body || typeof error.body !== "object") return false;
  const detail = (error.body as ApiErrorBody).detail;
  return detail === "Conversazione non trovata";
}

export function isInactiveConversation(error: unknown) {
  return error instanceof ApiError && error.status === 410;
}

export function unwrapList<T>(value: unknown, keys: string[]): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    for (const key of keys) {
      if (Array.isArray(object[key])) return object[key] as T[];
    }
  }
  return [];
}

export function resolveMessageResponse(value: unknown) {
  if (!value || typeof value !== "object") return [];
  const object = value as Record<string, unknown>;
  if (Array.isArray(object.messages)) return object.messages.map(normalizeMessage);
  if (object.assistant_message) return [normalizeMessage(object.assistant_message)];
  if (object.message && typeof object.message === "object") return [normalizeMessage(object.message)];
  return [];
}

function recordFrom(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? value as Record<string, unknown> : null;
}

export function normalizeAttachment(value: unknown): ConversationAttachment | null {
  const object = recordFrom(value);
  if (!object) return null;
  const id = typeof object.id === "string" ? object.id : "";
  const mediaType = typeof object.media_type === "string" ? object.media_type : "";
  const rawKind = object.kind || (mediaType.startsWith("image/") ? "image" : mediaType.startsWith("audio/") ? "audio" : null);
  if (!id || (rawKind !== "image" && rawKind !== "audio")) return null;
  const name = object.name || object.original_name;
  return {
    id,
    kind: rawKind,
    ...(typeof name === "string" && name ? { name } : {}),
    ...(typeof object.url === "string" && object.url ? { url: object.url } : {}),
  };
}

export function attachmentFromUploadResponse(value: unknown): ConversationAttachment | null {
  const object = recordFrom(value);
  if (!object) return null;
  const attachment = normalizeAttachment(object.attachment || object);
  if (!attachment) return null;
  const responseUrl = object.download_url;
  return typeof responseUrl === "string" && responseUrl
    ? { ...attachment, url: responseUrl }
    : attachment;
}

export function normalizeDocument(value: unknown): ConversationDocument | null {
  const object = recordFrom(value);
  if (!object) return null;
  const id = typeof object.id === "string" ? object.id : "";
  const name = object.name || object.original_name;
  const url = object.url || object.download_url;
  if (!id || typeof name !== "string" || !name || typeof url !== "string" || !url) return null;
  return {
    id,
    name,
    media_type: typeof object.media_type === "string" ? object.media_type : "application/octet-stream",
    size_bytes: typeof object.size_bytes === "number" ? object.size_bytes : 0,
    url,
  };
}

export function documentFromUploadResponse(value: unknown): ConversationDocument | null {
  const object = recordFrom(value);
  if (!object) return null;
  return normalizeDocument(object.document || object);
}

export function normalizeStudioDocument(value: unknown): StudioDocument | null {
  const object = recordFrom(value);
  const document = normalizeDocument(object);
  if (!object || !document) return null;
  const publicState = object.public_state;
  if (publicState !== "private" && publicState !== "draft" && publicState !== "active") return null;
  return {
    ...document,
    conversation_id: typeof object.conversation_id === "string" ? object.conversation_id : null,
    message_id: typeof object.message_id === "string" ? object.message_id : null,
    scope: object.scope === "conversation" ? "conversation" : "studio",
    uploader_type: typeof object.uploader_type === "string" ? object.uploader_type : "professional",
    sha256: typeof object.sha256 === "string" ? object.sha256 : "",
    status: typeof object.status === "string" ? object.status : "ready",
    extracted_characters: typeof object.extracted_characters === "number" ? object.extracted_characters : 0,
    public_state: publicState,
    download_url: document.url,
    created_at: typeof object.created_at === "string" ? object.created_at : "",
    updated_at: typeof object.updated_at === "string" ? object.updated_at : "",
  };
}

export function normalizeMessage(value: unknown): ConversationMessage {
  const object = (value || {}) as Record<string, unknown>;
  const authorType = String(object.author_type || object.author || "system") as ConversationMessage["author_type"];
  const fallbackName = authorType === "visitor"
    ? "Tu"
    : authorType === "professional"
      ? "Il professionista"
      : authorType === "studio_assistant"
        ? "Studio LAGGENTE"
        : authorType === "public_assistant"
          ? "LAGGENTE — assistente AI"
          : "LAGGENTE";
  return {
    id: String(object.id || `message-${Date.now()}-${Math.random().toString(36).slice(2)}`),
    author_type: authorType,
    author_name: String(object.author_name || object.author_label || fallbackName),
    content: String(object.content || ""),
    created_at: String(object.created_at || new Date().toISOString()),
    pending: Boolean(object.pending),
    attachment: normalizeAttachment(object.attachment),
    document: normalizeDocument(object.document),
  };
}

export function normalizeMessages(value: unknown): ConversationMessage[] {
  return Array.isArray(value) ? value.map(normalizeMessage) : [];
}

export function attachmentIdFromResponse(value: unknown) {
  if (!value || typeof value !== "object") return null;
  const object = value as Record<string, unknown>;
  const attachment = object.attachment as Record<string, unknown> | undefined;
  const id = attachment?.id || object.attachment_id || object.id;
  return typeof id === "string" && id ? id : null;
}

export function reconcileMessages(
  current: ConversationMessage[],
  incoming: ConversationMessage[],
): ConversationMessage[] {
  const currentById = new Map(current.map((message) => [message.id, message]));
  const reconciled = incoming.map((message) => {
    const previous = currentById.get(message.id);
    const previousAttachment = previous?.attachment;
    const incomingAttachment = message.attachment;
    if (
      previousAttachment
      && incomingAttachment
      && previousAttachment.id === incomingAttachment.id
      && previousAttachment.url
    ) {
      return {
        ...message,
        attachment: { ...incomingAttachment, url: previousAttachment.url },
      };
    }
    const previousDocument = previous?.document;
    const incomingDocument = message.document;
    if (
      previousDocument
      && incomingDocument
      && previousDocument.id === incomingDocument.id
      && previousDocument.url
    ) {
      return {
        ...message,
        document: { ...incomingDocument, url: previousDocument.url },
      };
    }
    return message;
  });
  const incomingIds = new Set(incoming.map((message) => message.id));
  return [
    ...reconciled,
    ...current.filter((message) => message.pending && !incomingIds.has(message.id)),
  ];
}
