import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { AppLink as Link } from "@/components/app-link";
import { ArrowUpRightIcon, CheckIcon, CloseIcon, SparkIcon } from "@/components/icons";
import { apiRequest } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { publicSpaceHref } from "@/lib/hosts";
import { normalizeRevision } from "@/lib/revisions";
import type { ConfigRevision, ConfigSection } from "@/lib/types";

function sectionText(value: ConfigSection["value"]) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.join(" · ");
  return Object.entries(value)
    .map(([key, item]) => `${key.replaceAll("_", " ")}: ${String(item)}`)
    .join(" · ");
}

export function PublicMiniPreview({ revision, fallbackName = "il professionista" }: { revision: ConfigRevision | null; fallbackName?: string }) {
  const preview = revision?.preview || {};
  const name = preview.professional_name || fallbackName;
  return (
    <div className="mini-preview" aria-label="Anteprima dello spazio pubblico">
      <div className="mini-preview__visual">
        <img src={preview.hero_image_url || "/images/laggente-hero.webp"} alt="" />
        <div><span>{preview.territory || "Il tuo territorio"}</span><strong>{name}</strong><small>{preview.professional_role || "Professionista"}</small></div>
      </div>
      <div className="mini-preview__chat">
        <p><i>AI</i><strong>LAGGENTE — assistente AI di {name}</strong></p>
        <blockquote>{preview.welcome_message || `Ciao, sono l’assistente AI di ${name}. Da dove vuoi partire?`}</blockquote>
      </div>
    </div>
  );
}

export function RevisionInspector({
  revision,
  activeRevision,
  onActivated,
  title = "Proposta pronta",
}: {
  revision: ConfigRevision | null;
  activeRevision?: ConfigRevision | null;
  onActivated?: (revision: ConfigRevision) => void;
  title?: string;
}) {
  const [confirming, setConfirming] = useState(false);
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function activate() {
    if (!revision?.id) return;
    setActivating(true);
    setError(null);
    try {
      const value = await apiRequest<unknown>(`/studio/config/revisions/${encodeURIComponent(revision.id)}/activate`, { method: "POST" });
      const activated = normalizeRevision((value as Record<string, unknown>)?.revision || value) || { ...revision, status: "active" as const };
      onActivated?.(activated);
      setConfirming(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile attivare la revisione.");
    } finally {
      setActivating(false);
    }
  }

  if (!revision) {
    return (
      <aside className="revision-inspector revision-inspector--empty">
        <span className="empty-mark"><SparkIcon /></span>
        <h2>Nessuna modifica in attesa</h2>
        <p>Continua la conversazione: quando lo Studio capisce una modifica concreta, la prepara qui senza pubblicarla.</p>
        {activeRevision && <span className="revision-current">Attiva: {activeRevision.title}</span>}
      </aside>
    );
  }

  const isActive = revision.status === "active";
  const resolvedProfessionalName = revision.preview?.professional_name
    || activeRevision?.preview?.professional_name
    || "il professionista";
  return (
    <aside className="revision-inspector">
      <header>
        <div><p>{isActive ? "Configurazione pubblica" : title}</p><h2>{revision.title}</h2></div>
        <span className={`status-label status-label--${isActive ? "active" : "draft"}`}><i /> {isActive ? "Attiva" : "Solo bozza"}</span>
      </header>
      {revision.summary && <p className="revision-inspector__summary">{revision.summary}</p>}
      <PublicMiniPreview revision={revision} fallbackName={resolvedProfessionalName} />
      <div className="revision-sections">
        <p>Ciò che lo Studio ha capito</p>
        {revision.sections.length ? revision.sections.map((section) => (
          <details key={section.key} open={section.changed}>
            <summary><span>{section.title}</span>{section.changed && <em>modificato</em>}</summary>
            <p>{sectionText(section.value)}</p>
          </details>
        )) : <p className="revision-sections__empty">La proposta riguarda la presentazione mostrata nell’anteprima.</p>}
      </div>
      <footer>
        <span>Preparata {formatDateTime(revision.created_at)}</span>
        {!isActive && (
          <button className="button button--ink button--wide" type="button" onClick={() => setConfirming(true)}>
            Attiva nello spazio pubblico <CheckIcon />
          </button>
        )}
        {isActive && <Link className="button button--outline button--wide" href={publicSpaceHref("mauro")} target="_blank">Vedi lo spazio pubblico <ArrowUpRightIcon /></Link>}
      </footer>

      <AnimatePresence>
        {confirming && (
          <div className="modal-layer" role="presentation">
            <motion.button className="modal-backdrop" type="button" aria-label="Chiudi conferma" onClick={() => setConfirming(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" initial={{ opacity: 0, scale: 0.98, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }}>
              <button type="button" onClick={() => setConfirming(false)} aria-label="Chiudi"><CloseIcon /></button>
              <p className="eyebrow">Conferma pubblicazione</p>
              <h2 id="confirm-title">Vuoi attivare questa versione?</h2>
              <p>Da questo momento le nuove conversazioni pubbliche useranno questa configurazione. La versione precedente resterà recuperabile.</p>
              {error && <p className="confirm-dialog__error" role="alert">{error}</p>}
              <div><button type="button" className="button button--outline" onClick={() => setConfirming(false)}>Continua a rivedere</button><button type="button" className="button button--ink" onClick={() => void activate()} disabled={activating}>{activating ? "Attivazione…" : "Sì, attiva"}<CheckIcon /></button></div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </aside>
  );
}
