import { useEffect, type ReactNode } from "react";
import { useLocation } from "wouter";
import { AppLink } from "@/components/app-link";
import { ConversationDetail } from "@/components/conversation-detail";
import { ConversationInbox } from "@/components/conversation-inbox";
import { LandingPage } from "@/components/landing-page";
import { InviteProfessional } from "@/components/invite-professional";
import { LoginForm } from "@/components/login-form";
import { Logo } from "@/components/logo";
import { PublicSpace } from "@/components/public-space";
import { RelationshipGraph } from "@/components/relationship-graph";
import { SpaceRevisions } from "@/components/space-revisions";
import { StudioShell } from "@/components/studio-shell";
import { StudioDocuments } from "@/components/studio-documents";
import { StudioWorkspace } from "@/components/studio-workspace";
import { canonicalProductRedirect, isReservedTenantSlug, tenantSlugFromHost } from "@/lib/tenant-routing";
import { PrivacyPage, TermsPage } from "@/src/legal-pages";
import { useCanonicalUrl, useDocumentTitle, useVisualViewportHeight } from "@/src/use-app-frame";

export function documentTitleForRoute(location: string, tenantSlug: string | null) {
  if (location === "/privacy") return "Privacy";
  if (location === "/terms") return "Condizioni d’uso";
  if (location === "/login") return "Accesso allo Studio";
  if (location === "/studio" || location === "/studio/") return "Studio privato";
  if (location === "/studio/conversazioni") return "Conversazioni — Studio";
  if (location.startsWith("/studio/conversazioni/")) return "Conversazione — Studio";
  if (location === "/studio/grafo") return "Grafo — Studio";
  if (location === "/studio/documenti") return "Documenti — Studio";
  if (location === "/studio/spazio") return "Spazio pubblico — Studio";
  if (location === "/studio/inviti") return "Invita — Studio";
  const pathSlug = tenantSlug
    ? null
    : location.match(/^\/(?:spazio\/)?([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/)?.[1];
  const slug = location === "/" && tenantSlug
    ? tenantSlug
    : pathSlug && !isReservedTenantSlug(pathSlug) ? pathSlug : null;
  if (slug) return `Spazio di ${slug.charAt(0).toLocaleUpperCase("it-IT")}${slug.slice(1)}`;
  return location === "/" ? "" : "Spazio non trovato";
}

export function canonicalUrlForRoute(location: string, tenantSlug: string | null, hostname: string) {
  if (tenantSlug) return location === "/" ? `https://${tenantSlug}.laggente.com/` : null;
  const normalizedHost = hostname.toLocaleLowerCase("en-US");
  if (normalizedHost === "app.laggente.com") return null;
  if (location === "/") return "https://laggente.com/";
  if (location === "/privacy" || location === "/terms") return `https://laggente.com${location}`;
  return null;
}

function Redirect({ href }: { href: string }) {
  useEffect(() => { window.location.replace(href); }, [href]);
  return <main className="route-wait" aria-live="polite">Apro lo spazio…</main>;
}

function NotFoundPage() {
  useDocumentTitle("Spazio non trovato");
  return (
    <main className="unknown-space">
      <Logo />
      <div><p className="eyebrow">Spazio non disponibile</p><h1>Questa porta non è ancora aperta.</h1><p>Controlla l’indirizzo oppure torna a LAGGENTE.</p><AppLink className="button button--ink" href="/">Torna alla pagina iniziale</AppLink></div>
    </main>
  );
}

function StudioArea({ location }: { location: string }) {
  const detailMatch = location.match(/^\/studio\/conversazioni\/([^/]+)$/);
  let page: ReactNode;
  if (detailMatch) page = <ConversationDetail conversationId={decodeURIComponent(detailMatch[1])} />;
  else if (location === "/studio/conversazioni") page = <ConversationInbox />;
  else if (location === "/studio/grafo") page = <RelationshipGraph />;
  else if (location === "/studio/documenti") page = <StudioDocuments />;
  else if (location === "/studio/spazio") page = <SpaceRevisions />;
  else if (location === "/studio/inviti") page = <InviteProfessional />;
  else if (location === "/studio" || location === "/studio/") page = <StudioWorkspace />;
  else page = <NotFoundPage />;
  return <StudioShell>{page}</StudioShell>;
}

function LocalRoutes({ location }: { location: string }) {
  if (location === "/") return <LandingPage />;
  if (location === "/login") return <LoginForm />;
  if (location === "/privacy") return <PrivacyPage />;
  if (location === "/terms") return <TermsPage />;
  if (location.startsWith("/studio")) return <StudioArea location={location} />;

  const internalSpace = location.match(/^\/spazio\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/);
  if (internalSpace) return <PublicSpace slug={internalSpace[1]} />;
  const publicPath = location.match(/^\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/);
  if (publicPath && !isReservedTenantSlug(publicPath[1])) return <PublicSpace slug={publicPath[1]} />;
  return <NotFoundPage />;
}

export function App() {
  const [location] = useLocation();
  useVisualViewportHeight();

  useEffect(() => {
    if (!window.location.hash) window.scrollTo({ top: 0, behavior: "auto" });
  }, [location]);

  const host = window.location.host;
  const hostname = window.location.hostname.toLowerCase();
  const tenantSlug = tenantSlugFromHost(host);
  useDocumentTitle(documentTitleForRoute(location, tenantSlug));
  useCanonicalUrl(canonicalUrlForRoute(location, tenantSlug, hostname));
  const canonical = canonicalProductRedirect(host, location, window.location.search);
  if (canonical) return <Redirect href={`${canonical}${window.location.hash}`} />;

  if (location === "/privacy") return <PrivacyPage />;
  if (location === "/terms") return <TermsPage />;

  if (tenantSlug) return location === "/" ? <PublicSpace slug={tenantSlug} /> : <NotFoundPage />;
  if (hostname === "app.laggente.com" && location === "/") return <Redirect href="/studio" />;
  return <LocalRoutes location={location} />;
}
