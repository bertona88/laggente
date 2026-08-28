import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AppLink as Link, useAppNavigate } from "@/components/app-link";
import {
  ArrowLeftIcon,
  CheckIcon,
  DocumentIcon,
  EditIcon,
  PauseIcon,
  PlayIcon,
  SendIcon,
  SparkIcon,
} from "@/components/icons";
import { ConversationDocument } from "@/components/conversation-document";
import { ConversationPhoto } from "@/components/conversation-photo";
import { MessageContent } from "@/components/message-markdown";
import { InlineError, LoadingLine } from "@/components/status";
import { useStudioSession } from "@/components/studio-shell";
import {
  apiRequest,
  documentFromUploadResponse,
  normalizeMessages,
  resolveMessageResponse,
} from "@/lib/api";
import { createClientMessageAttemptTracker } from "@/lib/client-message-id";
import { confirmConversationDeletion } from "@/lib/conversation-deletion";
import { formatDateTime, formatTime, initials } from "@/lib/format";
import type {
  ConversationDocument as ConversationDocumentValue,
  ConversationMessage,
  MemoryItem,
  StudioConversationDetail,
} from "@/lib/types";
import { startVisiblePolling } from "@/lib/visible-polling";
import { isNearThreadBottom, shouldAutoScrollThread } from "@/lib/thread-scroll";

function normalizeDetail(value: unknown, id: string, fallbackSlug = ""): StudioConversationDetail {
  const object = (value || {}) as Record<string, unknown>;
  const conversation = (object.conversation && typeof object.conversation === "object" ? object.conversation : object) as Record<string, unknown>;
  return {
    id: String(conversation.id || id),
    space_slug: String(conversation.space_slug || fallbackSlug),
    messages: normalizeMessages(object.messages || conversation.messages),
    visitor_name: String(conversation.visitor_name || object.visitor_name || "") || null,
    summary: String(conversation.summary || object.summary || "") || null,
    attention_reason: String(object.attention_reason || conversation.attention_reason || "") || null,
    memory_items: Array.isArray(object.memory_items) ? object.memory_items as MemoryItem[] : Array.isArray(object.memories) ? object.memories as MemoryItem[] : [],
    professional_present: Boolean(object.professional_present ?? conversation.professional_present ?? conversation.professional_joined),
    automatic_replies_enabled: Boolean(object.automatic_replies_enabled ?? conversation.automatic_replies_enabled ?? conversation.automatic_ai_enabled ?? true),
    created_at: String(conversation.created_at || ""),
    updated_at: String(conversation.updated_at || ""),
  };
}

export function ThreadMessage({ message }: { message: ConversationMessage }) {
  if (message.author_type === "system") return <div className="conversation-event">{message.content}</div>;
  const human = message.author_type === "professional";
  const ai = message.author_type === "public_assistant";
  return (
    <motion.article layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: message.pending ? 0.55 : 1, y: 0 }} className={`detail-message detail-message--${message.author_type}`} id={`message-${message.id}`}>
      {(human || ai) && <span className={`speaker-mark speaker-mark--${human ? "human" : "ai"}`}>{human ? initials(message.author_name) || "P" : "AI"}</span>}
      <div>
        <header><strong>{message.author_name}</strong><time dateTime={message.created_at}>{formatTime(message.created_at)}</time></header>
        <ConversationPhoto attachment={message.attachment} surface="studio" />
        <ConversationDocument document={message.document} />
        <MessageContent authorType={message.author_type} content={message.content} />
      </div>
    </motion.article>
  );
}

function MemoryRow({ item, conversationId, onSaved }: { item: MemoryItem; conversationId: string; onSaved: (item: MemoryItem) => void }) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(item.corrected_content || item.content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!content.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const result = await apiRequest<MemoryItem | { memory: MemoryItem }>(`/studio/conversations/${encodeURIComponent(conversationId)}/memory/${encodeURIComponent(item.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ content: content.trim(), status: "corrected" }),
      });
      onSaved("memory" in result ? result.memory : result);
      setEditing(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Correzione non salvata.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="memory-row">
      <div className="memory-row__top"><span>{item.kind === "question" || item.kind === "open_question" ? "Domanda aperta" : item.kind === "signal" ? "Da notare" : item.label || "Memoria"}</span><button type="button" onClick={() => setEditing((value) => !value)} aria-label={`Correggi: ${item.content}`}><EditIcon /></button></div>
      {editing ? (
        <div className="memory-edit"><textarea value={content} onChange={(event) => setContent(event.target.value)} rows={3} aria-label="Testo corretto" />{error && <p role="alert">{error}</p>}<div><button type="button" onClick={() => { setEditing(false); setContent(item.corrected_content || item.content); }}>Annulla</button><button type="button" onClick={() => void save()} disabled={saving || !content.trim()}>{saving ? "Salvo…" : "Salva correzione"}<CheckIcon /></button></div></div>
      ) : (
        <><p>{item.corrected_content || item.content}</p>{item.source_message_ids?.length ? <a href={`#message-${item.source_message_ids[0]}`}>Vedi il messaggio d’origine</a> : null}</>
      )}
    </div>
  );
}

