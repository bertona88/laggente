import type { AnchorHTMLAttributes, PropsWithChildren } from "react";
import { useCallback } from "react";
import { Link as WouterLink, useLocation } from "wouter";

type AppLinkProps = PropsWithChildren<
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string }
>;

function isExternalHref(href: string) {
  return /^(?:https?:|mailto:|tel:)/i.test(href) || href.startsWith("#");
}

export function AppLink({ href, children, ...props }: AppLinkProps) {
  if (isExternalHref(href) || props.target) {
    return <a href={href} {...props}>{children}</a>;
  }
  return <WouterLink href={href} {...props}>{children}</WouterLink>;
}

export function useAppNavigate() {
  const [, navigate] = useLocation();
  return useCallback((href: string, options: { replace?: boolean } = {}) => {
    const target = new URL(href, window.location.href);
    if (target.origin !== window.location.origin) {
      if (options.replace) window.location.replace(target.href);
      else window.location.assign(target.href);
      return;
    }
    navigate(`${target.pathname}${target.search}${target.hash}`, { replace: options.replace });
  }, [navigate]);
}
