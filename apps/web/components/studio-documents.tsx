import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AppLink as Link } from "@/components/app-link";
import { CheckIcon, DocumentIcon, LockIcon } from "@/components/icons";
import { InlineError, LoadingLine } from "@/components/status";
import { apiRequest, normalizeStudioDocument } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { StudioDocument } from "@/lib/types";

const stateCopy = {
  private: { label: "Solo Studio", detail: "Il tuo assistente privato può leggerlo." },
  draft: { label: "In bozza", detail: "Attiva la versione prima che sia usato nello spazio pubblico." },
  active: { label: "Conoscenza pubblica", detail: "L’assistente pubblico può consultarlo quando serve." },
} as const;

function documentsFrom(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map(normalizeStudioDocument).filter((item): item is StudioDocument => Boolean(item));
}

export function StudioDocuments() {
  const [documents, setDocuments] = useState<StudioDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDocuments(documentsFrom(await apiRequest<unknown>("/studio/documents")));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile aprire i documenti.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const result = await apiRequest<Record<string, unknown>>("/studio/documents", {
        method: "POST",
        body: form,
      });
      const document = normalizeStudioDocument(result.document);
      if (!document) throw new Error("Il documento caricato non è leggibile.");
      setDocuments((current) => [document, ...current]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Il documento non è stato caricato.");
    } finally {
      setUploading(false);
    }
  }

  async function propose(document: StudioDocument, enabled: boolean) {
    setBusyId(document.id);
    setError(null);
    try {
      const result = await apiRequest<Record<string, unknown>>(
        `/studio/documents/${encodeURIComponent(document.id)}/public-proposal`,
        { method: "POST", body: JSON.stringify({ enabled }) },
      );
      const updated = normalizeStudioDocument(result.document);
      if (updated) {
        setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "La modifica non è stata preparata.");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(document: StudioDocument) {
    if (!window.confirm(`Eliminare definitivamente “${document.name}” dallo Studio?`)) return;
    setBusyId(document.id);
    setError(null);
    try {
      await apiRequest(`/documents/${encodeURIComponent(document.id)}`, { method: "DELETE" });
      setDocuments((current) => current.filter((item) => item.id !== document.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Il documento non è stato eliminato.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="documents-page">
      <header className="documents-header">
        <div><p>Fonti private</p><h1>Documenti dello Studio</h1></div>
        <div className="documents-header__action">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md,.markdown,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/csv"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
              event.currentTarget.value = "";
            }}
          />
          <button type="button" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
            <DocumentIcon /> {uploading ? "Caricamento…" : "Carica documento"}
          </button>
          <span>PDF, DOCX, TXT, Markdown o CSV</span>
        </div>
      </header>

      <div className="documents-explainer">
        <LockIcon />
        <p><strong>Qui lo Studio può leggere tutto.</strong> Nessun documento diventa conoscenza pubblica da solo: prepari una bozza, poi la attivi esplicitamente in <Link href="/studio/spazio">Spazio pubblico</Link>.</p>
      </div>
      {error && <div className="documents-error"><InlineError message={error} retry={load} /></div>}

      <div className="documents-list" aria-live="polite" aria-busy={loading || uploading}>
        <div className="documents-list__head"><span>Documento</span><span>Accesso</span><span>Aggiunto</span><span>Azioni</span></div>
        {loading && <LoadingLine label="Apro la biblioteca privata…" />}
        {!loading && !documents.length && (
          <div className="documents-empty">
            <DocumentIcon />
            <h2>Porta qui le fonti che usi davvero.</h2>
            <p>Presentazioni, guide, testi e materiali di lavoro restano privati finché non scegli diversamente.</p>
            <button type="button" onClick={() => fileInputRef.current?.click()}>Scegli il primo documento</button>
          </div>
        )}
        <AnimatePresence initial={false}>
          {documents.map((document) => {
            const state = stateCopy[document.public_state];
            const busy = busyId === document.id;
            return (
              <motion.article
                layout
                key={document.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                className="document-row"
              >
                <div className="document-row__name"><span><DocumentIcon /></span><p><a href={document.download_url} download={document.name}>{document.name}</a><small>{document.extracted_characters.toLocaleString("it-IT")} caratteri leggibili dallo Studio</small></p></div>
                <div className={`document-row__state document-row__state--${document.public_state}`}><i>{document.public_state === "active" && <CheckIcon />}</i><p><strong>{state.label}</strong><small>{state.detail}</small></p></div>
                <time dateTime={document.created_at}>{document.created_at ? formatDateTime(document.created_at) : "Ora"}</time>
                <div className="document-row__actions">
                  {document.public_state === "private" && <button type="button" disabled={busy} onClick={() => void propose(document, true)}>Proponi al pubblico</button>}
                  {document.public_state === "draft" && <Link href="/studio/spazio">Controlla la bozza</Link>}
                  {document.public_state === "active" && <button type="button" disabled={busy} onClick={() => void propose(document, false)}>Prepara rimozione</button>}
                  <button className="document-row__delete" type="button" disabled={busy} onClick={() => void remove(document)}>Elimina</button>
                </div>
              </motion.article>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}
