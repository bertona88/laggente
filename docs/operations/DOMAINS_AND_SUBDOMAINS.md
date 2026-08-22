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

## Initial pilot TLS

DNS may remain wildcard-routed, but the first deployed pilot uses a named SAN certificate covering only the hosts that are live:

```text
laggente.com
www.laggente.com
app.laggente.com
mauro.laggente.com
```

This avoids storing a broad Namecheap API credential on the server and renews through ordinary HTTP-01. Install the temporary challenge vhost, issue the certificate, then replace it with the full site:

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

The host nginx template expects:

```text
/etc/letsencrypt/live/laggente.com/fullchain.pem
/etc/letsencrypt/live/laggente.com/privkey.pem
```

When enabling the full site, remove only the temporary site symlink before the syntax check and reload:

```bash
sudo install -m 0644 \
  /opt/laggente/repo/infra/nginx/laggente.conf \
  /etc/nginx/sites-available/laggente.conf
sudo ln -sfn /etc/nginx/sites-available/laggente.conf \
  /etc/nginx/sites-enabled/laggente.conf
sudo unlink /etc/nginx/sites-enabled/laggente-http-bootstrap.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run
```

Do not activate another professional hostname until TLS covers it. A small named pilot can expand the SAN lineage deliberately. The target remains a wildcard certificate once renewal can be automated safely.

## Wildcard TLS plan

A wildcard certificate must cover both `laggente.com` and `*.laggente.com` and requires DNS-01. The Namecheap-compatible controlled procedure is:

1. Start Certbot's manual DNS challenge for the apex and wildcard.
2. Use the `namecheap-dns` helper through the stable Hetzner-origin workflow to add every exact `_acme-challenge` TXT value while preserving the complete host set.
3. Confirm the TXT values through public DNS, finish issuance, then remove only those challenge values.
4. Install the resulting lineage at the same `/etc/letsencrypt/live/laggente.com/` paths used by nginx.

Manual DNS certificates do not renew unattended without a hook. Do not replace the auto-renewing named pilot certificate until either a reviewed hook can use Namecheap credentials through an approved secret mechanism or `_acme-challenge` is delegated to DNS with a narrowly scoped renewal credential. The upstream `acme.sh` project has a Namecheap hook, but it re-submits the complete record set and normally persists account credentials; adopting it is a separate security decision.

## Host nginx activation

After the certificate exists and the Compose gateway is healthy on loopback:

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
- `/mauro...` on any production host except `mauro.laggente.com` redirects to Mauro's host.

These redirects retain query arguments for navigation compatibility, while both nginx access-log
formats continue to record only normalized `$uri` and never the arguments. Client routing remains a
defense-in-depth fallback; it must not be the first mechanism that moves a Studio cookie or visitor
continuation journey onto its canonical host.

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
```

Unknown, inactive, reserved, malformed, or multi-level hosts return a safe response. The professional Studio cookie is host-only for `app.laggente.com`; it is never scoped to `.laggente.com`.

## Verification

```bash
curl -I https://laggente.com/
curl -I https://www.laggente.com/
curl -I https://app.laggente.com/
curl -I https://mauro.laggente.com/
curl -I 'https://laggente.com/studio?source=verification'
curl -I 'https://app.laggente.com/mauro?source=verification'
curl --insecure -I https://does-not-exist.laggente.com/

openssl s_client -connect laggente.com:443 -servername mauro.laggente.com </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -ext subjectAltName
```

Expected outcomes:

- apex, Studio, and Mauro hosts have valid HTTPS;
- `www` redirects permanently to `https://laggente.com`;
- canonical Studio and Mauro path redirects land on `app.laggente.com` and `mauro.laggente.com`
  respectively while retaining the verification query argument;
- the initial certificate includes the apex, `www`, `app`, and `mauro` SANs; after wildcard cutover it includes `DNS:*.laggente.com` and the apex SAN;
- an unknown slug never falls into another nginx site or resolves tenant data; before wildcard TLS, its certificate mismatch prevents ordinary browser navigation;
- no LAGGENTE container service is publicly reachable on `5432`, `8000`, or `45200`; the container
  gateway binds `45200` on host loopback only.

## Local and preview behavior

The canonical local fallback remains:

```text
http://localhost:3000/mauro
```

That port is the pinned Vite development server, not a production container port. The optional
built-artifact preview uses Vite's local preview port; production static files are served directly
by the internal nginx gateway.

Use controlled `Host` headers against the loopback gateway for proxy diagnostics. Do not use a client-supplied `account_id` as a substitute for hostname-to-space resolution.
