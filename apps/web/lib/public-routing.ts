function isResolvedTenantHost(hostValue: string) {
  const hostname = hostValue.trim().toLocaleLowerCase("en-US").replace(/:\d+$/, "").replace(/\.$/, "");
  if (!hostname.endsWith(".laggente.com")) return false;
  const slug = hostname.slice(0, -".laggente.com".length);
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)
    && !new Set(["www", "app", "api"]).has(slug);
}

export function publicSpaceEndpoint(slug: string, hostValue = window.location.host) {
  return isResolvedTenantHost(hostValue)
    ? "/public/resolve"
    : `/public/${encodeURIComponent(slug)}`;
}

export function publicConversationCreateEndpoint(slug: string, hostValue = window.location.host) {
  return isResolvedTenantHost(hostValue)
    ? "/public/resolve/conversations"
    : `/public/${encodeURIComponent(slug)}/conversations`;
}
