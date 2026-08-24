import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { AppLink as Link } from "@/components/app-link";
import { ArrowRightIcon, ArrowUpRightIcon } from "@/components/icons";
import { BrandHeader } from "@/components/brand-header";
import { Logo } from "@/components/logo";
import { studioHref } from "@/lib/hosts";
import { apiRequest } from "@/lib/api";
import type { ProductPositioning } from "@/lib/types";

const reveal = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0 },
};

const fallbackPositioning: ProductPositioning = {
  audience: "Professionisti che lavorano attraverso relazioni, competenza e fiducia, a partire dagli agenti immobiliari.",
  opening_question: "Che lavoro fai?",
  featured_verticals: [{
    id: "real_estate_it",
    label: "Agenti immobiliari",
    weight: 100,
    status: "pilot",
    template_id: "seller_it_v1",
    example_answer: "Sono un agente immobiliare a Roma Nord. Prima di valutare un immobile controllo titolo di provenienza, conformità urbanistica e catastale, APE, occupazione e vincoli.",
    headline: "Partiamo dagli agenti immobiliari.",
    description: "È il primo settore che stiamo rendendo concreto: un template italiano per accogliere chi sta valutando di vendere, senza trasformare la conversazione in un questionario o in una pipeline.",
  }],
};

export function LandingPage() {
  const heroRef = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const imageY = useTransform(scrollYProgress, [0, 1], [0, reduceMotion ? 0 : 72]);
  const imageScale = useTransform(scrollYProgress, [0, 1], [1.025, reduceMotion ? 1.025 : 1.075]);
  const textOpacity = useTransform(scrollYProgress, [0, 0.78], [1, reduceMotion ? 1 : 0.2]);
  const [positioning, setPositioning] = useState(fallbackPositioning);

  useEffect(() => {
    apiRequest<ProductPositioning>("/product/positioning")
      .then(setPositioning)
      .catch(() => undefined);
  }, []);

  const featuredVertical = positioning.featured_verticals[0] ?? fallbackPositioning.featured_verticals[0]!;

  return (
    <main className="landing">
      <section ref={heroRef} className="landing-hero" aria-labelledby="hero-title">
        <motion.div className="landing-hero__image" style={{ y: imageY, scale: imageScale }}>
          <img
            src="/images/laggente-hero.webp"
            alt="Una professionista nel proprio spazio di lavoro"
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
          transition={{ staggerChildren: reduceMotion ? 0 : 0.11, delayChildren: 0.1 }}
          style={{ opacity: textOpacity }}
        >
          <motion.p variants={reveal} transition={{ duration: 0.5 }} className="eyebrow eyebrow--light">
            Uno spazio AI per chi lavora con la gente
          </motion.p>
          <motion.h1 variants={reveal} transition={{ duration: 0.65 }} id="hero-title">
            La gente incontra <em>l’agente.</em>
          </motion.h1>
          <motion.p variants={reveal} transition={{ duration: 0.55 }} className="landing-hero__lead">
            Lo crei parlando con Studio. La gente entra dal tuo indirizzo, conversa con un assistente AI dichiarato e ritrova sempre lo stesso filo. Tu puoi leggerlo, correggerlo o unirti.
          </motion.p>
          <motion.div variants={reveal} transition={{ duration: 0.5 }} className="landing-hero__actions">
            <Link className="button button--paper" href="#come-funziona">
              Guarda come nasce <ArrowRightIcon />
            </Link>
            <Link className="landing-hero__studio-link" href={studioHref("/login")}>
              Crea il tuo spazio <ArrowUpRightIcon />
            </Link>
          </motion.div>
        </motion.div>
      </section>

      <section id="come-funziona" className="address-story" aria-labelledby="address-story-title">
        <motion.div
          className="address-story__intro"
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.45 }}
          transition={{ duration: 0.65 }}
        >
          <p className="section-index">01 / Come nasce il tuo spazio</p>
          <div>
            <h2 id="address-story-title">Modella il tuo stile.<br />Chattando.</h2>
            <p>Prima parli in privato con Studio: gli racconti come lavori e come vuoi accogliere la gente. Studio prepara lo spazio; tu lo rivedi, lo correggi e decidi quando aprirlo.</p>
          </div>
        </motion.div>

        <div className="address-story__sequence" aria-label="Come funziona LAGGENTE">
          <motion.article
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.5 }}
          >
            <span className="address-story__number">01</span>
            <p className="eyebrow">Chat privata · Configurazione</p>
            <div className="address-story__dialogue" aria-label="Chat privata di configurazione tra il professionista e Studio">
              <p><span>Studio AI</span>{positioning.opening_question}</p>
              <p className="address-story__dialogue-answer"><span>Professionista</span>{featuredVertical.example_answer}</p>
              <p><span>Studio AI</span>Perfetto. Li userò come contesto, non come una checklist da imporre alla gente.</p>
            </div>
            <h3>Configura il tuo spazio in privato.</h3>
            <p className="address-story__copy">Questa non è la chat con i visitatori. Qui Studio impara il tuo modo di lavorare e prepara una proposta che soltanto tu puoi attivare.</p>
          </motion.article>

          <motion.article
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.5, delay: reduceMotion ? 0 : 0.08 }}
          >
            <span className="address-story__number">02</span>
            <p className="eyebrow">Guarda l’anteprima</p>
            <div className="address-story__preview">
              <span>Il tuo spazio</span>
              <strong><i>nome</i>.laggente.com</strong>
              <small>In anteprima · visibile solo a te</small>
            </div>
            <h3>Vedi prima ciò che vedranno gli altri.</h3>
            <p className="address-story__copy">Ogni proposta resta privata finché non ti rappresenta. Puoi correggerla continuando a parlare.</p>
          </motion.article>

          <motion.article
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: 0.5, delay: reduceMotion ? 0 : 0.16 }}
          >
            <span className="address-story__number">03</span>
            <p className="eyebrow">Apri la porta</p>
            <div className="address-story__preview address-story__preview--active">
              <span>Il tuo spazio</span>
              <strong><i>nome</i>.laggente.com</strong>
              <small><b /> Aperto</small>
            </div>
            <h3>Lo attivi soltanto tu.</h3>
            <p className="address-story__copy">Da quel momento il tuo indirizzo accoglie la gente con la presenza che hai costruito.</p>
          </motion.article>
        </div>
      </section>

      <section id="spazio-pubblico" className="public-return" aria-labelledby="public-return-title">
        <motion.div
          className="public-return__copy"
          initial={{ opacity: 0, x: reduceMotion ? 0 : -24 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.65 }}
        >
          <p className="section-index section-index--light">02 / La chat della gente</p>
          <h2 id="public-return-title">La gente non compila.<br />Entra.</h2>
          <p>Questa è un’altra chat: pubblica e separata da Studio. La gente parla con l’assistente AI del professionista; il professionista legge lo stesso filo e può entrarci.</p>
          <div className="public-return__promise">
            <span>AI dichiarata</span>
            <span>Conversazioni persistenti</span>
            <span>Tu puoi entrare nello stesso filo</span>
          </div>
        </motion.div>

        <motion.div
          className="public-return__scene"
          initial={{ opacity: 0, y: reduceMotion ? 0 : 34 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.28 }}
          transition={{ duration: 0.72 }}
          aria-label="Esempio di chat pubblica tra un visitatore, l’assistente AI e il professionista"
        >
          <div className="public-return__browser">
            <span aria-hidden="true"><i /><i /><i /></span>
            <strong><b>nome</b>.laggente.com</strong>
            <small>Chat pubblica</small>
          </div>
          <div className="public-return__thread">
            <p className="public-return__day">Oggi</p>
            <article className="public-return__message public-return__message--ai">
              <span>AI</span>
              <div><strong>Assistente AI del professionista</strong><p>Ciao. Sono l’assistente AI di questo professionista. Posso raccogliere il contesto e passargli questa conversazione. Cosa vorresti capire?</p></div>
            </article>
            <article className="public-return__message public-return__message--visitor">
              <div><strong>Visitatore</strong><p>Sto pensando di vendere un appartamento ereditato a Roma Nord. Ho planimetria e APE, ma non so se la veranda è conforme.</p></div>
            </article>
            <article className="public-return__message public-return__message--human">
              <span>PRO</span>
              <div><strong>Il professionista è entrato</strong><p>Ho letto. Prima della valutazione verifichiamo la conformità della veranda. Se vuoi, carica qui la planimetria.</p></div>
            </article>
            <footer><i /> Questa conversazione resta qui quando tornate.</footer>
          </div>
        </motion.div>
      </section>

      <section id="due-lati" className="two-sides" aria-labelledby="two-sides-title">
        <div className="two-sides__intro">
          <p className="section-index">03 / Un luogo, due lati</p>
          <h2 id="two-sides-title">Davanti accoglie.<br />Dietro ti aiuta a capire.</h2>
        </div>
        <div className="two-sides__map">
          <motion.article
            initial={{ opacity: 0, x: reduceMotion ? 0 : -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.45 }}
            transition={{ duration: 0.55 }}
          >
            <p className="eyebrow">Per la gente</p>
            <h3><i>nome</i>.laggente.com</h3>
            <p>Una porta pubblica, personale. Qui l’assistente accoglie chi arriva, ricorda il contesto e rende facile trovarti.</p>
            <span>Spazio pubblico</span>
          </motion.article>
          <div className="two-sides__continuity" aria-hidden="true">
            <span>La stessa conversazione</span><i />
          </div>
          <motion.article
            initial={{ opacity: 0, x: reduceMotion ? 0 : 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.45 }}
            transition={{ duration: 0.55 }}
          >
            <p className="eyebrow">Per te</p>
            <h3>app.laggente.com</h3>
            <p>Il tuo Studio privato. Qui ritrovi le conversazioni, correggi ciò che l’AI ha capito e decidi quando partecipare.</p>
            <span>Studio privato</span>
          </motion.article>
        </div>

        <div className="two-sides__vertical">
          <p className="section-index">Il primo settore che stiamo costruendo bene</p>
          <h3>{featuredVertical.label}</h3>
          <p>{featuredVertical.description}</p>
          <span>Si parte da qui. Il tuo lavoro decide il resto.</span>
        </div>
      </section>

      <section className="human-control" aria-label="Controllo del professionista">
        <p>Tu scegli cosa va online.</p>
        <p>L’AI si presenta sempre come AI.</p>
        <p>Ogni voce conserva il proprio autore.</p>
      </section>

      <section className="closing" aria-labelledby="closing-title">
        <p className="section-index">Aperto ai professionisti</p>
        <h2 id="closing-title">Prima parli tu.<br />Poi la gente incontra l’agente.</h2>
        <div className="closing__actions">
          <Link href={studioHref("/login")}>Crea il tuo spazio <ArrowUpRightIcon /></Link>
          <Link href="#come-funziona">Rivedi come funziona <ArrowRightIcon /></Link>
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
