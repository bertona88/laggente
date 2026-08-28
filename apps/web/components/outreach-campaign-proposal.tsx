import { motion, useReducedMotion } from "framer-motion";
import type { OutreachCampaign } from "@/lib/types";

const statusCopy: Record<string, string> = {
  research: "Ricerca — invio bloccato",
  preparing: "Preparazione incompleta",
  ready: "Pacchetto pronto per la tua autorizzazione",
  sending: "Invio in corso",
  sent: "Invii accettati dal provider",
  simulated: "Simulazione completata — niente è uscito",
  partial: "Esito parziale — nessun retry automatico",
  failed: "Consegna non confermata",
};

const permissionCopy: Record<string, string> = {
  not_recorded: "Nessuna base di contatto registrata",
  explicit_consent: "Consenso esplicito dichiarato",
  existing_customer_similar_services: "Cliente esistente · servizio analogo",
};

export function OutreachCampaignProposal({
  campaign,
  busy,
  onAuthorize,
  onContinue,
}: {
  campaign: OutreachCampaign;
  busy: boolean;
  onAuthorize: () => void;
  onContinue: () => void;
}) {
  const reduceMotion = useReducedMotion();
  const canAuthorize = campaign.status === "ready" && campaign.recipients.length > 0;
  return (
    <motion.article
      className={`outreach-campaign outreach-campaign--${campaign.status}`}
      aria-label="Campagna outreach preparata da Studio"
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <header>
        <div><p>Pacchetto privato e delimitato</p><h2>{campaign.name}</h2></div>
        <span>{statusCopy[campaign.status] || campaign.status}</span>
      </header>
      <div className="outreach-campaign__link">
        <span>Link promosso</span>
        <a href={campaign.landing_url} target="_blank" rel="noreferrer">{campaign.landing_url}</a>
      </div>
      <ol>
        {campaign.recipients.map((recipient) => (
          <li key={recipient.id}>
            <div className="outreach-recipient__identity">
              <strong>{recipient.name}</strong>
              <span>{recipient.email || "Email non conservata"}</span>
              <a href={recipient.source_url} target="_blank" rel="noreferrer">{recipient.source_label || "Fonte pubblica"}</a>
            </div>
            <div className={`outreach-recipient__permission outreach-recipient__permission--${recipient.permission_basis}`}>
              {permissionCopy[recipient.permission_basis] || recipient.permission_basis}
            </div>
            {recipient.professional_email ? (
              <div className="outreach-recipient__email">
                <span>Email sigillata · {recipient.professional_email.content_sha256.slice(0, 12)}</span>
                <h3>{recipient.professional_email.subject}</h3>
                <p>{recipient.professional_email.body_text}</p>
              </div>
            ) : (
              <p className="outreach-recipient__blocked">Nessuna email può essere preparata finché la base di contatto non è registrata.</p>
            )}
          </li>
        ))}
      </ol>
      <footer>
        <p>Massimo {campaign.recipient_cap} destinatari · fonti visibili · disiscrizione inclusa · nessun invio o retry autonomo.</p>
        <div>
          {!canAuthorize && campaign.status !== "sent" && campaign.status !== "simulated" && (
            <button type="button" className="outreach-campaign__continue" onClick={onContinue}>Continua con Studio</button>
          )}
          {canAuthorize && (
            <button type="button" className="outreach-campaign__authorize" disabled={busy} onClick={onAuthorize}>
              {busy
                ? "Autorizzazione…"
                : `Autorizza ${campaign.recipients.length} ${campaign.recipients.length === 1 ? "invio esatto" : "invii esatti"}`}
            </button>
          )}
        </div>
      </footer>
    </motion.article>
  );
}
