import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AppLink as Link } from "@/components/app-link";
import {
  ArrowLeftIcon,
  ArrowUpRightIcon,
  DocumentIcon,
  ImageIcon,
  LockIcon,
  MicIcon,
  SendIcon,
} from "@/components/icons";
import { ConversationDocument } from "@/components/conversation-document";
import { ConversationPhoto } from "@/components/conversation-photo";
import { Logo } from "@/components/logo";
import { MessageContent } from "@/components/message-markdown";
import { InlineError, LoadingLine } from "@/components/status";
import {
  apiRequest,
  documentFromUploadResponse,
  isInactiveConversation,
  normalizeMessages,
  reconcileMessages,
  resolveMessageResponse,
  shouldForgetSavedConversation,
} from "@/lib/api";
import { createClientMessageAttemptTracker } from "@/lib/client-message-id";
import { confirmConversationDeletion, shouldDisableConversationDeletion } from "@/lib/conversation-deletion";
import { formatTime, initials } from "@/lib/format";
import {
  acceptResolvedMediaStream,
  finishMediaCaptureRequest,
  releaseMediaCapture,
  shouldDisableMicrophoneControl,
  tryBeginMediaCaptureRequest,
} from "@/lib/media-capture";
import { normalizeSpace } from "@/lib/space-adapter";
import { createSingleFlight } from "@/lib/single-flight";
import type {
  ConversationAttachment,
  ConversationDocument as ConversationDocumentValue,
  ConversationMessage,
  ProfessionalSpace,
  PublicConversation,
} from "@/lib/types";
import { startVisiblePolling } from "@/lib/visible-polling";
import {
  pendingAudioDraftFromUpload,
  shouldDisablePublicComposerSubmit,
  shouldBlockPublicMessageSubmission,
  submitUploadedImage,
} from "@/lib/public-attachments";
import { publicConversationCreateEndpoint, publicSpaceEndpoint } from "@/lib/public-routing";
import { isNearThreadBottom, shouldAutoScrollThread } from "@/lib/thread-scroll";

function normalizeConversation(value: unknown, slug: string): PublicConversation {
  const object = (value || {}) as Record<string, unknown>;
  const candidate = (object.conversation && typeof object.conversation === "object" ? object.conversation : object) as Partial<PublicConversation>;
  return {
    id: String(candidate.id || object.conversation_id || ""),
    space_slug: candidate.space_slug || slug,
    messages: normalizeMessages(object.messages || candidate.messages),
    automatic_replies_enabled: candidate.automatic_replies_enabled ?? (candidate as unknown as Record<string, unknown>).automatic_ai_enabled !== false,
    professional_present: Boolean(candidate.professional_present ?? (candidate as unknown as Record<string, unknown>).professional_joined),
  };
}

function welcomeMessage(space: ProfessionalSpace): ConversationMessage {
  return {
    id: `welcome-${space.slug}`,
    author_type: "public_assistant",
    author_name: space.assistant_disclosure,
    content: space.welcome_message,
    // Synthetic pre-conversation copy stays deterministic until a durable thread exists.
    created_at: "",
  };
}

export function MessageBubble({ message }: { message: ConversationMessage }) {
  const assistant = message.author_type === "public_assistant";
  const professional = message.author_type === "professional";
  if (message.author_type === "system") {
    return <div className="chat-system" role="status">{message.content}</div>;
  }
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: message.pending ? 0.62 : 1, y: 0 }}
      className={`chat-message chat-message--${message.author_type}`}
      aria-label={`Messaggio di ${message.author_name}`}
    >
      {(assistant || professional) && (
        <div className="chat-message__author">
          <span className={`speaker-mark speaker-mark--${professional ? "human" : "ai"}`} aria-hidden="true">
            {professional ? initials(message.author_name) || "P" : "AI"}
          </span>
          <strong>{message.author_name}</strong>
        </div>
      )}
      <div className="chat-message__body">
        <ConversationPhoto attachment={message.attachment} surface="public" />
        <ConversationDocument document={message.document} />
        <MessageContent authorType={message.author_type} content={message.content} />
        {message.created_at && <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>}
      </div>
    </motion.article>
  );
}

