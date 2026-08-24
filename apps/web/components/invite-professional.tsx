import { FormEvent, useState } from "react";
import { ArrowUpRightIcon, InviteIcon, LockIcon } from "@/components/icons";
import { InlineError } from "@/components/status";
import { useStudioSession } from "@/components/studio-shell";
import { apiRequest } from "@/lib/api";

interface InvitationResult {
  accepted: boolean;
  email: string;
  status: "sent" | "resent";
  expires_at: string;
  development_magic_link?: string | null;
}

export function InviteProfessional() {
  const { session, loading } = useStudioSession();
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<InvitationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || sending) return;
    setSending(true);
    setError(null);
    setResult(null);
    try {
      const invitation = await apiRequest<InvitationResult>("/studio/invitations", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
      });
      setResult(invitation);
      setEmail("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile inviare l’invito.");
    } finally {
      setSending(false);
    }
  }

  if (!loading && !session?.member.can_invite) {
    return <section className="invite-page"><div className="invite-card"><LockIcon /><h1>Inviti non disponibili</h1><p>Questo accesso non può creare altri spazi professionali.</p></div></section>;
  }

  return (
    <section className="invite-page">
      <header className="page-header page-header--compact">
        <div>
          <p>Pilot professionisti</p>
          <h1>Invita una nuova persona</h1>
          <span>Serve solo l’email. Identità, territorio, voce e spazio nasceranno nella sua conversazione privata con lo Studio.</span>
        </div>
      </header>
      <div className="invite-layout">
        <form className="invite-card" onSubmit={submit}>
          <span className="invite-card__mark"><InviteIcon /></span>
          <h2>Apri una nuova porta</h2>
          <p>L’invito crea un tenant separato e dormiente. Diventa pubblico solo quando la persona sceglie il proprio indirizzo e attiva la prima versione.</p>
          <label>
            <span>Email professionale</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="giulia@studio.it"
              autoComplete="off"
              required
            />
          </label>
          {error && <InlineError message={error} />}
          <button className="button button--ink button--wide" type="submit" disabled={sending || !email.trim()}>
            {sending ? "Invio in corso…" : "Invia il magic link"}
          </button>
        </form>
        <aside className="invite-explainer">
          <p>Da qui in poi</p>
          <ol>
            <li><span>1</span><div><strong>Si presenta allo Studio</strong><small>Parla naturalmente di sé e del proprio lavoro.</small></div></li>
            <li><span>2</span><div><strong>Sceglie l’indirizzo</strong><small>Per esempio giulia.laggente.com.</small></div></li>
            <li><span>3</span><div><strong>Controlla e pubblica</strong><small>L’attivazione accende lo spazio senza un deploy.</small></div></li>
          </ol>
          {result && (
            <div className="invite-success" role="status">
              <strong>Invito {result.status === "resent" ? "reinviato" : "inviato"}</strong>
              <p>{result.email} può ora creare il proprio spazio.</p>
              {result.development_magic_link && <a href={result.development_magic_link}>Apri il link di sviluppo <ArrowUpRightIcon /></a>}
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
