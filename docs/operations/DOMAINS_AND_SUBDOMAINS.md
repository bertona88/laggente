# Domains and Subdomains

## Host map

All hosts resolve to the single LAGGENTE deployment on the existing Hetzner IPv4 `116.203.123.0`.

| Host | Purpose |
| --- | --- |
| `laggente.com` | Canonical brand and entry surface |
| `www.laggente.com` | Permanent redirect to the apex |
| `app.laggente.com` | Private Studio and professional workspace |
| `mauro.laggente.com` | Mauro's public conversational space |
| `<slug>.laggente.com` | Any active professional space |

The same-origin `/api/v1` path reaches the FastAPI service through the reverse proxies. There is no public API subdomain and no deployment per professional.

## Required Namecheap records

| Host | Type | Value | TTL |
| --- | --- | --- | --- |
| `@` | `A` | `116.203.123.0` | `300` during launch |
| `www` | `CNAME` | `@` | `300` during launch |
| `app` | `A` | `116.203.123.0` | `300` during launch |
| `*` | `A` | `116.203.123.0` | `300` during launch |
| `auth` | `A` | `116.203.123.0` | `300` |
| `auth` | `NS` | `auth.laggente.com.` | `300` |
| `_acme-challenge` | `CNAME` | Registered target under `auth.laggente.com.` | `300` |

Before writing, use the `namecheap-dns` helper to fetch and preserve the complete existing record set. Namecheap's `setHosts` operation replaces the whole set, so never issue a hand-written partial API request. Do not alter unrelated `MX`, `TXT`, `CAA`, or verification records.

From the installed skill directory, the controlled sequence is:

```bash
cd /Users/andreabertoncini/.codex/skills/namecheap-dns
python3 scripts/namecheap_dns.py list laggente.com

python3 scripts/namecheap_dns.py add-website laggente.com \
  --ip 116.203.123.0 --www cname --ttl 300 --dry-run
python3 scripts/namecheap_dns.py add-website laggente.com \
  --ip 116.203.123.0 --www cname --ttl 300

python3 scripts/namecheap_dns.py add-record laggente.com \
  --type A --host app --value 116.203.123.0 --ttl 300 --dry-run
python3 scripts/namecheap_dns.py add-record laggente.com \
  --type A --host app --value 116.203.123.0 --ttl 300

python3 scripts/namecheap_dns.py add-record laggente.com \
  --type A --host '*' --value 116.203.123.0 --ttl 300 --dry-run
python3 scripts/namecheap_dns.py add-record laggente.com \
  --type A --host '*' --value 116.203.123.0 --ttl 300

python3 scripts/namecheap_dns.py list laggente.com
```

Namecheap API calls must originate from an IP allowlisted on the account. The stable approved origin is the Hetzner IPv4 `116.203.123.0`; if a local call reports `Invalid request IP`, use the skill's controlled Hetzner-origin workflow. Keep Namecheap credentials ephemeral and out of the VPS filesystem and logs.

Verify authoritative and public DNS before requesting TLS:

```bash
dig +short A laggente.com
dig +short CNAME www.laggente.com
dig +short A app.laggente.com
dig +short A mauro.laggente.com
```

Every `A` query above should ultimately resolve to `116.203.123.0`. DNS readiness does not prove that nginx or the application is ready.

## Retained named-certificate rollback

The first deployed pilot used a named SAN certificate covering only these hosts:

```text
laggente.com
www.laggente.com
app.laggente.com
mauro.laggente.com
```

That `laggente.com` lineage remains on the server as a rollback certificate and renews through
ordinary HTTP-01. It is no longer the active nginx lineage because it cannot cover a new
professional hostname. Do not add every new signup to this certificate.

The historical issuance procedure was:

