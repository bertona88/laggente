import { DocumentIcon } from "@/components/icons";
import type { ConversationDocument as ConversationDocumentValue } from "@/lib/types";

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toLocaleString("it-IT", { maximumFractionDigits: 1 })} MB`;
}

export function ConversationDocument({
  document,
  compact = false,
}: {
  document?: ConversationDocumentValue | null;
  compact?: boolean;
}) {
  if (!document) return null;
  return (
    <a
      className={`conversation-document${compact ? " conversation-document--compact" : ""}`}
      href={document.url}
      download={document.name}
      aria-label={`Scarica ${document.name}`}
    >
      <span><DocumentIcon /></span>
      <span><strong>{document.name}</strong><small>{formatFileSize(document.size_bytes)}</small></span>
      <em>Scarica</em>
    </a>
  );
}