export function PublicSpace({ slug }: { slug: string }) {
  const reduceMotion = useReducedMotion();
  const [space, setSpace] = useState<ProfessionalSpace>(() => normalizeSpace(null, slug));
  const [spaceLoading, setSpaceLoading] = useState(true);
  const [spaceError, setSpaceError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [automaticRepliesEnabled, setAutomaticRepliesEnabled] = useState(true);
  const [professionalPresent, setProfessionalPresent] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pendingAudioAttachmentId, setPendingAudioAttachmentId] = useState<string | null>(null);
  const [pendingImageAttachment, setPendingImageAttachment] = useState<ConversationAttachment | null>(null);
  const [pendingDocument, setPendingDocument] = useState<ConversationDocumentValue | null>(null);
  const [recording, setRecording] = useState(false);
  const [requestingMicrophone, setRequestingMicrophone] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [identityOpen, setIdentityOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);
  const previousLastMessageIdRef = useRef<string | null>(null);
  const attemptTrackerRef = useRef(createClientMessageAttemptTracker());
  const deletionGenerationRef = useRef(0);
  const conversationIdRef = useRef<string | null>(null);
  const conversationCreationRef = useRef(createSingleFlight<string>());
  const imageInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const disposedRef = useRef(false);
  const mediaCaptureRequestGateRef = useRef({ busy: false });
  const recordingChunks = useRef<Blob[]>([]);

  const storageKey = useMemo(() => `laggente:conversation:${slug}`, [slug]);

  const loadSpace = useCallback(async () => {
    setSpaceLoading(true);
    setSpaceError(null);
    try {
      const data = await apiRequest<unknown>(publicSpaceEndpoint(slug));
      setSpace(normalizeSpace(data, slug));
    } catch (error) {
      setSpaceError(error instanceof Error ? error.message : "Lo spazio non è disponibile in questo momento.");
    } finally {
      setSpaceLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    void loadSpace();
  }, [loadSpace]);

  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      releaseMediaCapture(recorderRef.current, recordingStreamRef.current);
      recorderRef.current = null;
      recordingStreamRef.current = null;
    };
  }, []);

  const refreshConversation = useCallback(async (id: string) => {
    const deletionGeneration = deletionGenerationRef.current;
    const data = await apiRequest<unknown>(`/public/conversations/${encodeURIComponent(id)}`);
    if (
      deletionGeneration !== deletionGenerationRef.current
      || conversationIdRef.current !== id
    ) return;
    const conversation = normalizeConversation(data, slug);
    setAutomaticRepliesEnabled(conversation.automatic_replies_enabled !== false);
    setProfessionalPresent(Boolean(conversation.professional_present));
    if (conversation.messages.length) {
      setMessages((current) => reconcileMessages(current, conversation.messages));
    }
  }, [slug]);

  const showInactiveConversation = useCallback((error: unknown) => {
    if (!isInactiveConversation(error)) return false;
    setSpaceError(error instanceof Error ? error.message : "Spazio non attivo");
    setComposerError(
      "Questo spazio non è più disponibile. La conversazione resta conservata e può essere eliminata.",
    );
    return true;
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey);
    if (!saved) return;
    setConversationId(saved);
    conversationIdRef.current = saved;
    const deletionGeneration = deletionGenerationRef.current;
    refreshConversation(saved).catch((error) => {
      if (
        deletionGeneration !== deletionGenerationRef.current
        || conversationIdRef.current !== saved
      ) return;
      if (shouldForgetSavedConversation(error)) {
        window.localStorage.removeItem(storageKey);
        setConversationId(null);
        conversationIdRef.current = null;
        return;
      }
      if (showInactiveConversation(error)) return;
      setComposerError("Non riesco ad aggiornare la conversazione. Il filo è conservato: riproverò tra poco.");
    });
  }, [refreshConversation, showInactiveConversation, storageKey]);

  useEffect(() => {
    if (!conversationId) return;
    return startVisiblePolling(
      () => {
        if (sending || uploading) return;
        return refreshConversation(conversationId).catch((error) => {
          showInactiveConversation(error);
        });
      },
      { intervalMs: 4_500 },
    );
  }, [conversationId, refreshConversation, sending, showInactiveConversation, uploading]);

  const lastMessageId = messages.at(-1)?.id || null;
  useEffect(() => {
    if (shouldAutoScrollThread(
      previousLastMessageIdRef.current,
      lastMessageId,
      nearBottomRef.current,
      sending,
    )) {
      bottomRef.current?.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
    }
    previousLastMessageIdRef.current = lastMessageId;
  }, [lastMessageId, sending, reduceMotion]);

  const visibleMessages = messages.length ? messages : [welcomeMessage(space)];
  const sharedDocuments = useMemo(
    () => messages.flatMap((message) => message.document ? [message.document] : []),
    [messages],
  );
  const professionalFirstName = space.professional_name.trim().split(/\s+/)[0] || "Il professionista";
  const assistantStatus = automaticRepliesEnabled
    ? "Disponibile ora"
    : professionalPresent
      ? `${professionalFirstName} risponde qui`
      : "Assistente in pausa";

  if (spaceError && !spaceLoading) {
    return (
      <main className="unknown-space">
        <Logo />
        <div>
          <p className="eyebrow">Spazio non disponibile</p>
          <h1>Non riesco ad aprire questo spazio.</h1>
          <p>Controlla l’indirizzo oppure riprova. Nessun messaggio può essere inviato finché il collegamento sicuro non torna disponibile.</p>
          <button className="button button--ink" type="button" onClick={() => void loadSpace()}>Riprova</button>
          {conversationId && (
            <button className="button button--ink" type="button" disabled={deleting} onClick={() => void deleteConversation()}>
              {deleting ? "Eliminazione…" : "Elimina la conversazione conservata"}
            </button>
          )}
          {composerError && <InlineError message={composerError} />}
          <Link className="button button--ink" href="https://laggente.com">Torna alla pagina iniziale <ArrowUpRightIcon /></Link>
        </div>
      </main>
    );
  }

  async function ensureConversation() {
    if (conversationIdRef.current) return conversationIdRef.current;
    return conversationCreationRef.current.run(async () => {
      const data = await apiRequest<unknown>(publicConversationCreateEndpoint(slug), {
        method: "POST",
        body: JSON.stringify({
          privacy_notice_version: space.privacy_notice_version,
          privacy_notice_acknowledged: true,
        }),
      });
      const conversation = normalizeConversation(data, slug);
      if (!conversation.id) throw new Error("Non è stato possibile iniziare la conversazione.");
      setAutomaticRepliesEnabled(conversation.automatic_replies_enabled !== false);
      setProfessionalPresent(Boolean(conversation.professional_present));
      conversationIdRef.current = conversation.id;
      setConversationId(conversation.id);
      window.localStorage.setItem(storageKey, conversation.id);
      if (conversation.messages.length) setMessages(conversation.messages);
      return conversation.id;
    });
  }

  async function submitMessage(
    value: string,
    attachmentId?: string,
    optimisticAttachment?: ConversationAttachment | null,
    resolvedConversationId?: string,
    documentId?: string,
    optimisticDocument?: ConversationDocumentValue | null,
  ) {
    const content = value.trim();
    if (shouldBlockPublicMessageSubmission({
      hasContent: Boolean(content),
      hasAttachment: Boolean(attachmentId || documentId),
      sending,
      uploading,
      captureActive: Boolean(recorderRef.current) || mediaCaptureRequestGateRef.current.busy,
      isResolvedUploadContinuation: Boolean(resolvedConversationId),
    })) return;
    const clientMessageId = attemptTrackerRef.current.idFor(content, attachmentId || documentId);
    setSending(true);
    setComposerError(null);
    const optimistic: ConversationMessage = {
      id: `pending-${clientMessageId}`,
      author_type: "visitor",
      author_name: "Tu",
      content: content || (optimisticDocument ? `Documento condiviso: ${optimisticDocument.name}` : "Fotografia condivisa"),
      created_at: new Date().toISOString(),
      pending: true,
      attachment: optimisticAttachment,
      document: optimisticDocument,
    };
    setMessages((current) => [...(current.length ? current : [welcomeMessage(space)]), optimistic]);
    setInput("");
    try {
      const id = resolvedConversationId || await ensureConversation();
      const data = await apiRequest<unknown>(`/public/conversations/${encodeURIComponent(id)}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content,
          client_message_id: clientMessageId,
          ...(attachmentId ? { attachment_id: attachmentId } : {}),
          ...(documentId ? { document_id: documentId } : {}),
        }),
      });
      const conversation = normalizeConversation(data, slug);
      setAutomaticRepliesEnabled(conversation.automatic_replies_enabled !== false);
      setProfessionalPresent(Boolean(conversation.professional_present));
      const returned = resolveMessageResponse(data) as ConversationMessage[];
      const visitor = returned.find((message) => message.author_type === "visitor");
      const otherReturned = returned.filter((message) => message.id !== visitor?.id);
      setMessages((current) => [
        ...current.filter((message) => message.id !== optimistic.id),
        visitor || { ...optimistic, id: `visitor-${clientMessageId}`, pending: false },
        ...otherReturned,
      ]);
      if (attachmentId && attachmentId === pendingAudioAttachmentId) {
        setPendingAudioAttachmentId(null);
      }
      if (attachmentId && attachmentId === pendingImageAttachment?.id) {
        setPendingImageAttachment(null);
      }
      if (documentId && documentId === pendingDocument?.id) {
        setPendingDocument(null);
      }
      attemptTrackerRef.current.complete(clientMessageId);
    } catch (error) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      setInput(content);
      if (optimisticAttachment?.kind === "image") {
        setPendingImageAttachment(optimisticAttachment);
      }
      if (optimisticDocument) setPendingDocument(optimisticDocument);
      setComposerError(error instanceof Error ? error.message : "Il messaggio non è partito. Riprova.");
    } finally {
      setSending(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (pendingDocument) {
      await submitMessage(
        input,
        undefined,
        null,
        undefined,
        pendingDocument.id,
        pendingDocument,
      );
      return;
    }
    if (pendingImageAttachment) {
      await submitMessage(input, pendingImageAttachment.id, pendingImageAttachment);
      return;
    }
    await submitMessage(input, pendingAudioAttachmentId || undefined);
  }

  async function uploadAttachment(file: File | Blob, kind: "image" | "audio") {
    if (recorderRef.current || mediaCaptureRequestGateRef.current.busy) {
      setComposerError("Termina prima la registrazione vocale.");
      return;
    }
    if (pendingAudioAttachmentId || pendingImageAttachment || pendingDocument) {
      setComposerError("Invia prima l’allegato già pronto, poi potrai aggiungerne un altro.");
      return;
    }
    setUploading(true);
    setComposerError(null);
    try {
      const id = await ensureConversation();
      const form = new FormData();
      form.append("kind", kind);
      form.append("file", file, file instanceof File ? file.name : "nota-vocale.webm");
      const result = await apiRequest<unknown>(
        `/public/conversations/${encodeURIComponent(id)}/attachments`,
        { method: "POST", body: form },
      );
      if (kind === "audio") {
        const draft = pendingAudioDraftFromUpload(result);
        if (!draft) throw new Error("La nota vocale non è stata associata alla trascrizione.");
        setPendingAudioAttachmentId(draft.attachmentId);
        setInput(draft.transcript);
      } else {
        await submitUploadedImage(result, id, submitMessage);
      }
    } catch (error) {
      setComposerError(error instanceof Error ? error.message : "Non è stato possibile caricare il file.");
    } finally {
      setUploading(false);
    }
  }

  async function uploadDocument(file: File) {
    if (recording || requestingMicrophone || sending || uploading) return;
    if (pendingAudioAttachmentId || pendingImageAttachment || pendingDocument) {
      setComposerError("Invia prima l’allegato già pronto, poi potrai aggiungerne un altro.");
      return;
    }
    setUploading(true);
    setComposerError(null);
    try {
      const id = await ensureConversation();
      const form = new FormData();
      form.append("file", file, file.name);
      const result = await apiRequest<unknown>(
        `/public/conversations/${encodeURIComponent(id)}/documents`,
        { method: "POST", body: form },
      );
      const document = documentFromUploadResponse(result);
      if (!document) throw new Error("Il documento caricato non è disponibile.");
      setPendingDocument(document);
    } catch (error) {
      setComposerError(error instanceof Error ? error.message : "Non è stato possibile caricare il documento.");
    } finally {
      setUploading(false);
    }
  }

  async function toggleRecording() {
    if (recorderRef.current) {
      if (recorderRef.current.state !== "inactive") recorderRef.current.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setComposerError("La registrazione vocale non è supportata da questo browser.");
      return;
    }
    if (!tryBeginMediaCaptureRequest(mediaCaptureRequestGateRef.current)) return;
    setRequestingMicrophone(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!acceptResolvedMediaStream(stream, disposedRef.current)) return;
      const recorder = new MediaRecorder(stream);
      recordingStreamRef.current = stream;
      recordingChunks.current = [];
      recorder.ondataavailable = (event) => event.data.size && recordingChunks.current.push(event.data);
      recorder.onstop = () => {
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
        recorderRef.current = null;
        const blob = new Blob(recordingChunks.current, { type: recorder.mimeType || "audio/webm" });
        void uploadAttachment(blob, "audio");
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      if (!disposedRef.current) {
        setComposerError("Per registrare una nota vocale, autorizza l’accesso al microfono.");
      }
    } finally {
      finishMediaCaptureRequest(mediaCaptureRequestGateRef.current);
      if (!disposedRef.current) setRequestingMicrophone(false);
    }
  }

  async function deleteConversation() {
    const captureActive = Boolean(recorderRef.current) || mediaCaptureRequestGateRef.current.busy;
    if (shouldDisableConversationDeletion({ deleting, sending, uploading, captureActive })) {
      setComposerError("Attendi che il messaggio o la registrazione in corso sia terminata.");
      return;
    }
    if (!conversationId || !confirmConversationDeletion("visitor")) return;
    // Invalidate any refresh already in flight so it cannot repopulate or overwrite the outcome
    // of this explicit privacy action.
    deletionGenerationRef.current += 1;
    setDeleting(true);
    setComposerError(null);
    try {
      await apiRequest(`/public/conversations/${encodeURIComponent(conversationId)}`, {
        method: "DELETE",
      });
      window.localStorage.removeItem(storageKey);
      conversationIdRef.current = null;
      setConversationId(null);
      setMessages([]);
      setAutomaticRepliesEnabled(true);
      setProfessionalPresent(false);
      setInput("");
      setPendingAudioAttachmentId(null);
      setPendingImageAttachment(null);
      setPendingDocument(null);
      attemptTrackerRef.current.invalidate();
      setPrivacyOpen(false);
      setComposerError("La conversazione e i suoi allegati sono stati eliminati.");
    } catch (error) {
      setComposerError(error instanceof Error ? error.message : "Non è stato possibile eliminare la conversazione.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="public-space">
      <section className="public-identity" aria-labelledby="professional-name">
        <img
          className="public-identity__image"
          src={space.hero_image_url || "/images/laggente-hero.webp"}
          alt={`Lo spazio professionale di ${space.professional_name}`}
          sizes="(max-width: 800px) 100vw, 54vw"
          fetchPriority="high"
        />
        <div className="public-identity__veil" />
        <div className="public-identity__top">
          <Logo href="https://laggente.com" inverse />
          <Link href="https://laggente.com" aria-label="Torna a LAGGENTE"><ArrowLeftIcon /> LAGGENTE</Link>
        </div>
        <motion.div
          className="public-identity__content"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <p className="eyebrow eyebrow--light">{space.territory || "Presenza locale"}</p>
          <h1 id="professional-name">{space.professional_name}</h1>
          <p>{space.professional_role}{space.agency ? ` · ${space.agency}` : ""}</p>
          <div className="public-identity__promise">
            <i aria-hidden="true" />
            <span>Una conversazione riservata.<br />{space.professional_name} può raggiungerci qui.</span>
          </div>
        </motion.div>
      </section>

      <section className="public-chat" aria-label={`Conversazione con l’assistente AI di ${space.professional_name}`}>
        <header className="public-chat__header">
          <button
            className="public-chat__professional"
            type="button"
            onClick={() => setIdentityOpen((value) => !value)}
            aria-expanded={identityOpen}
            aria-controls="public-professional-context"
          >
            <img src={space.hero_image_url || "/images/laggente-hero.webp"} alt="" />
            <span><strong>{space.professional_name}</strong><small>{space.territory || space.professional_role}</small></span>
          </button>
          <div className={`public-chat__assistant-status${automaticRepliesEnabled ? "" : " is-paused"}${professionalPresent ? " is-human-followup" : ""}`}>
            <span className="speaker-mark speaker-mark--ai" aria-hidden="true">AI</span>
            <div><strong>{space.assistant_disclosure}</strong><span>{assistantStatus}</span></div>
          </div>
          <button type="button" onClick={() => setDocumentsOpen((value) => !value)} aria-expanded={documentsOpen} aria-controls="public-shared-documents">
            <DocumentIcon /> Documenti{sharedDocuments.length ? ` (${sharedDocuments.length})` : ""}
          </button>
          <button type="button" onClick={() => setPrivacyOpen((value) => !value)} aria-expanded={privacyOpen}>
            <LockIcon /> Privacy
          </button>
        </header>

        <AnimatePresence>
          {identityOpen && (
            <motion.aside
              id="public-professional-context"
              className="public-professional-context"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <p><strong>{space.professional_name}</strong><span>{space.professional_role}{space.agency ? ` · ${space.agency}` : ""}</span></p>
              <small>{space.territory || "Presenza locale"} · Può raggiungere questa conversazione e risponderti personalmente.</small>
            </motion.aside>
          )}
          {privacyOpen && (
            <motion.aside
              className="privacy-note"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <LockIcon />
              <div className="privacy-note__content">
                <p><strong>Questa conversazione è privata.</strong> I messaggi sono conservati nello spazio di {space.professional_name} per darti continuità. Ogni autore è sempre identificato. <Link href="/privacy">Come trattiamo i dati <ArrowUpRightIcon /></Link></p>
                {conversationId && <button type="button" disabled={shouldDisableConversationDeletion({ deleting, sending, uploading, captureActive: recording || requestingMicrophone })} onClick={() => void deleteConversation()}>{deleting ? "Eliminazione…" : "Elimina questa conversazione"}</button>}
              </div>
            </motion.aside>
          )}
          {documentsOpen && (
            <motion.aside
              id="public-shared-documents"
              className="shared-documents-panel"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div><DocumentIcon /><p><strong>Documenti condivisi</strong><span>Visibili a te, a {professionalFirstName} e agli assistenti di questo spazio.</span></p></div>
              {sharedDocuments.length
                ? <div>{sharedDocuments.map((document) => <ConversationDocument key={document.id} document={document} compact />)}</div>
                : <p className="shared-documents-panel__empty">Non avete ancora condiviso documenti in questa conversazione.</p>}
            </motion.aside>
          )}
        </AnimatePresence>

        <div
          ref={threadRef}
          className="public-chat__messages"
          aria-live="polite"
          aria-busy={sending || spaceLoading}
          onScroll={() => {
            if (threadRef.current) nearBottomRef.current = isNearThreadBottom(threadRef.current);
          }}
        >
          {spaceLoading && <LoadingLine label={`Apro lo spazio di ${space.professional_name}…`} />}
          {spaceError && <InlineError message={spaceError} retry={loadSpace} />}
          {visibleMessages.map((message) => <MessageBubble key={message.id} message={message} />)}
          {!messages.length && !spaceLoading && (
            <div className="suggested-prompts" aria-label="Possibili inizi di conversazione">
              {(space.suggested_prompts || []).map((prompt) => (
                <button type="button" key={prompt} disabled={recording || requestingMicrophone || uploading || sending} onClick={() => void submitMessage(prompt)}>{prompt}<ArrowUpRightIcon /></button>
              ))}
            </div>
          )}
          {sending && automaticRepliesEnabled && (
            <div className="assistant-typing" role="status" aria-label="L’assistente sta scrivendo">
              <span /><span /><span />
            </div>
          )}
          {sending && !automaticRepliesEnabled && (
            <div className="chat-system" role="status">Invio il messaggio a {professionalFirstName}…</div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="public-chat__composer-wrap">
          {composerError && <InlineError message={composerError} />}
          {recording && <div className="recording-state" role="status"><i /> Registrazione in corso… <span>tocca il microfono per terminare</span></div>}
          {pendingAudioAttachmentId && !recording && <div className="recording-state" role="status"><i /> Trascrizione pronta <span>puoi correggerla prima di inviarla</span></div>}
          {pendingImageAttachment && <div className="recording-state" role="status"><i /> Fotografia pronta <span>riprova l’invio senza ricaricarla</span></div>}
          {pendingDocument && <div className="document-draft" role="status"><ConversationDocument document={pendingDocument} compact /><span>Puoi aggiungere un messaggio, poi inviare.</span></div>}
          {uploading && <LoadingLine label="Preparo il file in modo privato…" />}
          <p className="upload-notice">Continuando confermi di aver ricevuto l’<Link href="/privacy">informativa privacy</Link>; non è un consenso marketing. Condividi solo dati necessari. Foto, audio e documenti restano in questa conversazione; gli assistenti possono elaborarli secondo gli accessi indicati. L’audio viene eliminato dopo la trascrizione.</p>
          <form className="chat-composer" onSubmit={onSubmit}>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void uploadAttachment(file, "image");
                event.currentTarget.value = "";
              }}
            />
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
            <button type="button" className="chat-composer__utility" onClick={() => documentInputRef.current?.click()} disabled={recording || requestingMicrophone || uploading || sending || Boolean(pendingAudioAttachmentId || pendingImageAttachment || pendingDocument)} aria-label="Allega un documento">
              <DocumentIcon />
            </button>
            {space.capabilities.photographs && (
              <button type="button" className="chat-composer__utility" onClick={() => imageInputRef.current?.click()} disabled={recording || requestingMicrophone || uploading || sending || Boolean(pendingAudioAttachmentId || pendingImageAttachment || pendingDocument)} aria-label="Allega una fotografia">
                <ImageIcon />
              </button>
            )}
            {space.capabilities.voice_notes && (
              <button type="button" className={`chat-composer__utility${recording ? " is-recording" : ""}`} onClick={() => void toggleRecording()} disabled={shouldDisableMicrophoneControl({ recording, requesting: requestingMicrophone, sending, uploading, hasPendingAttachment: Boolean(pendingAudioAttachmentId || pendingImageAttachment || pendingDocument) })} aria-label={requestingMicrophone ? "Attendo il permesso per il microfono" : recording ? "Termina la registrazione" : "Registra una nota vocale"}>
                <MicIcon />
              </button>
            )}
            <textarea
              value={input}
              onChange={(event) => {
                attemptTrackerRef.current.invalidate();
                setInput(event.target.value);
                event.currentTarget.style.height = "0px";
                event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 112)}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={automaticRepliesEnabled ? "Scrivi ciò che hai in mente…" : `Scrivi a ${professionalFirstName}…`}
              aria-label="Il tuo messaggio"
              rows={1}
              maxLength={4000}
              disabled={recording || requestingMicrophone || sending || uploading}
            />
            <button
              className="chat-composer__send"
              type="submit"
              disabled={shouldDisablePublicComposerSubmit({
                hasContent: Boolean(input.trim()),
                hasPendingAttachment: Boolean(pendingImageAttachment || pendingAudioAttachmentId || pendingDocument),
                recording,
                requestingMicrophone,
                sending,
                uploading,
              })}
              aria-label="Invia il messaggio"
            ><SendIcon /></button>
          </form>
          <p className="public-chat__fineprint">
            {automaticRepliesEnabled
              ? `L’assistente può sbagliare: non fornisce valutazioni, impegni o pareri professionali al posto di ${space.professional_name}.`
              : `${professionalFirstName} può leggere e rispondere in questa conversazione; l’assistente AI è in pausa.`}
          </p>
        </div>
      </section>
    </main>
  );
}
