import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { AppLink as Link } from "@/components/app-link";
import { ArrowRightIcon, ArrowUpRightIcon } from "@/components/icons";
import { BrandHeader } from "@/components/brand-header";
import { Logo } from "@/components/logo";
import { studioHref } from "@/lib/hosts";
import { apiRequest } from "@/lib/api";
import type { FeaturedVertical, ProductPositioning } from "@/lib/types";

// Neutral first paint and old-API/offline fallback; market examples come from the API.
const fallbackPositioning: ProductPositioning = {
  audience: "Per professionisti che seguono i propri clienti di persona.",
  opening_question: "Che lavoro fai?",
  homepage: {
    headline: "Un assistente AI che risponde ai tuoi clienti.",
    description: "LAGGENTE ti dà una pagina personale con un assistente AI. Lo prepari raccontandogli come lavori in una chat privata. I clienti gli scrivono; tu ritrovi le conversazioni e puoi rispondere di persona.",
  },
  featured_verticals: [],
};

const genericExample = {
  instruction: "Quando un cliente chiede un preventivo, chiedi di cosa ha bisogno. Spiega che preparo io la proposta dopo averne parlato con lui.",
  visitor: "Vorrei un preventivo, ma non so da dove cominciare.",
  assistant: "Sono l’assistente AI del professionista. Per il preventivo ne parlerai con lui. Intanto, che cosa ti serve?",
  professional: "Ho letto la conversazione. Possiamo approfondire insieme la tua richiesta, poi ti preparo una proposta.",
};

const chapters = [
  { label: "Gli insegni", title: "Tu gli racconti come lavori.", description: "Apri Studio, la tua chat privata. Spieghi cosa fai, quali informazioni usare e come vuoi che l’assistente risponda ai clienti." },
  { label: "Approvi", title: "Prima controlli. Poi attivi.", description: "Studio trasforma quello che gli hai detto in istruzioni per il tuo assistente. Le rivedi insieme a lui e le attivi quando ti piacciono." },
  { label: "Condividi", title: "Ai clienti basta un link.", description: "Scegli il tuo indirizzo personale e lo condividi. Chi lo apre trova la tua pagina e può scrivere al tuo assistente AI, senza creare un account." },
  { label: "L’AI risponde", title: "Il cliente scrive. L’assistente risponde.", description: "Anche quando sei impegnato, l’assistente raccoglie la richiesta e risponde seguendo il modo di lavorare che gli hai insegnato." },
  { label: "Intervieni", title: "Tu riprendi da ciò che si sono detti.", description: "In Studio ritrovi la richiesta e quello che l’assistente ha risposto. Puoi entrare nella stessa chat e continuare tu: il cliente non deve ricominciare da capo." },
];

type Example = NonNullable<FeaturedVertical["conversation_example"]>;

function Message({ author, text, progress = 1, human = false }: { author: string; text: string; progress?: number; human?: boolean }) {
  const count = Math.ceil(text.length * Math.min(1, Math.max(0, progress)));
  return <div className={`product-demo__message${human ? " product-demo__message--human" : ""}`}>
    <strong>{author}</strong>
    <p className="product-demo__typed">
      <span className="product-demo__reserve" aria-hidden="true">{text}</span>
      <span className="product-demo__ink" aria-hidden="true">{text.slice(0, count)}{count < text.length && <i className="product-demo__cursor" />}</span>
      <span className="sr-only">{text}</span>
    </p>
  </div>;
}

