# ADR-0005: Automate Wildcard TLS Through Delegated ACME DNS

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

ADR-0002 requires wildcard hostname tenancy without DNS or application deployment per professional.
The initial pilot certificate covered only the apex, `www`, `app`, and `mauro`. Open professional
signup then proved the gap: a newly published tenant resolved through wildcard DNS and the application
but browsers rejected the hostname because the certificate lacked its name.

Let's Encrypt wildcard certificates require DNS-01. Namecheap's API credential can replace the
domain's complete record set and is not narrow enough to retain unattended on the shared VPS.
Manual DNS-01 would repair the current certificate but create a 90-day human renewal dependency.

## Decision

Delegate only `auth.laggente.com` to a pinned self-hosted `acme-dns` process on the existing Hetzner
server, and point `_acme-challenge.laggente.com` to one registered record beneath that zone.

- The authoritative DNS listener uses public TCP and UDP port 53 and serves only
  `auth.laggente.com`; it provides no recursion.
- The update API binds only to `127.0.0.1:5399`. Registration is enabled for initial setup, one
  credential limited to localhost is stored root-only, and registration is then disabled.
- The broad Namecheap credential remains off-server. A repository helper sends it through SSH stdin
  to a short-lived Hetzner-origin process only for the one-time full-record-preserving delegation.
- Certbot's root-owned auth hook can update only the registered TXT record. It issues and renews the
  separate `laggente-wildcard` lineage for `laggente.com` and `*.laggente.com`.
- The deploy hook tests nginx configuration before reload. The original named certificate remains a
  rollback lineage.
- The service uses a local SQLite database. A root-only closed-database registration snapshot is
  retained separately so the limited record can be restored without the Namecheap credential.

This service is certificate infrastructure, not a product AI role, tenant runtime, public API, or
per-professional deployment.

## Consequences

### Positive

- every valid professional slug receives browser-valid HTTPS immediately through one wildcard
  certificate;
- renewals are unattended without retaining broad DNS authority on the server;
- compromise of the Certbot hook credential is limited to issuing a certificate for the already
  delegated LAGGENTE names, an authority the server effectively has while holding the live key;
- Namecheap mail, application, and verification records remain outside the renewal path;
- nginx and application topology remain one shared deployment.

### Negative

- the shared host exposes a small authoritative DNS listener on TCP/UDP 53;
- wildcard renewal depends on the acme-dns process, delegated record, SQLite state, Certbot timer,
  and nginx deploy hook remaining healthy;
- the Hetzner Cloud firewall, external DNS delegation, and certificate renewal need operational
  monitoring in addition to ordinary HTTPS checks;
- the original named certificate continues to exist as rollback state until deliberately retired.

## Alternatives considered

- **Persist Namecheap API credentials on the VPS:** rejected because they can replace the complete
  domain record set and exceed the authority required for certificate renewal.
- **Issue a manual wildcard certificate:** rejected because unattended renewal would remain broken.
- **Expand one HTTP-01 SAN certificate for every signup:** rejected because publication would race a
  privileged provisioning job and eventually encounter certificate name and issuance limits.
- **Move authoritative DNS to another managed provider:** rejected because wildcard TLS does not
  justify a broader DNS-provider migration during the pilot.
- **Run a third-party public acme-dns service:** rejected because the delegated service can issue
  certificates for LAGGENTE; the existing controlled server is the smaller trust boundary.
