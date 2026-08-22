const RESERVED = new Set([
  "www",
  "app",
  "api",
  "admin",
  "status",
  "mail",
  "send",
  "support",
  "staging",
]);

const GLOBAL_PATHS = new Set(["/privacy", "/terms"]);

export function canonicalProductRedirect(
  hostValue: string,
  pathname: string,
  search = "",
): string | null {
  const host = hostValue.split(":")[0].toLowerCase();
  const productionHost = host === "laggente.com" || host.endsWith(".laggente.com");
  if (
    productionHost
    && host !== "mauro.laggente.com"
    && (pathname === "/mauro" || pathname.startsWith("/mauro/"))
  ) {
    const tenantPath = pathname.slice("/mauro".length) || "/";
    return `https://mauro.laggente.com${tenantPath}${search}`;
  }
  if (host !== "laggente.com" && host !== "www.laggente.com") return null;
  if (
    pathname === "/login"
    || pathname.startsWith("/login/")
    || pathname === "/studio"
    || pathname.startsWith("/studio/")
  ) {
    return `https://app.laggente.com${pathname}${search}`;
  }
  return null;
}

export function tenantSlugFromHost(hostValue: string) {
  const host = hostValue.split(":")[0].toLowerCase();
  let slug: string | null = null;
  if (host.endsWith(".laggente.com")) slug = host.slice(0, -".laggente.com".length);
  else if (host.endsWith(".localhost")) slug = host.split(".")[0];
  if (!slug || RESERVED.has(slug) || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) return null;
  return slug;
}

export function tenantRewriteTarget(host: string, pathname: string) {
  if (GLOBAL_PATHS.has(pathname)) return null;
  const slug = tenantSlugFromHost(host);
  if (!slug) return null;
  return `/spazio/${slug}${pathname === "/" ? "" : pathname}`;
}