function DemoScene({ step, progress, example, openingQuestion }: { step: number; progress: number; example: Example; openingQuestion: string }) {
  const typed = Math.min(1, Math.max(0, (progress - 0.08) / 0.65));
  return <div className={`product-demo product-demo--${step}`}>
    <header className="product-demo__header">
      <span className="product-demo__indicator" />
      <strong>{step < 2 ? "Studio · solo tu e l’AI" : step === 2 ? "La tua pagina personale" : "nome.laggente.com"}</strong>
      <span>{step < 2 ? "Privato" : "Per i clienti"}</span>
    </header>
    <div className="product-demo__body">
      {step === 0 && <>
        <Message author="Studio · assistente AI" text={openingQuestion} />
        <Message author="Tu" text={example.instruction} progress={typed} human />
        <div className="product-demo__note">Stai insegnando al tuo assistente come lavorare.</div>
      </>}
      {step === 1 && <>
        <p className="product-demo__eyebrow">Proposta di Studio</p>
        <h3>Ecco come risponderà il tuo assistente.</h3>
        <Message author="Istruzioni da approvare" text={example.instruction} progress={typed} />
        <div className={`product-demo__approval${progress > 0.78 ? " is-approved" : ""}`}>
          {progress > 0.78 ? "✓ Hai attivato queste istruzioni" : "In attesa della tua approvazione"}
        </div>
        <div className="product-demo__note">Puoi chiedere correzioni prima di attivare.</div>
      </>}
      {step === 2 && <div className="product-demo__link-scene">
        <p className="product-demo__eyebrow">Il link che condividi</p>
        <h3><span>nome</span>.laggente.com</h3>
        <div className="product-demo__link-line" style={{ transform: `scaleY(${typed})` }} />
        <div className="product-demo__destination" style={{ opacity: typed }}>
          <Logo />
          <strong>Il tuo nome, il tuo lavoro.</strong>
          <p>«Ciao, sono l’assistente AI del professionista. Come posso aiutarti?»</p>
          <span>Il cliente può iniziare a scrivere.</span>
        </div>
      </div>}
      {step === 3 && <>
        <Message author="Cliente" text={example.visitor} human />
        <Message author="Il tuo assistente AI" text={example.assistant} progress={typed} />
        <div className="product-demo__note">La risposta segue le istruzioni che hai approvato.</div>
      </>}
      {step === 4 && <>
        <div className="product-demo__context"><strong>La richiesta del cliente</strong><p>{example.visitor}</p></div>
        <div className="product-demo__takeover">Sei entrato tu · risposte AI in pausa</div>
        <Message author="Tu · professionista" text={example.professional} progress={typed} human />
        <div className="product-demo__note">Il cliente continua nella stessa conversazione.</div>
      </>}
    </div>
    <footer>Esempio di utilizzo</footer>
  </div>;
}

function ProductStory({ example, openingQuestion, vertical }: { example: Example; openingQuestion: string; vertical?: string }) {
  const storyRef = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const [readAll, setReadAll] = useState(false);
  const [shortViewport, setShortViewport] = useState(false);
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    const query = window.matchMedia("(max-height: 600px)");
    const update = () => setShortViewport(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (readAll) storyRef.current?.scrollIntoView({ block: "start" });
  }, [readAll]);
  const { scrollYProgress } = useScroll({ target: storyRef, offset: ["start start", "end end"] });
  useMotionValueEvent(scrollYProgress, "change", setProgress);
  const staticMode = reduceMotion || shortViewport || readAll;
  const scaled = Math.min(progress * chapters.length, chapters.length - 0.0001);
  const step = Math.floor(scaled);
  const chapter = chapters[step];

  return <section id="come-funziona" ref={storyRef} className={`product-story${staticMode ? " product-story--static" : ""}`} aria-label="Come funziona LAGGENTE, passo per passo">
    {staticMode ? <>
      <div className="product-story__static-intro"><p className="section-index">Come funziona · esempio illustrativo{vertical ? ` · ${vertical}` : ""}</p>
        {!reduceMotion && !shortViewport && <button type="button" onClick={() => setReadAll(false)}>Torna alla versione animata</button>}
      </div>
      {chapters.map((item, index) => <article key={item.label} className="product-story__static-step">
        <div className="product-story__copy"><p className="section-index">0{index + 1} / 05</p><h2>{item.title}</h2><p>{item.description}</p></div>
        <DemoScene step={index} progress={1} example={example} openingQuestion={openingQuestion} />
      </article>)}
    </> : <div className="product-story__sticky">
      <div className="product-story__top"><p className="section-index">Scorri per vedere come funziona{vertical ? ` · ${vertical}` : ""}</p><button type="button" onClick={() => setReadAll(true)}>Leggi senza animazioni</button></div>
      <div className="product-story__stage">
        <div className="product-story__copy">
          <p className="product-story__count">0{step + 1}<span> / 05</span></p>
          <AnimatePresence mode="wait"><motion.div key={step} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
            <h2>{chapter.title}</h2><p>{chapter.description}</p>
          </motion.div></AnimatePresence>
        </div>
        <div className="product-story__screen">
          <AnimatePresence mode="wait"><motion.div key={step} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
            <DemoScene step={step} progress={scaled - step} example={example} openingQuestion={openingQuestion} />
          </motion.div></AnimatePresence>
        </div>
      </div>
      <div className="product-story__progress" aria-label={`Passaggio ${step + 1} di 5: ${chapter.label}`}>
        {chapters.map((item, index) => <div key={item.label} className={index === step ? "is-current" : ""}><span><i style={{ transform: `scaleX(${Math.min(1, Math.max(0, scaled - index))})` }} /></span><p>{item.label}</p></div>)}
      </div>
    </div>}
  </section>;
}

