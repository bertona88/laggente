import { AppLink as Link } from "@/components/app-link";

export function Logo({ href = "/", inverse = false }: { href?: string; inverse?: boolean }) {
  return (
    <Link className={`logo${inverse ? " logo--inverse" : ""}`} href={href} aria-label="LAGGENTE, pagina iniziale">
      <span className="logo__word">LAGGENTE</span>
      <span className="logo__dot" aria-hidden="true" />
    </Link>
  );
}
