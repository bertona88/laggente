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
    document.title = title ? `${title} — LAGGENTE` : "Assistente AI per agenti immobiliari | LAGGENTE";
  }, [title]);
}

export function useCanonicalUrl(url: string | null) {
  useEffect(() => {
    const existing = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!url) {
      existing?.remove();
      return;
    }
    const canonical = existing || document.createElement("link");
    canonical.rel = "canonical";
    canonical.href = url;
    if (!existing) document.head.append(canonical);
  }, [url]);
}
