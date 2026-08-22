import { motion, useReducedMotion } from "framer-motion";
import type { ProfessionalEmail } from "@/lib/types";

const statusCopy: Record<string, string> = {
  draft: "In attesa della tua autorizzazione",
  sending: "Invio in corso",
  sent: "Invio confermato",
  simulated: "Invio simulato — niente è uscito",
  failed: "Consegna non confermata",
  superseded: "Versione sostituita",
};

export function ProfessionalEmailProposal({
  email,
  busy,
  onAuthorize,
  onRequestChange,
}: {
  email: ProfessionalEmail;
  busy: boolean;
  onAuthorize: () => void;
  onRequestChange: () => void;
}) {
  const reduceMotion = useReducedMotion();
  const canAuthorize = email.status === "draft";
  return (
    <motion.article
      className={`professional-email professional-email--${email.status}`}
      aria-label="Email preparata da Studio"
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <header>
        <div>
          <p>Documento sigillato da Studio</p>
          <h2>Email professionale</h2>
        </div>
        <span>{statusCopy[email.status] || email.status}</span>
      </header>
      <dl>
        <div><dt>Da</dt><dd>{email.from_address}</dd></div>
        <div><dt>A</dt><dd>{email.to_address}</dd></div>
        <div><dt>Oggetto</dt><dd>{email.subject}</dd></div>
      </dl>
      <div className="professional-email__body">{email.body_text}</div>
      <footer>
        <p>
          Contenuto esatto · impronta <code>{email.content_sha256.slice(0, 12)}</code>
          {canAuthorize && " · l’autorizzazione invierà questa versione senza modifiche"}
        </p>
        {canAuthorize && (
          <div>
            <button type="button" className="professional-email__change" onClick={onRequestChange}>
              Chiedi una modifica
            </button>
            <button
              type="button"
              className="professional-email__authorize"
              disabled={busy}
              onClick={onAuthorize}
            >
              {busy ? "Autorizzazione…" : "Autorizza e invia"}
            </button>
          </div>
        )}
      </footer>
    </motion.article>
  );
}
