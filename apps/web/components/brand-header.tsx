import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AppLink as Link } from "@/components/app-link";
import { ArrowUpRightIcon, CloseIcon, MenuIcon } from "@/components/icons";
import { Logo } from "@/components/logo";
import { studioHref } from "@/lib/hosts";

export function BrandHeader({ inverse = false }: { inverse?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <header className={`brand-header${inverse ? " brand-header--inverse" : ""}`}>
      <Logo inverse={inverse} />
      <nav className="brand-nav" aria-label="Navigazione principale">
        <Link href="#come-funziona">Come funziona</Link>
        <Link href="#spazio-pubblico">Lo spazio pubblico</Link>
        <Link href="#due-lati">I due lati</Link>
      </nav>
      <Link className="brand-header__cta" href={studioHref("/login")}>
        Accedi allo Studio <ArrowUpRightIcon />
      </Link>
      <button
        className="brand-header__menu"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="mobile-menu"
        aria-label={open ? "Chiudi il menu" : "Apri il menu"}
      >
        {open ? <CloseIcon /> : <MenuIcon />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.nav
            id="mobile-menu"
            className="mobile-menu"
            aria-label="Navigazione mobile"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
          >
            <Link href="#come-funziona" onClick={() => setOpen(false)}>Come funziona</Link>
            <Link href="#spazio-pubblico" onClick={() => setOpen(false)}>Lo spazio pubblico</Link>
            <Link href="#due-lati" onClick={() => setOpen(false)}>I due lati</Link>
            <Link href={studioHref("/login")} onClick={() => setOpen(false)}>Accedi allo Studio</Link>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