export function LandingPage() {
  const [positioning, setPositioning] = useState(fallbackPositioning);
  const [heroStep, setHeroStep] = useState(0);
  const reduceMotion = useReducedMotion();
  useEffect(() => {
    let active = true;
    apiRequest<ProductPositioning>("/product/positioning").then((value) => { if (active) setPositioning(value); }).catch(() => undefined);
    return () => { active = false; };
  }, []);
  const copy = positioning.homepage ?? fallbackPositioning.homepage!;
  const featured = positioning.featured_verticals[0];
  const example = featured?.conversation_example ?? genericExample;
  return <main className="landing landing--explain">
    <section className="landing-hero" aria-labelledby="hero-title">
      <div className="landing-hero__image"><img src="/media/laggente-hero.webp" alt="Una professionista nel proprio spazio di lavoro" fetchPriority="high" /></div>
      <div className="landing-hero__veil" />
      <BrandHeader inverse />
      <div className="landing-hero__layout">
      <motion.div className="landing-hero__content" initial={reduceMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <p className="eyebrow eyebrow--light">LAGGENTE · AI per professionisti</p>
        <h1 id="hero-title">{copy.headline}</h1>
        <p className="landing-hero__lead">{copy.description}</p>
        <div className="landing-hero__actions">
          <Link className="button button--paper" href="#come-funziona">Guarda come funziona <ArrowRightIcon /></Link>
          <Link className="landing-hero__studio-link" href={studioHref("/login")}>Crea il tuo assistente <ArrowUpRightIcon /></Link>
        </div>
        <p className="landing-hero__scroll">Scorri: dall’istruzione al primo cliente ↓</p>
      </motion.div>
      <div className="landing-hero__demo">
        <div className="landing-hero__demo-tabs" role="group" aria-label="Esplora l’esempio">
          {[{ step: 0, label: "Tu lo prepari" }, { step: 3, label: "L’AI risponde" }, { step: 4, label: "Tu intervieni" }].map((item) => <button key={item.step} type="button" aria-pressed={heroStep === item.step} onClick={() => setHeroStep(item.step)}>{item.label}</button>)}
        </div>
        <DemoScene step={heroStep} progress={1} example={example} openingQuestion={positioning.opening_question} />
        <div className="landing-hero__mobile-actions"><Link href={studioHref("/login")}>Crea il tuo assistente <ArrowUpRightIcon /></Link><Link href="#come-funziona">Scopri come ↓</Link></div>
      </div>
      </div>
    </section>
    <ProductStory example={example} openingQuestion={positioning.opening_question} vertical={featured?.conversation_example ? featured.label : undefined} />
    <section id="due-lati" className="product-roles" aria-labelledby="roles-title">
      <p className="section-index">Cosa trovi in LAGGENTE</p>
      <h2 id="roles-title">Una chat privata per te.<br />Una pagina per i tuoi clienti.</h2>
      <div className="product-roles__columns">
        <article><p className="eyebrow">Tu · app.laggente.com</p><h3>Il tuo Studio privato</h3><p>Qui parli con l’AI che ti aiuta a preparare e aggiornare l’assistente. Aggiungi informazioni e documenti, controlli le proposte e le attivi. Qui ritrovi anche le conversazioni dei clienti.</p></article>
        <article><p className="eyebrow">I clienti · nome.laggente.com</p><h3>La tua pagina con l’assistente</h3><p>Qui i clienti parlano con l’AI che hai preparato. L’assistente risponde alle loro domande e ricorda quello che si sono detti. Tu puoi leggere e intervenire in ogni conversazione.</p></article>
      </div>
      {featured && <div className="product-roles__pilot"><p className="section-index">Da chi partiamo</p><h3>{featured.label}</h3><p>{featured.description}</p><p>{positioning.audience}</p></div>}
    </section>
    <section id="inizia" className="closing" aria-labelledby="closing-title">
      <p className="section-index">Aperto ai professionisti</p>
      <h2 id="closing-title">Comincia raccontando<br />che lavoro fai.</h2>
      <p className="closing__explanation">Inserisci la tua email e apri il link di accesso. Entri nel tuo Studio e inizi a preparare il tuo assistente.</p>
      <div className="closing__actions"><Link href={studioHref("/login")}>Crea il tuo assistente <ArrowUpRightIcon /></Link><Link href="#come-funziona">Rivedi l’esempio <ArrowRightIcon /></Link></div>
    </section>
    <footer className="brand-footer"><Logo /><p>La gente incontra l’agente.</p><div><Link href="/privacy">Privacy</Link><span>© 2026 LAGGENTE</span></div></footer>
  </main>;
}
