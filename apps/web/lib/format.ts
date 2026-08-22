const italianDateTime = new Intl.DateTimeFormat("it-IT", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Rome",
});

const italianTime = new Intl.DateTimeFormat("it-IT", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Rome",
});

function apiDate(value: string): Date {
  // PostgreSQL returns timezone-aware values; SQLite used by local acceptance can
  // round-trip the same UTC columns without an explicit offset.
  const normalized = /(?:z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Date(normalized);
}

export function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const date = apiDate(value);
  return Number.isNaN(date.getTime()) ? "—" : italianDateTime.format(date);
}

export function formatTime(value?: string | null) {
  if (!value) return "";
  const date = apiDate(value);
  return Number.isNaN(date.getTime()) ? "" : italianTime.format(date);
}

export function initials(value: string) {
  return value
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function hostnameSlug(hostname: string) {
  const clean = hostname.toLowerCase().split(":")[0];
  if (clean.endsWith(".laggente.com")) {
    const slug = clean.slice(0, -".laggente.com".length);
    return slug && !["www", "app"].includes(slug) ? slug : null;
  }
  if (clean.endsWith(".localhost")) return clean.split(".")[0] || null;
  return null;
}