export function ConversationDetail({ conversationId }: { conversationId: string }) {
  const { session } = useStudioSession();
  const studioSpaceSlug = session?.space?.slug || "";
  const navigate = useAppNavigate();
  const reduceMotion = useReducedMotion();
  const [detail, setDetail] = useState<StudioConversationDetail | null>(null);
  const [input, setInput] = useState("");
  const [joined, setJoined] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [joinBusy, setJoinBusy] = useState(false);
  const [controlBusy, setControlBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [pendingDocument, setPendingDocument] = useState<ConversationDocumentValue | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);
  const previousLastMessageIdRef = useRef<string | null>(null);
  const attemptTrackerRef = useRef(createClientMessageAttemptTracker());

  const load = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
      setError(null);
    }
    try {
      const result = await apiRequest<unknown>(`/studio/conversations/${encodeURIComponent(conversationId)}`);
      const normalized = normalizeDetail(result, conversationId, studioSpaceSlug);
      setDetail(normalized);
      setJoined(normalized.professional_present);
    } catch (reason) {
      if (!background) {
        setError(reason instanceof Error ? reason.message : "Non è stato possibile aprire la conversazione.");
      }
    } finally {
      if (!background) setLoading(false);
    }
  }, [conversationId, studioSpaceSlug]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => startVisiblePolling(
    () => {
      if (sending || joinBusy || controlBusy) return;
      return load(true);
    },
    { intervalMs: 5_500 },
  ), [controlBusy, joinBusy, load, sending]);
  const lastMessageId = detail?.messages.at(-1)?.id || null;
  useEffect(() => {
    if (shouldAutoScrollThread(
      previousLastMessageIdRef.current,
      lastMessageId,
      nearBottomRef.current,
      sending,
    )) {
      bottomRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    }
    previousLastMessageIdRef.current = lastMessageId;
  }, [lastMessageId, reduceMotion, sending]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = input.trim();
    if ((!content && !pendingDocument) || sending || uploadingDocument || !detail) return;
    const clientMessageId = attemptTrackerRef.current.idFor(content, pendingDocument?.id);
    const optimistic: ConversationMessage = {
      id: `pending-${clientMessageId}`,
      author_type: "professional",
      author_name: session?.member.display_name || "Professionista",
      content: content || `Ho condiviso il documento “${pendingDocument?.name}”.`,
      created_at: new Date().toISOString(),
      pending: true,
      document: pendingDocument,
    };
    setDetail({ ...detail, messages: [...detail.messages, optimistic], professional_present: true, automatic_replies_enabled: false });
    setJoined(true);
    setInput("");
    setSending(true);
    setError(null);
    try {
      const result = await apiRequest<unknown>(`/studio/conversations/${encodeURIComponent(conversationId)}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content,
          client_message_id: clientMessageId,
          ...(pendingDocument ? { document_id: pendingDocument.id } : {}),
        }),
      });
      const object = (result || {}) as Record<string, unknown>;
      if (object.conversation || object.memory_items || object.automatic_replies_enabled !== undefined) {
        setDetail(normalizeDetail(result, conversationId, studioSpaceSlug));
      } else {
        const returned = resolveMessageResponse(result) as ConversationMessage[];
        setDetail((current) => current ? { ...current, messages: [...current.messages.filter((message) => message.id !== optimistic.id), ...(returned.length ? returned : [{ ...optimistic, pending: false }])], professional_present: true, automatic_replies_enabled: false } : current);
      }
      setPendingDocument(null);
      attemptTrackerRef.current.complete(clientMessageId);
    } catch (reason) {
      setDetail((current) => current ? { ...current, messages: current.messages.filter((message) => message.id !== optimistic.id) } : current);
      setInput(content);
      setError(reason instanceof Error ? reason.message : "Il messaggio non è partito.");
    } finally {
      setSending(false);
    }
  }

  async function uploadDocument(file: File) {
    if (uploadingDocument || sending || pendingDocument) return;
    setUploadingDocument(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const result = await apiRequest<unknown>(
        `/studio/conversations/${encodeURIComponent(conversationId)}/documents`,
        { method: "POST", body: form },
      );
      const document = documentFromUploadResponse(result);
      if (!document) throw new Error("Il documento caricato non è disponibile.");
      setPendingDocument(document);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Il documento non è stato caricato.");
    } finally {
      setUploadingDocument(false);
    }
  }

  async function setAssistant(enabled: boolean) {
    if (!detail) return;
    setControlBusy(true);
    setError(null);
    try {
      await apiRequest(`/studio/conversations/${encodeURIComponent(conversationId)}/assistant-control`, { method: "POST", body: JSON.stringify({ automatic_replies_enabled: enabled }) });
      setDetail({ ...detail, automatic_replies_enabled: enabled });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile cambiare il controllo delle risposte.");
    } finally {
      setControlBusy(false);
    }
  }

  async function joinConversation() {
    setJoinBusy(true);
    setError(null);
    try {
      const result = await apiRequest<unknown>(`/studio/conversations/${encodeURIComponent(conversationId)}/join`, { method: "POST" });
      setDetail(normalizeDetail(result, conversationId, studioSpaceSlug));
      setJoined(true);
      setTimeout(() => inputRef.current?.focus(), 50);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile entrare nella conversazione.");
    } finally {
      setJoinBusy(false);
    }
  }

  async function deleteConversation() {
    if (!confirmConversationDeletion("professional")) return;
    setDeleteBusy(true);
    setError(null);
    try {
      await apiRequest(`/studio/conversations/${encodeURIComponent(conversationId)}`, {
        method: "DELETE",
      });
      navigate("/studio/conversazioni", { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile eliminare la conversazione.");
      setDeleteBusy(false);
    }
  }

  if (loading) return <div className="detail-loading"><LoadingLine label="Apro la conversazione…" /></div>;
  if (!detail) return <div className="detail-loading">{error && <InlineError message={error} retry={load} />}</div>;
  const visitorName = detail.visitor_name || "Visitatore";
  const professionalName = session?.member.display_name || "il professionista";
  const professionalFirstName = professionalName.split(/\s+/)[0] || "il professionista";
  const professionalInitials = initials(professionalName) || "P";
  const sharedDocuments = detail.messages.flatMap(
    (message) => message.document ? [message.document] : [],
  );

  return (
    <section className="conversation-detail">
      <header className="detail-header">
        <Link href="/studio/conversazioni" aria-label="Torna alle conversazioni"><ArrowLeftIcon /></Link>
        <div><p>Conversazione pubblica</p><h1>{visitorName}</h1><span>{detail.updated_at ? `Ultimo aggiornamento ${formatDateTime(detail.updated_at)}` : `Spazio di ${professionalName}`}</span></div>
        <button type="button" className="detail-context-toggle" onClick={() => setContextOpen(true)} aria-expanded={contextOpen} aria-controls="conversation-context"><SparkIcon /> Contesto</button>
        <div className={`assistant-control${detail.automatic_replies_enabled ? " is-on" : " is-paused"}`}>
          <div><i /><span><strong>{detail.automatic_replies_enabled ? "Assistente attivo" : "Assistente in pausa"}</strong><small>{detail.automatic_replies_enabled ? "Può rispondere automaticamente" : `Risponde solo ${professionalFirstName}`}</small></span></div>
          <button type="button" disabled={controlBusy} onClick={() => void setAssistant(!detail.automatic_replies_enabled)}>
            {detail.automatic_replies_enabled ? <><PauseIcon /> Metti in pausa</> : <><PlayIcon /> Riattiva</>}
          </button>
        </div>
      </header>
      {error && <div className="detail-error"><InlineError message={error} /></div>}
      <div className="detail-layout">
        <div className="detail-thread-column">
          <div
            ref={threadRef}
            className="detail-thread"
            aria-live="polite"
            onScroll={() => {
              if (threadRef.current) nearBottomRef.current = isNearThreadBottom(threadRef.current);
            }}
          >
            {detail.messages.map((message) => <ThreadMessage key={message.id} message={message} />)}
            {!detail.messages.length && <div className="thread-empty">Questa conversazione non contiene ancora messaggi.</div>}
            <div ref={bottomRef} />
          </div>
          {!joined && (
            <motion.div className="join-prompt" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <span className="speaker-mark speaker-mark--human">{professionalInitials}</span>
              <div><strong>Vuoi entrare nella conversazione?</strong><p>Il tuo primo messaggio sarà firmato da te e metterà in pausa le risposte automatiche.</p></div>
              <button type="button" disabled={joinBusy} onClick={() => void joinConversation()}>{joinBusy ? "Ingresso…" : `Entra come ${professionalFirstName}`}</button>
            </motion.div>
          )}
          <AnimatePresence>
            {joined && (
              <motion.form className="professional-composer" onSubmit={submit} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <div className="professional-composer__identity"><span>{professionalInitials}</span><strong>Stai scrivendo come {professionalName}</strong></div>
                <input
                  ref={documentInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.md,.markdown,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/csv"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void uploadDocument(file);
                    event.currentTarget.value = "";
                  }}
                />
                {pendingDocument && <div className="professional-document-draft"><ConversationDocument document={pendingDocument} compact /><button type="button" onClick={() => setPendingDocument(null)}>Rimuovi</button></div>}
                <textarea ref={inputRef} value={input} onChange={(event) => { attemptTrackerRef.current.invalidate(); setInput(event.target.value); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} rows={2} placeholder="Scrivi alla persona…" aria-label={`Messaggio di ${professionalName}`} />
                <div><button className="professional-composer__document" type="button" disabled={sending || uploadingDocument || Boolean(pendingDocument)} onClick={() => documentInputRef.current?.click()}><DocumentIcon /> {uploadingDocument ? "Carico…" : "Documento"}</button><span>L’assistente andrà in pausa automaticamente.</span><button type="submit" disabled={sending || uploadingDocument || (!input.trim() && !pendingDocument)}>{sending ? "Invio…" : `Invia come ${professionalFirstName}`}<SendIcon /></button></div>
              </motion.form>
            )}
          </AnimatePresence>
        </div>
        <AnimatePresence>
          {contextOpen && <motion.button type="button" className="conversation-context-backdrop" aria-label="Chiudi il contesto" onClick={() => setContextOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />}
        </AnimatePresence>
        <aside id="conversation-context" className={`conversation-context${contextOpen ? " is-open" : ""}`}>
          <button type="button" className="conversation-context__close" onClick={() => setContextOpen(false)}>Chiudi</button>
          <section>
            <p className="context-label">In breve</p>
            <h2>{detail.summary || "La conversazione sta ancora prendendo forma."}</h2>
          </section>
          {detail.attention_reason && <section className="attention-note"><SparkIcon /><div><p>Perché guardarla</p><strong>{detail.attention_reason}</strong></div></section>}
          <section className="context-documents">
            <header><p className="context-label">Documenti condivisi</p><span>{sharedDocuments.length}</span></header>
            <p>Visibili alla persona, a te e agli assistenti soltanto dentro questa conversazione.</p>
            {sharedDocuments.length
              ? sharedDocuments.map((document) => <ConversationDocument key={document.id} document={document} compact />)
              : <small>Nessun documento condiviso.</small>}
          </section>
          <section className="memory-section">
            <header><div><p className="context-label">Memoria correggibile</p><span>{detail.memory_items.length} elementi derivati</span></div></header>
            {detail.memory_items.length ? detail.memory_items.map((item) => <MemoryRow key={item.id} item={item} conversationId={conversationId} onSaved={(updated) => setDetail((current) => current ? { ...current, memory_items: current.memory_items.map((memory) => memory.id === updated.id ? updated : memory) } : current)} />) : <p className="memory-empty">LAGGENTE non ha ancora derivato informazioni utili. I messaggi originali restano comunque qui.</p>}
          </section>
          <section className="conversation-danger">
            <p className="context-label">Controllo dei dati</p>
            <p>Rimuove definitivamente messaggi, memoria derivata e allegati da questa conversazione.</p>
            <button type="button" disabled={deleteBusy} onClick={() => void deleteConversation()}>{deleteBusy ? "Eliminazione…" : "Elimina conversazione"}</button>
          </section>
        </aside>
      </div>
    </section>
  );
}