```bash
sudo install -d -m 0755 /var/www/letsencrypt/.well-known/acme-challenge
sudo install -m 0644 \
  /opt/laggente/repo/infra/nginx/laggente-http-bootstrap.conf \
  /etc/nginx/sites-available/laggente-http-bootstrap.conf
sudo ln -sfn /etc/nginx/sites-available/laggente-http-bootstrap.conf \
  /etc/nginx/sites-enabled/laggente-http-bootstrap.conf
sudo nginx -t
sudo systemctl reload nginx

sudo certbot certonly \
  --webroot \
  --webroot-path /var/www/letsencrypt \
  --cert-name laggente.com \
  -d laggente.com \
  -d www.laggente.com \
  -d app.laggente.com \
  -d mauro.laggente.com
```

The normal `certbot.timer` can renew this HTTP-01 lineage without a DNS credential as long as the challenge webroot remains reachable. The full HTTPS template includes an HTTP-to-HTTPS redirect, and Certbot follows the same registered webroot during renewal.

The active host nginx template now expects:

```text
/etc/letsencrypt/live/laggente-wildcard/fullchain.pem
/etc/letsencrypt/live/laggente-wildcard/privkey.pem
```

## Automated wildcard TLS

The active certificate covers both `laggente.com` and `*.laggente.com`. DNS-01 is automated without
placing the broad Namecheap API credential on the VPS:

```text
Namecheap zone
  auth.laggente.com A  116.203.123.0
  auth.laggente.com NS auth.laggente.com.
  _acme-challenge CNAME <limited-id>.auth.laggente.com.

public TCP/UDP 53
  self-hosted acme-dns authoritative only for auth.laggente.com

127.0.0.1:5399
  registration-disabled acme-dns update API

Certbot manual-auth hook
  one root-owned credential that can update only <limited-id>.auth.laggente.com TXT
```

The limited credential can answer LAGGENTE's ACME challenge but cannot alter apex, mail, application,
or verification records. The Namecheap credential stays local and crosses SSH stdin only during the
one-time delegation update.

Install the pinned service and register its limited record:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes root@116.203.123.0 \
  'cd /opt/laggente/repo && ./scripts/install-acme-dns.sh'
```

Copy the printed public CNAME target, dry-run the full-record Namecheap update, then apply it. The
helper reads the local credential file, performs the API call from the allowlisted Hetzner origin,
and never writes or prints the credential:

```bash
./scripts/configure-namecheap-acme-delegation.py \
  --env /Users/andreabertoncini/.codex/skills/namecheap-dns/assets/namecheap.env \
  --ssh-key /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  --fulldomain LIMITED_ID.auth.laggente.com

./scripts/configure-namecheap-acme-delegation.py \
  --env /Users/andreabertoncini/.codex/skills/namecheap-dns/assets/namecheap.env \
  --ssh-key /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  --fulldomain LIMITED_ID.auth.laggente.com \
  --apply
```

Verify delegation from a public recursive resolver before issuance:

```bash
dig +short A auth.laggente.com @1.1.1.1
dig +short NS auth.laggente.com @1.1.1.1
dig +short CNAME _acme-challenge.laggente.com @1.1.1.1
```

Then issue the separate rollback-safe wildcard lineage and prove unattended renewal:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes root@116.203.123.0 \
  'cd /opt/laggente/repo && ./scripts/issue-wildcard-certificate.sh'
```

The ordinary `certbot.timer` reuses the stored manual-auth and deploy hooks. On successful renewal,
the deploy hook runs `nginx -t` before reloading nginx. The acme-dns registration endpoint remains
disabled, its update API is loopback-only, and `/var/backups/laggente-acme-dns/registration.db`
retains a root-only closed-database snapshot of the limited registration state.

The application can now create, configure, and publish a verified tenant without a DNS write,
certificate change, or application deployment per professional. A successful database activation
still does not prove TLS readiness by itself; the production audit and smoke checks enforce the
wildcard SAN.

## Host nginx activation

After the wildcard certificate exists and the Compose gateway is healthy on loopback:

```bash
sudo install -m 0644 \
  /opt/laggente/repo/infra/nginx/laggente.conf \
  /etc/nginx/sites-available/laggente.conf
sudo ln -sfn /etc/nginx/sites-available/laggente.conf \
  /etc/nginx/sites-enabled/laggente.conf
sudo nginx -t
sudo systemctl reload nginx
```

