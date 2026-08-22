export function magicLinkTokenFromFragment(fragment: string): string | null {
  const value = fragment.startsWith("#") ? fragment.slice(1) : fragment;
  return new URLSearchParams(value).get("token");
}
