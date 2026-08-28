import { AppLink as Link } from "@/components/app-link";
import { ArrowLeftIcon } from "@/components/icons";
import { Logo } from "@/components/logo";
import { useDocumentTitle } from "@/src/use-app-frame";

export function PrivacyPage() {
  useDocumentTitle("Privacy");
  return (
    <main className="legal-page">
      <header><Logo /><Link href="/"><ArrowLeftIcon /> Torna alla pagina iniziale</Link></header>
      <article>
        <p className="section-index">Informazioni essenziali</p>
        <h1>La conversazione è privata.</h1>
        <p className="legal-page__lead">LAGGENTE conserva i messaggi per dare continuità alla conversazione e renderli disponibili al professionista del cui spazio fai parte.</p>
        <h2>Con chi stai parlando</h2>
        <p>Ogni messaggio indica chiaramente se è stato scritto dall’assistente AI, dal professionista o da te. L’assistente non impersona mai il professionista.</p>
        <h2>Cosa viene conservato</h2>
        <p>Conserviamo i messaggi, le informazioni che scegli di condividere e gli allegati necessari alla conversazione, compresi i documenti condivisi con il professionista. Le interpretazioni generate dall’AI sono visibili e correggibili. Le note vocali vengono eliminate dopo la trascrizione, salvo diversa indicazione esplicita.</p>
        <h2>Come interviene il fornitore AI</h2>
        <p>Il testo, le note vocali, le fotografie e il testo estratto dai documenti necessari a rispondere possono essere elaborati dal fornitore AI di LAGGENTE. Una fotografia viene inviata soltanto nel turno a cui è allegata; il suo indirizzo privato non viene condiviso. I documenti della conversazione restano accessibili soltanto ai partecipanti e agli assistenti autorizzati di quello spazio. LAGGENTE non usa la funzione di archiviazione delle risposte del fornitore.</p>
        <h2>Le tue scelte</h2>
        <p>Puoi chiedere al professionista l’accesso, la correzione o la cancellazione dei tuoi dati. Non è necessario fornire recapiti per iniziare una conversazione.</p>
        <p className="legal-page__notice">Questa informativa sintetica accompagna il pilot. L’informativa legale completa e i contatti del titolare saranno pubblicati prima dell’apertura al pubblico.</p>
      </article>
    </main>
  );
}

export function TermsPage() {
  useDocumentTitle("Condizioni d’uso");
  return (
    <main className="legal-page">
      <header><Logo /><Link href="/"><ArrowLeftIcon /> Torna alla pagina iniziale</Link></header>
      <article>
        <p className="section-index">Pilot LAGGENTE</p>
        <h1>Una conversazione, non una consulenza automatica.</h1>
        <p className="legal-page__lead">LAGGENTE aiuta a iniziare e continuare una conversazione con un professionista. L’assistente AI non sostituisce il suo giudizio.</p>
        <h2>Identità trasparente</h2>
        <p>L’assistente dichiara sempre di essere un sistema di intelligenza artificiale. Non può assumere impegni, confermare appuntamenti, sostituire una valutazione professionale o parlare come se fosse il professionista.</p>
        <h2>Uso responsabile</h2>
        <p>Condividi soltanto informazioni pertinenti. Non caricare documenti d’identità, dati di pagamento o materiali di terzi senza averne il diritto.</p>
        <h2>Risposte e verifiche</h2>
        <p>Le risposte dell’AI possono essere incomplete o inesatte. Le decisioni professionali, legali, fiscali, sanitarie o economiche richiedono una verifica con persone qualificate.</p>
        <p className="legal-page__notice">Queste condizioni sintetiche accompagnano il pilot e saranno sostituite dalle condizioni complete prima dell’apertura pubblica.</p>
      </article>
    </main>
  );
}