The host front door preserves the original hostname. The container gateway independently rejects malformed or multi-level hosts. The application then resolves a valid single-label slug to an active `space_id` and `account_id`; hostname parsing never replaces authorization.

Before serving the SPA, the container gateway also enforces the cookie-owning canonical hosts:

- `app.laggente.com/` redirects to `app.laggente.com/studio`;
- `/login` and `/studio...` on the apex or `www` redirect to `app.laggente.com`;
- `/<valid-slug>...` on the apex, `www`, or Studio host redirects generically to
  `<valid-slug>.laggente.com`, excluding reserved product paths.

These redirects retain query arguments for navigation compatibility, while both nginx access-log
formats continue to record only normalized `$uri` and never the arguments. Client routing remains a
defense-in-depth fallback; it must not be the first mechanism that moves a Studio cookie or visitor
continuation journey onto its canonical host.

## Search indexing policy

The brand apex homepage is the only crawl target during the pilot. It serves a small sitemap
containing only `https://laggente.com/` and a real `robots.txt`. Every other apex SPA route, the
Studio, and every professional subdomain emit `X-Robots-Tag: noindex, nofollow`. This prevents bare
slug previews and soft-not-found SPA routes from becoming alternate indexable tenant URLs. A tenant
space becomes indexable only after the professional has explicitly opted in and the product can
serve truthful, unique metadata for that hostname; activating a space is not itself search-indexing
consent.

This keeps the public brand discoverable for focused phrases such as “assistente AI per agenti
immobiliari” without turning pilot identities, private application routes, or thin generated pages
into an SEO surface.

## Slug rules

- lowercase ASCII letters, digits, and single hyphens;
- unique at the database level;
- cannot begin or end with a hyphen;
- immutable or deliberately migrated after publication;
- resolved publicly only for an active professional space.

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
studio
login
privacy
terms
spazio
static
assets
blog
```

Unknown, inactive, reserved, malformed, or multi-level hosts return a safe response. The professional Studio cookie is host-only for `app.laggente.com`; it is never scoped to `.laggente.com`.

## Verification

```bash
curl -I https://laggente.com/
curl -I https://www.laggente.com/
curl -I https://app.laggente.com/
curl -I https://mauro.laggente.com/
secondary_slug=REPLACE_WITH_ACTIVE_SLUG
curl -I "https://$secondary_slug.laggente.com/"
curl -I 'https://laggente.com/studio?source=verification'
curl -I 'https://app.laggente.com/giulia?source=verification'
curl --insecure -I https://does-not-exist.laggente.com/

openssl s_client -connect laggente.com:443 -servername tls-probe.laggente.com </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -ext subjectAltName
```

Expected outcomes:

- apex, Studio, and Mauro hosts have valid HTTPS;
- `www` redirects permanently to `https://laggente.com`;
- canonical Studio and generic professional paths land on `app.laggente.com` and the slug-owned
  professional host respectively while retaining the verification query argument;
- the active certificate includes the apex SAN and `DNS:*.laggente.com`;
- a controlled published non-Mauro hostname and every other valid single-label professional hostname receive valid HTTPS;
- an unknown slug receives valid edge TLS but never resolves tenant data or falls into another nginx site;
- no LAGGENTE container service is publicly reachable on `5432`, `8000`, or `45200`; the container
  gateway binds `45200` on host loopback only;
- public TCP/UDP `53` serves only the delegated `auth.laggente.com` challenge zone; its update API
  remains bound to `127.0.0.1:5399`.

## Local and preview behavior

The canonical local fallback remains:

```text
http://localhost:3000/mauro
http://localhost:3000/giulia
```

That port is the pinned Vite development server, not a production container port. The optional
built-artifact preview uses Vite's local preview port; production static files are served directly
by the internal nginx gateway.

Use controlled `Host` headers against the loopback gateway for proxy diagnostics. Do not use a client-supplied `account_id` as a substitute for hostname-to-space resolution.
