import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AppLink as Link } from "@/components/app-link";
import { ChevronRightIcon, ConversationIcon } from "@/components/icons";
import { InlineError, LoadingLine } from "@/components/status";
import { apiRequest, unwrapList } from "@/lib/api";
import { normalizeConversationSummary } from "@/lib/conversations";
import { formatDateTime, initials } from "@/lib/format";
import type { ConversationSummary } from "@/lib/types";
import { publicSpaceHref } from "@/lib/hosts";
import { startVisiblePolling } from "@/lib/visible-polling";

export function ConversationInbox() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [total, setTotal] = useState(0);

  const load = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
      setError(null);
    }
    try {
      const result = await apiRequest<unknown>("/studio/conversations?limit=50&offset=0");
      const object = (result || {}) as Record<string, unknown>;
      const page = unwrapList<unknown>(result, ["conversations", "items"]).map(normalizeConversationSummary);
      setConversations((current) => {
        if (!background) return page;
        const refreshed = new Set(page.map((item) => item.id));
        return [...page, ...current.filter((item) => !refreshed.has(item.id))];
      });
      setTotal(Number(object.total ?? page.length));
    } catch (reason) {
      if (!background) {
        setError(reason instanceof Error ? reason.message : "Non è stato possibile caricare le conversazioni.");
      }
    } finally {
      if (!background) setLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMore || conversations.length >= total) return;
    setLoadingMore(true);
    setError(null);
    try {
      const result = await apiRequest<unknown>(
        `/studio/conversations?limit=50&offset=${conversations.length}`,
      );
      const object = (result || {}) as Record<string, unknown>;
      const page = unwrapList<unknown>(result, ["conversations", "items"]).map(normalizeConversationSummary);
      setConversations((current) => {
        const known = new Set(current.map((item) => item.id));
        return [...current, ...page.filter((item) => !known.has(item.id))];
      });
      setTotal(Number(object.total ?? conversations.length + page.length));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile caricare le conversazioni precedenti.");
    } finally {
      setLoadingMore(false);
    }
  }, [conversations.length, loadingMore, total]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => startVisiblePolling(() => load(true), { intervalMs: 7_000 }), [load]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("it-IT");
    if (!needle) return conversations;
    return conversations.filter((item) => [item.visitor_name, item.visitor_label, item.summary, item.last_message]
      .filter(Boolean)
      .some((value) => value!.toLocaleLowerCase("it-IT").includes(needle)));
  }, [conversations, query]);

  return (
    <section className="inbox-page">
      <header className="page-header">
        <div><p>Conversazioni pubbliche</p><h1>Le persone che hai ricevuto</h1><span>Il filo originale resta al centro. LAGGENTE evidenzia soltanto dove la tua attenzione può servire.</span></div>
        <div className="page-header__metric"><strong>{total}</strong><span>conversazioni<br />nel tuo spazio</span></div>
      </header>
      <div className="inbox-toolbar">
        <label><span className="sr-only">Cerca nelle conversazioni</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca una persona o un argomento…" /></label>
        <span>{filtered.length} {filtered.length === 1 ? "conversazione" : "conversazioni"}</span>
      </div>
      <div className="inbox-list" aria-live="polite" aria-busy={loading}>
        {loading && <LoadingLine label="Raccolgo le conversazioni…" />}
        {error && <InlineError message={error} retry={load} />}
        {!loading && !error && !conversations.length && (
          <div className="inbox-empty"><ConversationIcon /><h2>Qui è ancora tranquillo.</h2><p>Quando una persona scrive nello spazio pubblico, la conversazione apparirà qui con il suo contesto originale.</p><Link href={publicSpaceHref("mauro")} target="_blank">Apri lo spazio pubblico ↗</Link></div>
        )}
        {!loading && conversations.length > 0 && !filtered.length && (
          <div className="inbox-empty inbox-empty--small"><h2>Nessun risultato</h2><p>Prova con un nome, una zona o una parola usata nella conversazione.</p></div>
        )}
        {filtered.map((conversation, index) => {
          const name = conversation.visitor_name || conversation.visitor_label || "Visitatore";
          return (
            <motion.div key={conversation.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * 0.035, 0.2) }}>
              <Link className="inbox-row" href={`/studio/conversazioni/${conversation.id}`}>
                <span className="inbox-row__avatar">{initials(name) || "V"}</span>
                <div className="inbox-row__identity"><strong>{name}</strong><span>{formatDateTime(conversation.last_message_at)}</span></div>
                <div className="inbox-row__content"><strong>{conversation.summary || conversation.last_message || "Conversazione appena iniziata"}</strong>{conversation.attention_reason && <span>{conversation.attention_reason}</span>}</div>
                <div className="inbox-row__state">
                  {conversation.professional_present ? <span className="human-present">Mauro presente</span> : conversation.automatic_replies_enabled ? <span>AI attiva</span> : <span>AI in pausa</span>}
                  <ChevronRightIcon />
                </div>
              </Link>
            </motion.div>
          );
        })}
        {conversations.length < total && (
          <button className="inbox-load-more" type="button" onClick={() => void loadMore()} disabled={loadingMore}>
            {loadingMore ? "Carico le precedenti…" : "Carica conversazioni precedenti"}
          </button>
        )}
      </div>
    </section>
  );
}
