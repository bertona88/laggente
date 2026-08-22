import { createElement } from "react";
import type { ConversationAttachment } from "@/lib/types";

export function ConversationPhoto({
  attachment,
  surface,
}: {
  attachment?: ConversationAttachment | null;
  surface: "public" | "studio";
}) {
  if (attachment?.kind !== "image" || !attachment.url) return null;
  return createElement("img", {
    src: attachment.url,
    alt: attachment.name || "Fotografia condivisa nella conversazione",
    className: surface === "studio" ? "detail-message__attachment" : undefined,
  });
}
