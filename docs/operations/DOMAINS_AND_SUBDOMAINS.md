# Domains and Subdomains

## Purpose

The personal subdomain is the professional's public digital branch office and the first node of the future LAGGENTE network.

All professional subdomains use one application deployment.

## Host map

| Host | Purpose |
| --- | --- |
| `laggente.com` | Brand and entry surface |
| `www.laggente.com` | Redirect to the canonical brand host |
| `app.laggente.com` | Private Studio and dashboard |
| `mauro.laggente.com` | Mauro's public branch office |
| `<slug>.laggente.com` | Any published professional branch office |

The API should normally be exposed as a same-origin `/api` route rather than requiring browser calls to a separate API subdomain.

## DNS plan

Namecheap and DNS changes are performed by local Codex with explicit authorization. The intended records are:

| Name | Type | Target |
| --- | --- | --- |
| `@` | `A` | Hetzner server IPv4 |
| `www` | `A` or `CNAME` | Canonical web host |
| `app` | `A` | Hetzner server IPv4 |
| `*` | `A` | Hetzner server IPv4 |

Use the actual server address at execution time. Do not commit IP addresses unless there is a deliberate reason to make them public project configuration.

## TLS

For the five-agent pilot, either:

1. issue certificates for the known named hosts; or
2. use a wildcard certificate for `*.laggente.com` through a DNS challenge.

The wildcard approach is the target because publishing a professional should not require a certificate or proxy change. DNS API credentials remain server-side.

## Slug rules

- lowercase ASCII letters, digits, and single hyphens;
- unique at the database level;
- cannot begin or end with a hyphen;
- immutable or deliberately migrated after publication;
- resolved only when the public profile is active and published.

Reserve at least:

```text
www
app
api
admin
status
mail
send
support
staging
```

## Routing and security

- Validate the `Host` header against `laggente.com` and expected subdomains.
- Unknown slugs return a safe 404.
- Never accept `account_id` from a public client as authoritative.
- Resolve hostname to `account_id` server-side.
- Apply `account_id` again in every query, tool call, upload path, and audit event.
- Do not share Studio authentication cookies across `*.laggente.com`.
- Do not permit tenant-controlled scripts or arbitrary HTML on personal subdomains.

## Local development

The canonical fallback is:

```text
http://localhost:3000/mauro
```

Subdomain behavior can additionally be tested with a loopback wildcard domain when useful, but the path fallback must remain available for previews and automated tests.

## Future custom domains

Customer-owned domains are outside the MVP. When introduced, add a verified `domains` mapping with ownership proof, certificate lifecycle, status, and audit events. Do not overload the professional slug table with unverified external hosts.

