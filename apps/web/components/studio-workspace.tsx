import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { MicIcon, SendIcon, SparkIcon } from "@/components/icons";
import { MessageContent } from "@/components/message-markdown";
import { ProfessionalEmailProposal } from "@/components/professional-email-proposal";
import { OutreachCampaignProposal } from "@/components/outreach-campaign-proposal";
import { RevisionInspector } from "@/components/revision-inspector";
import { InlineError, LoadingLine } from "@/components/status";
import { useStudioSession } from "@/components/studio-shell";
import { apiRequest, normalizeMessages } from "@/lib/api";
import { createClientMessageAttemptTracker } from "@/lib/client-message-id";
import { formatTime } from "@/lib/format";
import {
  acceptResolvedMediaStream,
  finishMediaCaptureRequest,
  releaseMediaCapture,
  shouldDisableMicrophoneControl,
  tryBeginMediaCaptureRequest,
} from "@/lib/media-capture";
import { normalizeProfessionalEmail } from "@/lib/professional-email";
import { normalizeOutreachCampaign } from "@/lib/outreach";
import { normalizeRevision } from "@/lib/revisions";
import type { ConfigRevision, ConversationMessage, OutreachCampaign, ProfessionalEmail, StudioBootstrap, StudioSpaceState } from "@/lib/types";

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

export const studioStarterPrompts = [
  "Ti racconto che lavoro faccio",
  "Cerca cosa si trova già su di me online",
  "Trova il mio sito e i miei profili professionali",
  "Vorrei rendere l’accoglienza più personale",
  "Ti racconto il territorio in cui lavoro",
  "Fammi vedere come appare lo spazio oggi",
];

export function shouldShowStudioStarterPrompts(messages: ConversationMessage[]) {
  return !messages.some((message) => message.author_type === "professional");
}

export function shouldShowPublicAddressPicker(
  space: Pick<StudioSpaceState, "onboarding_state" | "slug_claimed"> | null,
) {
  return Boolean(space && space.onboarding_state !== "published" && !space.slug_claimed);
}

export function suggestPublicSlug(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("it-IT")
    .trim()
    .split(/\s+/)[0]
    ?.replace(/[^a-z0-9-]/g, "")
    .replace(/^-+|-+$/g, "") || "";
}

