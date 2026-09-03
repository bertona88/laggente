const RESERVED = new Set([
  "www",
  "app",
  "api",
  "admin",
  "assets",
  "blog",
  "status",
  "mail",
  "outreach",
  "privacy",
  "send",
  "short123",
  "spazio",
  "support",
  "staging",
  "studio",
  "static",
  "terms",
  "login",
]);

const GLOBAL_PATHS = new Set(["/privacy", "/terms"]);

export function isReservedTenantSlug(slug: string) {
  return RESERVED.has(slug.toLocaleLowerCase("en-US"));
}

export function canonicalProductRedirect(
  hostValue: string,
  pathname: string,
  search = "",
): string | null {
  const host = hostValue.split(":")[0].toLowerCase();
  const productionHost = host === "laggente.com" || host.endsWith(".laggente.com");
  const brandHost = host === "laggente.com" || host === "www.laggente.com";
  const studioHost = host === "app.laggente.com";
  if (
    brandHost
    && (
    pathname === "/login"
    || pathname.startsWith("/login/")
    || pathname === "/studio"
    || pathname.startsWith("/studio/")
    )
  ) {
    return `https://app.laggente.com${pathname}${search}`;
  }
  const publicPath = pathname.match(/^\/([a-z0-9]+(?:-[a-z0-9]+)*)(\/.*)?$/);
  if (productionHost && (brandHost || studioHost) && publicPath) {
    const slug = publicPath[1];
    if (!isReservedTenantSlug(slug)) {
      return `https://${slug}.laggente.com${publicPath[2] || "/"}${search}`;
    }
  }
  return null;
}

export function tenantSlugFromHost(hostValue: string) {
  const host = hostValue.split(":")[0].toLowerCase();
  let slug: string | null = null;
  if (host.endsWith(".laggente.com")) slug = host.slice(0, -".laggente.com".length);
  else if (host.endsWith(".localhost")) slug = host.split(".")[0];
  if (!slug || isReservedTenantSlug(slug) || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) return null;
  return slug;
}

export function tenantRewriteTarget(host: string, pathname: string) {
  if (GLOBAL_PATHS.has(pathname)) return null;
  const slug = tenantSlugFromHost(host);
  if (!slug) return null;
  return `/spazio/${slug}${pathname === "/" ? "" : pathname}`;
}
