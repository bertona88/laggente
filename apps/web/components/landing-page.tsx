import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { AppLink as Link } from "@/components/app-link";
import { ArrowRightIcon, ArrowUpRightIcon, ConversationIcon, SparkIcon } from "@/components/icons";
import { BrandHeader } from "@/components/brand-header";
import { Logo } from "@/components/logo";
import { publicSpaceHref, studioHref } from "@/lib/hosts";

const reveal = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0 },
};

export function LandingPage() {
  const heroRef = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const imageY = useTransform(scrollYProgress, [0, 1], [0, reduceMotion ? 0 : 72]);
  const imageScale = useTransform(scrollYProgress, [0, 1], [1.025, reduceMotion ? 1.025 : 1.075]);
  const textOpacity = useTransform(scrollYProgress, [0, 0.75], [1, reduceMotion ? 1 : 0.25]);

  return (
    <main className="landing">
      <section ref={heroRef} className="landing-hero" aria-labelledby="hero-title">
        <motion.div className="landing-hero__image" style={{ y: imageY, scale: imageScale }}>
          <img
            src="/images/laggente-hero.webp"
            alt="Un agente immobiliare prepara il proprio spazio di lavoro in una casa romana luminosa"
            sizes="100vw"
            fetchPriority="high"
          />
        </motion.div>
        <div className="landing-hero__veil" />
        <BrandHeader inverse />
        <motion.div
          className="landing-hero__content"
          initial="hidden"
          animate="visible"
          transition={{ staggerChildren: reduceMotion ? 0 : 0.12, delayChildren: 0.12 }}
          style={{ opacity: textOpacity }}
        >
          <motion.p variants={reveal} transition={{ duration: 0.5 }} className="eyebrow eyebrow--light">
            Il tuo spazio immobiliare personale
          </motion.p>
          <motion.h1 variants={reveal} transition={{ duration: 0.65 }} id="hero-title">
            La gente incontra <em>l’agente.</em>
          </motion.h1>
          <motion.p variants={reveal} transition={{ duration: 0.55 }} className="landing-hero__lead">
            Una conversazione che inizia subito, ricorda ciò che conta e porta la persona giusta più vicino al professionista.
          </motion.p>
          <motion.div variants={reveal} transition={{ duration: 0.5 }} className="landing-hero__actions">
            <Link className="button button--paper" href={publicSpaceHref("mauro")}>
              Incontra Mauro <ArrowRightIcon />
            </Link>
            <span className="landing-hero__note">Assistente AI sempre dichiarato</span>
          </motion.div>
        </motion.div>
        <div className="landing-hero__scroll" aria-hidden="true">
          <span>Scopri</span><i />
        </div>
      </section>

      <section className="manifesto" aria-labelledby="manifesto-title">
        <motion.div
          className="manifesto__intro"
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.45 }}
          transition={{ duration: 0.65 }}
        >
          <p className="section-index">01 / Uno spazio vivo</p>
          <h2 id="manifesto-title">Non un modulo da compilare.<br />Un luogo in cui tornare.</h2>
        </motion.div>
        <div className="manifesto__flow" aria-label="Come funziona LAGGENTE">
          <article>
            <span className="manifesto__number">I</span>
            <div>
              <h3>Il professionista parla</h3>
              <p>Nel suo Studio privato racconta territorio, metodo e modo di accogliere. Lo spazio prende forma senza una gabbia di campi.</p>
            </div>
          </article>
          <article>
            <span className="manifesto__number">II</span>
            <div>
              <h3>L’assistente riceve</h3>
              <p>Le persone conversano in modo naturale con un’AI trasparente, guidata solo da ciò che il professionista ha attivato.</p>
            </div>
          </article>
          <article>
            <span className="manifesto__number">III</span>
            <div>
              <h3>L’umano entra</h3>
              <p>Quando serve giudizio, presenza o fiducia, il professionista raggiunge la stessa conversazione senza perdere il contesto.</p>
            </div>
          </article>
        </div>
      </section>

      <section className="atelier" aria-labelledby="atelier-title">
        <div className="atelier__tone" aria-hidden="true">
          <span>L</span><span>A</span><span>G</span><span>G</span><span>E</span><span>N</span><span>T</span><span>E</span>
        </div>
        <div className="atelier__copy">
          <p className="section-index section-index--light">02 / Due conversazioni, un solo spazio</p>
          <h2 id="atelier-title">La tecnologia resta dietro.<br />Davanti, una relazione.</h2>
          <p>Il tuo assistente pubblico mantiene continuità. Il tuo Studio privato trasforma ciò che gli insegni in una presenza fedele, sempre sotto il tuo controllo.</p>
          <Link href={studioHref("/login")} className="text-link text-link--light">Apri lo Studio <ArrowUpRightIcon /></Link>
        </div>
        <div className="atelier__signals">
          <div><ConversationIcon /><span>Conversazioni<br />persistenti</span></div>
          <div><SparkIcon /><span>Memoria<br />correggibile</span></div>
          <div><span className="atelier__human">M</span><span>Presenza umana<br />nello stesso filo</span></div>
        </div>
      </section>

      <section className="mauro-feature" aria-labelledby="mauro-title">
        <div className="mauro-feature__portrait">
          <div className="mauro-feature__monogram" aria-hidden="true">M</div>
          <p>Roma Nord<br />Presenza locale</p>
        </div>
        <motion.div
          className="mauro-feature__content"
          initial={{ opacity: 0, x: 28 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.65 }}
        >
          <p className="section-index">03 / Il primo spazio</p>
          <h2 id="mauro-title">“Raccontami da dove vuoi partire.”</h2>
          <p className="mauro-feature__quote">Lo spazio di Mauro accoglie chi sta pensando di vendere una casa con chiarezza, senza pressioni e senza trasformare la conversazione in un interrogatorio.</p>
          <div className="mauro-feature__byline">
            <div><strong>Mauro Rossi</strong><span>Agente immobiliare · Roma</span></div>
            <Link className="circle-link" href={publicSpaceHref("mauro")} aria-label="Entra nello spazio pubblico di Mauro"><ArrowRightIcon /></Link>
          </div>
        </motion.div>
      </section>

      <section className="closing" aria-labelledby="closing-title">
        <p className="section-index">04 / Entra</p>
        <h2 id="closing-title">La porta è aperta.</h2>
        <div className="closing__actions">
          <Link href={publicSpaceHref("mauro")}>Parla con l’assistente di Mauro <ArrowUpRightIcon /></Link>
          <Link href={studioHref("/login")}>Sei un professionista? Entra nello Studio <ArrowUpRightIcon /></Link>
        </div>
      </section>

      <footer className="brand-footer">
        <Logo />
        <p>La gente incontra l’agente.</p>
        <div><Link href="/privacy">Privacy</Link><span>© 2026 LAGGENTE</span></div>
      </footer>
    </main>
  );
}
