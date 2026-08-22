import { useEffect } from "react";

export function useVisualViewportHeight() {
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () => {
      const height = viewport?.height || window.innerHeight;
      document.documentElement.style.setProperty("--visual-viewport-height", `${Math.round(height)}px`);
    };
    update();
    viewport?.addEventListener("resize", update);
    viewport?.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    return () => {
      viewport?.removeEventListener("resize", update);
      viewport?.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);
}

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} — LAGGENTE` : "LAGGENTE — La gente incontra l’agente";
  }, [title]);
}
