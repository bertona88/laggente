import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useLocation } from "wouter";
import { AppLink as Link, useAppNavigate } from "@/components/app-link";
import {
  CloseIcon,
  ConversationIcon,
  LayersIcon,
  LogOutIcon,
  MenuIcon,
  InviteIcon,
  NetworkIcon,
  StudioIcon,
} from "@/components/icons";
import { Logo } from "@/components/logo";
import { apiRequest, isUnauthorized } from "@/lib/api";
import { initials } from "@/lib/format";
import { publicSpaceHref, studioHref } from "@/lib/hosts";
import type { StudioSession } from "@/lib/types";

const navItems = [
  { href: "/studio", label: "Studio", icon: StudioIcon, exact: true },
  { href: "/studio/conversazioni", label: "Conversazioni", icon: ConversationIcon },
  { href: "/studio/grafo", label: "Grafo", icon: NetworkIcon },
  { href: "/studio/spazio", label: "Spazio pubblico", icon: LayersIcon },
];

interface StudioSessionContextValue {
  session: StudioSession | null;
  loading: boolean;
  refreshSession: () => Promise<void>;
}

const StudioSessionContext = createContext<StudioSessionContextValue>({
  session: null,
  loading: true,
  refreshSession: async () => undefined,
});

export function useStudioSession() {
  return useContext(StudioSessionContext);
}

export function StudioShell({ children }: { children: React.ReactNode }) {
  const [pathname] = useLocation();
  const navigate = useAppNavigate();
  const [session, setSession] = useState<StudioSession | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);

  const refreshSession = useCallback(async () => {
    try {
      setSession(await apiRequest<StudioSession>("/auth/session"));
    } catch (error) {
      if (isUnauthorized(error)) navigate(studioHref("/login"), { replace: true });
      else throw error;
    } finally {
      setSessionLoading(false);
    }
  }, [navigate]);

  useEffect(() => { void refreshSession().catch(() => undefined); }, [refreshSession]);

  async function logout() {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } finally {
      navigate(studioHref("/login"), { replace: true });
    }
  }

  const professionalName = session?.member.display_name || "Il tuo Studio";
  const space = session?.space;
  const visibleNavItems = session?.member.can_invite
    ? [...navItems, { href: "/studio/inviti", label: "Invita", icon: InviteIcon }]
    : navItems;
  const nav = (
    <>
      <div className="studio-sidebar__brand">
        <Logo href={studioHref("/studio")} />
        <button type="button" onClick={() => setMenuOpen(false)} aria-label="Chiudi navigazione"><CloseIcon /></button>
      </div>
      <nav className="studio-nav" aria-label="Studio">
        <p>Il tuo spazio</p>
        {visibleNavItems.map((item) => {
          const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} className={active ? "is-active" : ""} onClick={() => setMenuOpen(false)}>
              <Icon /><span>{item.label}</span>{active && <motion.i layoutId="studio-nav-active" />}
            </Link>
          );
        })}
      </nav>
      <div className="studio-sidebar__public">
        <span>{space?.is_active ? "Online ora" : space?.slug_claimed ? "Indirizzo riservato" : "In preparazione"}</span>
        <strong>{space?.slug_claimed ? `${space.slug}.laggente.com` : "Scegli il tuo indirizzo"}</strong>
        {space?.is_active && space.slug_claimed
          ? <Link href={publicSpaceHref(space.slug)} target="_blank">Apri spazio pubblico ↗</Link>
          : <Link href="/studio">Completa lo spazio →</Link>}
      </div>
      <div className="studio-user">
        <span className="studio-user__avatar">{initials(professionalName)}</span>
        <div><strong>{professionalName}</strong><span>{session?.member.email || "Accesso privato"}</span></div>
        <button type="button" onClick={() => void logout()} aria-label="Esci dallo Studio"><LogOutIcon /></button>
      </div>
    </>
  );

  return (
    <StudioSessionContext.Provider value={{ session, loading: sessionLoading, refreshSession }}>
    <div className="studio-layout">
      <aside className="studio-sidebar">{nav}</aside>
      <header className="studio-mobile-header">
        <Logo href={studioHref("/studio")} />
        <button type="button" onClick={() => setMenuOpen(true)} aria-label="Apri navigazione"><MenuIcon /></button>
      </header>
      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.button
              className="studio-drawer-backdrop"
              type="button"
              aria-label="Chiudi navigazione"
              onClick={() => setMenuOpen(false)}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            />
            <motion.aside
              className="studio-drawer"
              initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
            >{nav}</motion.aside>
          </>
        )}
      </AnimatePresence>
      <div className="studio-main">{children}</div>
    </div>
    </StudioSessionContext.Provider>
  );
}
