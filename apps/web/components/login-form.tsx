import { FormEvent, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AppLink as Link, useAppNavigate } from "@/components/app-link";
import { ArrowLeftIcon, ArrowRightIcon, LockIcon } from "@/components/icons";
import { Logo } from "@/components/logo";
import { InlineError, LoadingLine } from "@/components/status";
import { apiRequest } from "@/lib/api";
import { studioHref } from "@/lib/hosts";
import { magicLinkTokenFromFragment } from "@/lib/magic-link";

type AuthMode = "pilot_password" | "magic_link";

export function LoginForm() {
  const navigate = useAppNavigate();
  const [mode, setMode] = useState<AuthMode | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;

    async function loadMode() {
      try {
        const result = await apiRequest<{ mode: AuthMode }>("/auth/mode");
        if (!disposed) setMode(result.mode);
      } catch {
        if (!disposed) setMode("pilot_password");
      }
    }

    async function prepareLogin() {
      const token = magicLinkTokenFromFragment(window.location.hash);
      if (!token) {
        await loadMode();
        return;
      }

      setLoading(true);
      try {
        await apiRequest("/auth/magic-link/consume", {
          method: "POST",
          body: JSON.stringify({ token }),
        });
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
        navigate(studioHref("/studio"), { replace: true });
      } catch (reason) {
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
        if (!disposed) {
          setError(reason instanceof Error ? reason.message : "Il link non è più valido.");
        }
        await loadMode();
      } finally {
        if (!disposed) setLoading(false);
      }
    }

    void prepareLogin();
    return () => {
      disposed = true;
    };
  }, [navigate]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mode === "magic_link") {
        await apiRequest("/auth/magic-link/request", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        setSent(true);
      } else {
        await apiRequest("/auth/pilot-login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        navigate(studioHref("/studio"), { replace: true });
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Non è stato possibile accedere.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-page__visual" aria-hidden="true">
        <img src="/images/laggente-hero.webp" alt="" sizes="(max-width: 800px) 100vw, 52vw" fetchPriority="high" />
        <div className="login-page__veil" />
        <div className="login-page__line">Il tuo spazio.<br />La tua voce.<br />Le tue relazioni.</div>
      </section>
      <section className="login-page__form-section">
        <div className="login-page__top"><Logo /><Link href="/"><ArrowLeftIcon /> Torna a LAGGENTE</Link></div>
        <motion.div
          className="login-form"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <p className="eyebrow">Studio privato</p>
          <h1>Bentornato.</h1>
          <p className="login-form__intro">Entra nello spazio in cui insegni a LAGGENTE come rappresentarti.</p>

          {!mode && !error ? (
            <LoadingLine label="Preparo il tuo accesso…" />
          ) : sent ? (
            <div className="login-success" role="status">
              <span aria-hidden="true">✓</span>
              <h2>Controlla la posta</h2>
              <p>Abbiamo inviato un collegamento sicuro a <strong>{email}</strong>. È valido per un solo accesso.</p>
              <button type="button" onClick={() => setSent(false)}>Usa un altro indirizzo</button>
            </div>
          ) : (
            <form onSubmit={onSubmit}>
              <label>
                <span>Email professionale</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  placeholder="nome@studio.it"
                  required
                />
              </label>
              {mode === "pilot_password" && (
                <label>
                  <span>Password</span>
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    placeholder="La tua password"
                    required
                  />
                </label>
              )}
              {error && <InlineError message={error} />}
              <button className="button button--ink button--wide" type="submit" disabled={loading}>
                {loading ? "Accesso in corso…" : mode === "magic_link" ? "Ricevi il link di accesso" : "Entra nello Studio"}
                {!loading && <ArrowRightIcon />}
              </button>
            </form>
          )}
          <div className="login-form__security"><LockIcon /><span>Accesso riservato. La sessione dello Studio non viene condivisa con gli spazi pubblici.</span></div>
        </motion.div>
        <footer>Continuando accetti le <Link href="/terms">condizioni d’uso</Link> e l’<Link href="/privacy">informativa privacy</Link>.</footer>
      </section>
    </main>
  );
}
