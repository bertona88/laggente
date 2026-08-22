import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useLocation } from "wouter";
import { AppLink as Link, useAppNavigate } from "@/components/app-link";
import {
  CloseIcon,
  ConversationIcon,
  LayersIcon,
  LogOutIcon,
  MenuIcon,
  StudioIcon,
} from "@/components/icons";
import { Logo } from "@/components/logo";
import { apiRequest, isUnauthorized } from "@/lib/api";
import { initials } from "@/lib/format";
import { publicSpaceHref, studioHref } from "@/lib/hosts";

const navItems = [
  { href: "/studio", label: "Studio", icon: StudioIcon, exact: true },
  { href: "/studio/conversazioni", label: "Conversazioni", icon: ConversationIcon },
  { href: "/studio/spazio", label: "Spazio pubblico", icon: LayersIcon },
];

interface SessionInfo {
  professional_name?: string;
  name?: string;
  display_name?: string;
  email?: string;
  space_slug?: string;
}

export function StudioShell({ children }: { children: React.ReactNode }) {
  const [pathname] = useLocation();
  const navigate = useAppNavigate();
  const [session, setSession] = useState<SessionInfo>({ professional_name: "Mauro Rossi", space_slug: "mauro" });
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    apiRequest<SessionInfo | { member?: SessionInfo }>("/auth/session")
      .then((data) => setSession("member" in data && data.member ? data.member : data as SessionInfo))
      .catch((error) => {
        if (isUnauthorized(error)) navigate(studioHref("/login"), { replace: true });
      });
  }, [navigate]);

  async function logout() {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } finally {
      navigate(studioHref("/login"), { replace: true });
    }
  }

  const professionalName = session.professional_name || session.display_name || session.name || "Mauro Rossi";
  const nav = (
    <>
      <div className="studio-sidebar__brand">
        <Logo href={studioHref("/studio")} />
        <button type="button" onClick={() => setMenuOpen(false)} aria-label="Chiudi navigazione"><CloseIcon /></button>
      </div>
      <nav className="studio-nav" aria-label="Studio">
        <p>Il tuo spazio</p>
        {navItems.map((item) => {
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
        <span>Online ora</span>
        <strong>{session.space_slug || "mauro"}.laggente.com</strong>
        <Link href={publicSpaceHref(session.space_slug || "mauro")} target="_blank">Apri spazio pubblico ↗</Link>
      </div>
      <div className="studio-user">
        <span className="studio-user__avatar">{initials(professionalName)}</span>
        <div><strong>{professionalName}</strong><span>{session.email || "Agente immobiliare"}</span></div>
        <button type="button" onClick={() => void logout()} aria-label="Esci dallo Studio"><LogOutIcon /></button>
      </div>
    </>
  );

  return (
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
  );
}
