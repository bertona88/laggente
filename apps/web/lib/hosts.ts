function normalizedHostname(explicit?: string): string {
  if (explicit) return explicit.trim().toLocaleLowerCase("en-US").replace(/\.$/, "");
  if (typeof window !== "undefined" && window.location.hostname) {
    return window.location.hostname.toLocaleLowerCase("en-US");
  }
  return import.meta.env.PROD ? "laggente.com" : "localhost";
}

export function isLocalHostname(hostname: string): boolean {
  const value = hostname.trim().toLocaleLowerCase("en-US").replace(/^\[|\]$/g, "");
  return value === "localhost"
    || value === "127.0.0.1"
    || value === "0.0.0.0"
    || value === "::1"
    || value.endsWith(".localhost");
}

export function publicSpaceHref(slug: string, hostname?: string): string {
  const safeSlug = slug.trim().toLocaleLowerCase("en-US");
  return isLocalHostname(normalizedHostname(hostname))
    ? `/${safeSlug}`
    : `https://${safeSlug}.laggente.com`;
}

export function studioHref(path = "/login", hostname?: string): string {
  const safePath = path.startsWith("/") ? path : `/${path}`;
  return isLocalHostname(normalizedHostname(hostname))
    ? safePath
    : `https://app.laggente.com${safePath}`;
}
