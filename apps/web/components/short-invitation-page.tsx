import { motion, useReducedMotion } from "framer-motion";
import { AppLink as Link } from "@/components/app-link";
import { ArrowRightIcon, ArrowUpRightIcon } from "@/components/icons";
import { Logo } from "@/components/logo";
import { studioHref } from "@/lib/hosts";

const reveal = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

const steps = [
  {
    number: "01",
    title: "Accoglie le persone.",
    copy: "Chi arriva può raccontare la propria situazione e continuare la stessa conversazione nel tempo, sapendo sempre di parlare con un assistente AI.",
  },
  {
    number: "02",
    title: "Impara come lavori.",
    copy: "Nel tuo Studio privato spieghi cosa chiedere, cosa evitare e quando coinvolgerti. Studio prepara le modifiche; tu le rivedi e le attivi.",
  },
  {
    number: "03",
    title: "Ti lascia entrare.",
    copy: "Ritrovi il contesto e, quando serve il tuo giudizio, entri nella stessa conversazione come professionista riconoscibile.",
  },
] as const;

export function ShortInvitationPage() {
  const reduceMotion = useReducedMotion();

  return (
    <main className="short-invite">
      <section className="short-invite__hero" aria-labelledby="short-invite-title">
        <header className="short-invite__header">
          <Logo inverse />
          <span>Anteprima</span>
        </header>

        <div className="short-invite__hero-content">
          <motion.div
            className="short-invite__copy"
            initial="hidden"
            animate="visible"
            transition={{ staggerChildren: reduceMotion ? 0 : 0.11, delayChildren: 0.08 }}
          >
            <motion.p className="eyebrow eyebrow--light" variants={reveal} transition={{ duration: 0.45 }}>
              LAGGENTE in 38 secondi
            </motion.p>
            <motion.h1 id="short-invite-title" variants={reveal} transition={{ duration: 0.65 }}>
              Un assistente online che lavora come gli insegni tu.
            </motion.h1>
            <motion.p variants={reveal} transition={{ duration: 0.55 }}>
              Accoglie le persone, conserva il filo e ti permette di entrare quando servi tu.
            </motion.p>
            <motion.div className="short-invite__actions" variants={reveal} transition={{ duration: 0.5 }}>
              <Link className="button button--paper" href={studioHref("/login")}>
                Prova LAGGENTE <ArrowUpRightIcon />
              </Link>
              <Link href="#come-funziona">
                Capisci come funziona <ArrowRightIcon />
              </Link>
            </motion.div>
          </motion.div>

          <motion.figure
            className="short-invite__reel"
            initial={{ opacity: 0, y: reduceMotion ? 0 : 30, scale: reduceMotion ? 1 : 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.75, delay: reduceMotion ? 0 : 0.2 }}
          >
            <div>
              <span>Studio → link → conversazione</span>
              <span>00:38</span>
            </div>
            <video
              aria-label="Breve presentazione di LAGGENTE"
              autoPlay={!reduceMotion}
              controls
              loop
              muted
              playsInline
              poster="/media/laggente-extension-poster.png"
              preload="metadata"
            >
              <source src="/media/laggente-extension-it.mp4" type="video/mp4" />
              Il tuo browser non supporta la riproduzione del video.
            </video>
            <figcaption>Un’estensione del professionista.</figcaption>
          </motion.figure>
        </div>
      </section>

      <section id="come-funziona" className="short-invite__steps" aria-labelledby="short-steps-title">
        <div className="short-invite__section-heading">
          <p className="section-index">Come funziona</p>
          <h2 id="short-steps-title">Tre passaggi.<br />Un solo filo.</h2>
        </div>
        <div className="short-invite__step-list">
          {steps.map((step, index) => (
            <motion.article
              key={step.number}
              initial={{ opacity: 0, x: reduceMotion ? 0 : -22 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.55 }}
              transition={{ duration: 0.5, delay: reduceMotion ? 0 : index * 0.06 }}
            >
              <span>{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.copy}</p>
            </motion.article>
          ))}
        </div>
      </section>

      <section className="short-invite__address" aria-labelledby="short-address-title">
        <motion.div
          initial={{ opacity: 0, y: reduceMotion ? 0 : 26 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.65 }}
        >
          <p className="section-index section-index--light">Il tuo indirizzo</p>
          <h2 id="short-address-title">Alla fine gli dai il tuo nome.</h2>
          <p>Scegli tu l’indirizzo disponibile: il tuo nome, il cognome oppure il brand della tua attività.</p>
          <div className="short-invite__address-examples" aria-label="Esempi di indirizzi personali">
            <span><b>tola</b>.laggente.com</span>
            <span><b>giuliatola</b>.laggente.com</span>
            <span><b>nomeagenzia</b>.laggente.com</span>
          </div>
        </motion.div>
      </section>

      <section className="short-invite__closing" aria-labelledby="short-closing-title">
        <p className="section-index">I primi professionisti</p>
        <h2 id="short-closing-title">Provalo.<br />Poi decidi.</h2>
        <p>Ci basta sapere se ti è utile. Se poi ti piace davvero, possiamo capire se ha senso costruirlo insieme.</p>
        <Link className="button button--ink" href={studioHref("/login")}>
          Entra nello Studio <ArrowUpRightIcon />
        </Link>
      </section>

      <footer className="short-invite__footer">
        <Logo />
        <Link href="/privacy">Privacy</Link>
      </footer>
    </main>
  );
}