export function StudioWorkspace() {
  const { session, refreshSession } = useStudioSession();
  const reduceMotion = useReducedMotion();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [proposed, setProposed] = useState<ConfigRevision | null>(null);
  const [active, setActive] = useState<ConfigRevision | null>(null);
  const [spaceState, setSpaceState] = useState<StudioSpaceState | null>(null);
  const [slugInput, setSlugInput] = useState("");
  const [claimingSlug, setClaimingSlug] = useState(false);
  const [slugMessage, setSlugMessage] = useState<string | null>(null);
  const [email, setEmail] = useState<ProfessionalEmail | null>(null);
  const [campaign, setCampaign] = useState<OutreachCampaign | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [dictationState, setDictationState] = useState<"idle" | "requesting" | "recording" | "transcribing">("idle");
  const [composerError, setComposerError] = useState<string | null>(null);
  const [authorizingEmail, setAuthorizingEmail] = useState(false);
  const [authorizingCampaign, setAuthorizingCampaign] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const inputValueRef = useRef("");
  const attemptTrackerRef = useRef(createClientMessageAttemptTracker());
  const dictationRecorderRef = useRef<MediaRecorder | null>(null);
  const dictationStreamRef = useRef<MediaStream | null>(null);
  const dictationChunksRef = useRef<Blob[]>([]);
  const mediaCaptureRequestGateRef = useRef({ busy: false });
  const disposedRef = useRef(false);

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
      const loadedSpace = (spaceObject.space && typeof spaceObject.space === "object" ? spaceObject.space : null) as StudioSpaceState | null;
      const loadedDraft = normalizeRevision(spaceObject.latest_draft || spaceObject.proposed_revision);
      setMessages(loadedMessages.length ? loadedMessages : normalizeMessages(spaceObject.studio_messages));
      setSpaceState(loadedSpace);
      setProposed(loadedDraft);
      setActive(normalizeRevision(spaceObject.active_revision));
      if (loadedSpace?.slug_claimed) setSlugInput(loadedSpace.slug);
      else if (loadedDraft?.preview?.professional_name) {
        setSlugInput((current) => current || suggestPublicSlug(loadedDraft.preview?.professional_name || ""));
      }
      setEmail(normalizeProfessionalEmail(messageObject.latest_email));
      setCampaign(normalizeOutreachCampaign(messageObject.latest_campaign));
    } catch (reason) {
      if (!background) {
        setError(reason instanceof Error ? reason.message : "Non è stato possibile aprire lo Studio.");
      }
    } finally {
      if (!background) setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); }, [messages, email, campaign, sending, reduceMotion]);
  useEffect(() => {
    const requestGate = mediaCaptureRequestGateRef.current;
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      releaseMediaCapture(dictationRecorderRef.current, dictationStreamRef.current);
      dictationRecorderRef.current = null;
      dictationStreamRef.current = null;
      finishMediaCaptureRequest(requestGate);
    };
  }, []);

  async function submit(value: string) {
    const content = value.trim();
    if (!content || sending || dictationState !== "idle") return;
    const clientMessageId = attemptTrackerRef.current.idFor(content);
    const optimistic: ConversationMessage = {
      id: `pending-${clientMessageId}`,
      author_type: "professional",
      author_name: session?.member.display_name || "Tu",
      content,
      created_at: new Date().toISOString(),
      pending: true,
    };
    setMessages((current) => [...current, optimistic]);
    inputValueRef.current = "";
    setInput("");
    setComposerError(null);
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
      const proposedCampaign = normalizeOutreachCampaign(object.proposed_campaign);
      if (proposedCampaign) setCampaign(proposedCampaign);
      await load(true);
      attemptTrackerRef.current.complete(clientMessageId);
    } catch (reason) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      inputValueRef.current = content;
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

  async function transcribeDictation(blob: Blob) {
    if (disposedRef.current) return;
    setDictationState("transcribing");
    setComposerError(null);
    try {
      const form = new FormData();
      const mediaType = blob.type || "audio/webm";
      const filename = mediaType.startsWith("audio/mp4")
        ? "dettatura.m4a"
        : mediaType.startsWith("audio/ogg")
          ? "dettatura.ogg"
          : "dettatura.webm";
      form.append("file", blob, filename);
      const result = await apiRequest<unknown>("/studio/dictation", {
        method: "POST",
        body: form,
      });
      const transcript = typeof (result as { transcript?: unknown })?.transcript === "string"
        ? (result as { transcript: string }).transcript.trim()
        : "";
      if (!transcript) throw new Error("La trascrizione non contiene testo.");
      const currentInput = inputValueRef.current;
      const separator = currentInput && !/\s$/.test(currentInput) ? " " : "";
      const nextInput = `${currentInput}${separator}${transcript}`;
      if (nextInput.length > 5000) {
        throw new Error("La trascrizione è troppo lunga per il messaggio dello Studio.");
      }
      attemptTrackerRef.current.invalidate();
      inputValueRef.current = nextInput;
      setInput(nextInput);
      requestAnimationFrame(() => composerRef.current?.focus());
    } catch (reason) {
      if (!disposedRef.current) {
        setComposerError(
          reason instanceof Error ? reason.message : "Non è stato possibile trascrivere la dettatura.",
        );
      }
    } finally {
      if (!disposedRef.current) setDictationState("idle");
    }
  }

  async function toggleDictation() {
    if (dictationRecorderRef.current) {
      if (dictationRecorderRef.current.state !== "inactive") {
        dictationRecorderRef.current.stop();
      }
      return;
    }
    if (sending || dictationState !== "idle") return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setComposerError("La dettatura non è supportata da questo browser.");
      return;
    }
    if (!tryBeginMediaCaptureRequest(mediaCaptureRequestGateRef.current)) return;
    setComposerError(null);
    setDictationState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!acceptResolvedMediaStream(stream, disposedRef.current)) return;
      dictationStreamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      dictationChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) dictationChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const chunks = dictationChunksRef.current;
        const mediaType = recorder.mimeType || chunks[0]?.type || "audio/webm";
        dictationChunksRef.current = [];
        stream.getTracks().forEach((track) => track.stop());
        dictationStreamRef.current = null;
        dictationRecorderRef.current = null;
        if (disposedRef.current) return;
        const blob = new Blob(chunks, { type: mediaType });
        if (!blob.size) {
          setDictationState("idle");
          setComposerError("Non ho ricevuto audio. Prova di nuovo.");
          return;
        }
        void transcribeDictation(blob);
      };
      dictationRecorderRef.current = recorder;
      recorder.start();
      setDictationState("recording");
    } catch {
      releaseMediaCapture(dictationRecorderRef.current, dictationStreamRef.current);
      dictationRecorderRef.current = null;
      dictationStreamRef.current = null;
      if (!disposedRef.current) {
        setDictationState("idle");
        setComposerError("Per dettare, autorizza l’accesso al microfono.");
      }
    } finally {
      finishMediaCaptureRequest(mediaCaptureRequestGateRef.current);
    }
  }

  async function claimSlug(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slugInput.trim() || claimingSlug) return;
    setClaimingSlug(true);
    setSlugMessage(null);
    try {
      const claimed = await apiRequest<StudioSpaceState>("/studio/space/slug", {
        method: "PATCH",
        body: JSON.stringify({ slug: slugInput.trim() }),
      });
      setSpaceState(claimed);
      setSlugInput(claimed.slug);
      setSlugMessage(`${claimed.slug}.laggente.com è riservato per te.`);
      await refreshSession();
    } catch (reason) {
      setSlugMessage(reason instanceof Error ? reason.message : "Non è stato possibile riservare l’indirizzo.");
    } finally {
      setClaimingSlug(false);
    }
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
    const nextInput = `Vorrei modificare la bozza email per ${email.to_address}: `;
    inputValueRef.current = nextInput;
    setInput(nextInput);
    setComposerError(null);
    requestAnimationFrame(() => composerRef.current?.focus());
  }

  async function authorizeCampaign() {
    if (!campaign || campaign.status !== "ready" || authorizingCampaign) return;
    setAuthorizingCampaign(true);
    setError(null);
    try {
      const result = await apiRequest<unknown>(`/studio/outreach/${campaign.id}/authorize`, {
        method: "POST",
      });
      const updated = normalizeOutreachCampaign(result);
      if (updated) setCampaign(updated);
      await load(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile autorizzare la campagna.");
      await load(true);
    } finally {
      setAuthorizingCampaign(false);
    }
  }

  function continueCampaign() {
    if (!campaign) return;
    const nextInput = `Continuiamo la campagna “${campaign.name}”. Mostrami esattamente cosa manca prima di poter autorizzare gli invii.`;
    inputValueRef.current = nextInput;
    setInput(nextInput);
    setComposerError(null);
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
        {spaceState && shouldShowPublicAddressPicker(spaceState) && (
          <section className="studio-onboarding" aria-label="Preparazione dello spazio pubblico">
            <div className="studio-onboarding__copy">
              <p>Il tuo spazio sta prendendo forma</p>
              <strong>{proposed ? "La prima bozza è pronta. Ora scegli il tuo indirizzo e controllala." : "Presentati allo Studio con parole tue: non serve compilare un profilo."}</strong>
              <span>Diventerà pubblico soltanto quando attiverai esplicitamente una versione.</span>
            </div>
            <form onSubmit={claimSlug} className="slug-claim-form">
              <label htmlFor="public-slug">Il tuo indirizzo pubblico</label>
              <div>
                <span>https://</span>
                <input
                  id="public-slug"
                  value={slugInput}
                  onChange={(event) => { setSlugInput(event.target.value); setSlugMessage(null); }}
                  placeholder="giulia"
                  autoComplete="off"
                  disabled={claimingSlug}
                />
                <span>.laggente.com</span>
              </div>
              <button type="submit" disabled={!slugInput.trim() || claimingSlug}>{claimingSlug ? "Salvo…" : spaceState.slug_claimed ? "Aggiorna indirizzo" : "Riserva indirizzo"}</button>
              {slugMessage && <small role="status">{slugMessage}</small>}
              {spaceState.slug_claimed && !slugMessage && <small>{spaceState.slug}.laggente.com è riservato. Puoi correggerlo finché non pubblichi.</small>}
            </form>
          </section>
        )}
        <div className="studio-thread" aria-live="polite" aria-busy={loading || sending}>
          {loading && <LoadingLine label="Riprendo la nostra conversazione…" />}
          {error && <InlineError message={error} retry={load} />}
          {!loading && !messages.length && !error && (
            <div className="studio-empty">
              <span><SparkIcon /></span>
              <h2>Parlami del professionista che vuoi essere qui.</h2>
              <p>Partiamo da “Che lavoro fai?”, poi dal modo in cui ricevi le persone o da qualcosa che non vuoi delegare.</p>
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
          {campaign && (
            <OutreachCampaignProposal
              campaign={campaign}
              busy={authorizingCampaign}
              onAuthorize={() => void authorizeCampaign()}
              onContinue={continueCampaign}
            />
          )}
          {sending && <div className="studio-thinking" role="status"><span /><span /><span /> Lo Studio sta interpretando…</div>}
          <div ref={bottomRef} />
        </div>
        {shouldShowStudioStarterPrompts(messages) && !loading && (
          <div className="studio-starters" aria-label="Possibili inizi con Studio">
            {studioStarterPrompts.map((prompt) => (
              <button
                type="button"
                key={prompt}
                disabled={sending || dictationState !== "idle"}
                onClick={() => void submit(prompt)}
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
        <form className="studio-composer" onSubmit={onSubmit}>
          {composerError && <InlineError message={composerError} />}
          <textarea
            ref={composerRef}
            value={input}
            onChange={(event) => {
              attemptTrackerRef.current.invalidate();
              inputValueRef.current = event.target.value;
              setInput(event.target.value);
              setComposerError(null);
            }}
            rows={2}
            maxLength={5000}
            placeholder="Racconta, correggi o chiedi una modifica…"
            aria-label="Messaggio per lo Studio"
            disabled={sending || dictationState !== "idle"}
          />
          <div className="studio-composer__footer">
            <span
              className={`studio-composer__hint studio-composer__hint--${dictationState}`}
              role={dictationState === "idle" ? undefined : "status"}
            >
              {dictationState === "requesting" && "Attendo il permesso per il microfono…"}
              {dictationState === "recording" && <><i /> Ti ascolto… tocca di nuovo per terminare</>}
              {dictationState === "transcribing" && "Trascrivo la dettatura…"}
              {dictationState === "idle" && "Invia dal pulsante"}
            </span>
            <div className="studio-composer__actions">
              <button
                type="button"
                className={`studio-composer__dictate${dictationState === "recording" ? " is-recording" : ""}${dictationState === "transcribing" ? " is-transcribing" : ""}`}
                onClick={() => void toggleDictation()}
                disabled={shouldDisableMicrophoneControl({
                  recording: dictationState === "recording",
                  requesting: dictationState === "requesting",
                  sending,
                  uploading: dictationState === "transcribing",
                  hasPendingAttachment: false,
                })}
                aria-label={
                  dictationState === "requesting"
                    ? "Attendo il permesso per il microfono"
                    : dictationState === "recording"
                      ? "Termina la dettatura"
                      : dictationState === "transcribing"
                        ? "Trascrizione in corso"
                        : "Inizia la dettatura"
                }
                aria-pressed={dictationState === "recording"}
              >
                <MicIcon />
              </button>
              <button className="studio-composer__send" type="submit" disabled={!input.trim() || sending || dictationState !== "idle"} aria-label="Invia allo Studio"><SendIcon /></button>
            </div>
          </div>
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
          onActivated={(revision) => { setActive(revision); setProposed(null); setInspectorOpen(false); void load(true); }}
        />
      </div>
    </div>
  );
}
