import { useEffect, useState } from "react";
import { Logo } from "@/components/logo";
import { apiRequest } from "@/lib/api";
import { useDocumentTitle } from "@/src/use-app-frame";

export function OutreachUnsubscribe() {
  useDocumentTitle("Disiscrizione");
  const [status, setStatus] = useState<"working" | "done" | "invalid">("working");

  useEffect(() => {
    const parameters = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = parameters.get("token");
    window.history.replaceState(null, "", window.location.pathname);
    if (!token) {
      setStatus("invalid");
      return;
    }
    void apiRequest("/outreach/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ token }),
    }).then(() => setStatus("done"), () => setStatus("invalid"));
  }, []);

  return (
    <main className="outreach-unsubscribe">
      <Logo />
      <div>
        <p className="eyebrow">Preferenze email</p>
        <h1>{status === "done" ? "Richiesta registrata." : status === "invalid" ? "Link non valido." : "Registro la tua richiesta…"}</h1>
        <p>
          {status === "done"
            ? "L’indirizzo non potrà essere usato per altri invii outreach da questo spazio LAGGENTE."
            : status === "invalid"
              ? "Il collegamento è incompleto o non è più riconosciuto. Puoi rispondere direttamente all’email chiedendo di non ricevere altri messaggi."
              : "Attendi un momento."}
        </p>
      </div>
    </main>
  );
}
