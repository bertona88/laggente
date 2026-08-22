# ADR-0002: Wildcard Hostname-Based Tenancy with One Deployment

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Every professional needs a personal public space such as `mauro.laggente.com`. Activating that space must not require a new application deployment or dedicated infrastructure.

## Decision

Point wildcard DNS for `*.laggente.com` to the shared Hetzner server and route all professional hosts through the same application deployment.

The application extracts a normalized slug from the hostname, resolves it to an active professional space and `account_id`, and loads that space's active configuration revision.

The hostname is not a security boundary. Every tenant-owned query, tool call, file path, conversation, and audit event must independently enforce `account_id` server-side.

## Consequences

### Positive

- personal URLs are created by activating database-backed professional spaces;
- no DNS record or code deployment is required per professional;
- the user experience reinforces the digital branch office concept;
- the topology can later support many professionals without separate services.

### Negative

- wildcard TLS and DNS automation must be configured correctly;
- host-header validation and reserved slugs become security-sensitive;
- shared authentication cookies across the wildcard would be dangerous and must be avoided;
- tenant isolation requires explicit tests at every data boundary.

## Local and preview behavior

Maintain `laggente.com/<slug>` as a development and preview fallback. Test production hostname resolution separately using controlled host headers or a loopback wildcard domain.
