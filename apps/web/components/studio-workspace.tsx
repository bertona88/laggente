import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { SendIcon, SparkIcon } from "@/components/icons";
import { MessageContent } from "@/components/message-markdown";
import { ProfessionalEmailProposal } from "@/components/professional-email-proposal";
import { RevisionInspector } from "@/components/revision-inspector";
import { InlineError, LoadingLine } from "@/components/status";
import { apiRequest, normalizeMessages } from "@/lib/api";
import { createClientMessageAttemptTracker } from "@/lib/client-message-id";
import { formatTime } from "@/lib/format";
import { normalizeRevision } from "@/lib/revisions";
import { normalizeProfessionalEmail } from "@/lib/professional-email";
import type { ConfigRevision, ConversationMessage, ProfessionalEmail, StudioBootstrap } from "@/lib/types";

function StudioMessage({ message }: { message: ConversationMessage }) {
  if (message.author_type === "system") return <div className="studio-system-event">{message.content}</div>;
  const assistant = message.author_type === "studio_assistant";
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: message.pending ? 0.55 : 1, y: 0 }}
      className={`studio-message studio-message--${assistant ? "assistant" : "professional"}`}
    >
      {assistant && <span className="speaker-mark speaker-mark--studio" aria-hidden="true"><SparkIcon /></span>}
      <div>
        <header><strong>{assistant ? "Studio LAGGENTE" : message.author_name}</strong><time dateTime={message.created_at}>{formatTime(message.created_at)}</time></header>
        <MessageContent authorType={message.author_type} content={message.content} />
      </div>
    </motion.article>
  );
}

const starterPrompts = [
  "Vorrei rendere l’accoglienza più personale",
  "Aggiungiamo ciò che so di Roma Nord",
  "Fammi vedere come appare lo spazio oggi",
];

export function StudioWorkspace() {
  const reduceMotion = useReducedMotion();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [proposed, setProposed] = useState<ConfigRevision | null>(null);
  const [active, setActive] = useState<ConfigRevision | null>(null);
  const [email, setEmail] = useState<ProfessionalEmail | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [authorizingEmail, setAuthorizingEmail] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const attemptTrackerRef = useRef(createClientMessageAttemptTracker());

  const load = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
      setError(null);
    }
    try {
      const [spaceData, messageData] = await Promise.all([
        apiRequest<unknown>("/studio/space"),
        apiRequest<unknown>("/studio/messages"),
      ]);
      const spaceObject = (spaceData || {}) as StudioBootstrap & Record<string, unknown>;
      const messageObject = (messageData || {}) as Record<string, unknown>;
      const loadedMessages = normalizeMessages(messageObject.messages || messageObject.items || messageData);
      setMessages(loadedMessages.length ? loadedMessages : normalizeMessages(spaceObject.studio_messages));
      setProposed(normalizeRevision(spaceObject.latest_draft || spaceObject.proposed_revision));
      setActive(normalizeRevision(spaceObject.active_revision));
      setEmail(normalizeProfessionalEmail(messageObject.latest_email));
    } catch (reason) {
      if (!background) {
        setError(reason instanceof Error ? reason.message : "Non è stato possibile aprire lo Studio.");
      }
    } finally {
      if (!background) setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); }, [messages, email, sending, reduceMotion]);

  async function submit(value: string) {
    const content = value.trim();
    if (!content || sending) return;
    const clientMessageId = attemptTrackerRef.current.idFor(content);
    const optimistic: ConversationMessage = {
      id: `pending-${clientMessageId}`,
      author_type: "professional",
      author_name: "Mauro",
      content,
      created_at: new Date().toISOString(),
      pending: true,
    };
    setMessages((current) => [...current, optimistic]);
    setInput("");
    setSending(true);
    setError(null);
    try {
      const value = await apiRequest<unknown>("/studio/messages", {
        method: "POST",
        body: JSON.stringify({ content, client_message_id: clientMessageId }),
      });
      const object = (value || {}) as Record<string, unknown>;
      const revision = normalizeRevision(object.proposed_revision || object.revision);
      if (revision) setProposed(revision);
      const proposedEmail = normalizeProfessionalEmail(object.proposed_email);
      if (proposedEmail) setEmail(proposedEmail);
      await load(true);
      attemptTrackerRef.current.complete(clientMessageId);
    } catch (reason) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      setInput(content);
      setError(reason instanceof Error ? reason.message : "Il messaggio non è partito.");
    } finally {
      setSending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(input);
  }

  async function authorizeEmail() {
    if (!email || email.status !== "draft" || authorizingEmail) return;
    setAuthorizingEmail(true);
    setError(null);
    try {
      const result = await apiRequest<unknown>(`/studio/email/${email.id}/authorize`, {
        method: "POST",
      });
      const updated = normalizeProfessionalEmail(result);
      if (updated) setEmail(updated);
      await load(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile autorizzare l’email.");
      await load(true);
    } finally {
      setAuthorizingEmail(false);
    }
  }

  function requestEmailChange() {
    if (!email) return;
    setInput(`Vorrei modificare la bozza email per ${email.to_address}: `);
    requestAnimationFrame(() => composerRef.current?.focus());
  }

  return (
    <div className="studio-workspace">
      <section className="studio-conversation" aria-label="Conversazione con lo Studio LAGGENTE">
        <header className="workspace-header">
          <div><p>Studio privato</p><h1>Costruiamo il tuo spazio</h1></div>
          <div className="workspace-header__actions">
            <span className="workspace-header__presence"><i /> Studio in ascolto</span>
            <button type="button" className="workspace-panel-toggle" onClick={() => setInspectorOpen(true)} aria-expanded={inspectorOpen} aria-controls="studio-revision-panel">Bozza{proposed ? " pronta" : ""}</button>
          </div>
        </header>
        <div className="studio-thread" aria-live="polite" aria-busy={loading || sending}>
          {loading && <LoadingLine label="Riprendo la nostra conversazione…" />}
          {error && <InlineError message={error} retry={load} />}
          {!loading && !messages.length && !error && (
            <div className="studio-empty">
              <span><SparkIcon /></span>
              <h2>Parlami del professionista che vuoi essere qui.</h2>
              <p>Possiamo partire dal tuo territorio, dal modo in cui ricevi le persone o da qualcosa che non vuoi delegare.</p>
            </div>
          )}
          {messages.map((message) => <StudioMessage key={message.id} message={message} />)}
          {email && email.direction === "outbound" && (
            <ProfessionalEmailProposal
              email={email}
              busy={authorizingEmail}
              onAuthorize={() => void authorizeEmail()}
              onRequestChange={requestEmailChange}
            />
          )}
          {sending && <div className="studio-thinking" role="status"><span /><span /><span /> Lo Studio sta interpretando…</div>}
          <div ref={bottomRef} />
        </div>
        {!messages.length && !loading && (
          <div className="studio-starters">{starterPrompts.map((prompt) => <button type="button" key={prompt} onClick={() => void submit(prompt)}>{prompt}</button>)}</div>
        )}
        <form className="studio-composer" onSubmit={onSubmit}>
          <textarea
            ref={composerRef}
            value={input}
            onChange={(event) => {
              attemptTrackerRef.current.invalidate();
              setInput(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={2}
            maxLength={5000}
            placeholder="Racconta, correggi o chiedi una modifica…"
            aria-label="Messaggio per lo Studio"
            disabled={sending}
          />
          <div><span>Invio ↵ · nuova riga ⇧↵</span><button type="submit" disabled={!input.trim() || sending} aria-label="Invia allo Studio"><SendIcon /></button></div>
        </form>
      </section>
      <div id="studio-revision-panel" className={`studio-revision-panel${inspectorOpen ? " is-open" : ""}`}>
        <AnimatePresence>
          {inspectorOpen && <motion.button type="button" className="studio-revision-backdrop" aria-label="Chiudi il pannello configurazione" onClick={() => setInspectorOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />}
        </AnimatePresence>
        <button type="button" className="studio-revision-close" onClick={() => setInspectorOpen(false)} aria-label="Chiudi il pannello configurazione">Chiudi</button>
        <RevisionInspector
          revision={proposed}
          activeRevision={active}
          onActivated={(revision) => { setActive(revision); setProposed(null); setInspectorOpen(false); }}
        />
      </div>
    </div>
  );
}
