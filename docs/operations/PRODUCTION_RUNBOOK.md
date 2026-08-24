# Production Runbook

## Operator context

Connect as the dedicated user and let the scripts select the rootless Docker socket:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes -o ConnectTimeout=8 laggente@116.203.123.0
cd /opt/laggente/repo
current_env=/opt/laggente/releases/current.env
```

Do not use root for ordinary Compose work. Use root only for host nginx, Certbot, package, firewall, or filesystem administration.

## Healthy baseline

```bash
./scripts/audit-production.sh
docker compose --env-file "$current_env" ps
docker compose --env-file "$current_env" logs --tail 100 gateway api db backup
curl -fsS -H 'Host: laggente.com' http://127.0.0.1:45200/api/health
curl -fsS -H 'Host: laggente.com' http://127.0.0.1:45200/api/readyz
```

Expected:

- `db`, `api`, `gateway`, and `backup` are running and healthy;
- gateway health proves that nginx can serve the built SPA entry file; API readiness is checked
  independently;
- only the gateway publishes a host port, exactly `127.0.0.1:45200`;
- liveness and readiness return HTTP 200;
- the most recent backup checksum passes;
- disk and memory have operating margin;
- public apex, Studio, and Mauro hosts respond over valid HTTPS.
- `acme-dns.service` and `certbot.timer` are active, public delegation resolves, and the active
  certificate contains both `laggente.com` and `*.laggente.com`.

The public `/api/health`, `/api/healthz`, and `/api/readyz` routes use the existing modest API rate
zone; readiness reaches PostgreSQL and is not an unbounded public probe. Container and deployment
health checks use the loopback gateway directly, so this host-edge limit does not destabilize local
Compose health.

## Before opening professional signup or sending an invitation

The entry UI is not a TLS readiness check. Before enabling live signup or sending an invitation:

- confirm `RESEND_API_KEY` and `FROM_EMAIL` are configured and a delivery smoke has succeeded;
- confirm the signup-link migration is applied and expired pre-tenant proofs are being pruned;
- for curated invitations, confirm the operator session reports invitation permission;
- confirm wildcard DNS resolves a proposed slug to `116.203.123.0`;
- confirm the active certificate covers `*.laggente.com`;
- verify a controlled non-Mauro host reaches the shared gateway without resolving another tenant.

Do not publish a new slug merely because the database flow succeeds. A missing wildcard SAN means
the open signup release is operationally incomplete even when application routing is correct.

## Read logs without leaking secrets

```bash
docker compose --env-file "$current_env" logs --since 30m api gateway
docker compose --env-file "$current_env" logs --since 2h db backup
journalctl --user -u docker.service --since '30 min ago' --no-pager
```

The host and gateway access logs are structured and intentionally omit query strings and referers. They retain the request ID, client address, host, method, normalized path, protocol, status, byte count, and timing. Per-site and gateway error logs use `crit` because ordinary nginx limit/upstream errors can include the raw query-bearing request line. A token appearing in either nginx log is a security incident; preserve a redacted evidence sample and investigate configuration drift. Media content is cookie-authorized and login tokens are delivered in URL fragments; do not introduce bearer credentials in query strings.

The API hides SQL bind parameters in application exceptions, and PostgreSQL keeps
`log_parameter_max_length=0` so slow-statement logs cannot include private message, memory, or
configuration values. Do not relax either control while inspecting latency.

Never run `docker inspect` with unfiltered environment output in a shared screen or paste full container configuration into chat. Never print `/opt/laggente/secrets/database.env` or `/opt/laggente/secrets/application.env`.

To verify required secret names without values:

```bash
for secret_file in \
  /opt/laggente/secrets/database.env \
  /opt/laggente/secrets/application.env
do
  stat -c '%U:%G %a %n' "$secret_file"
  awk -F= '/^[A-Z][A-Z0-9_]*=/ {print $1 "=[redacted]"}' "$secret_file"
done
```

Both files must report `root:laggente 640`. The database file is visible only to `db`, `migrate`, `api`, and `backup`; the application file is visible only to `api`; the static gateway receives neither. `audit-production.sh` also verifies the exact production environment, base domain, Studio origin, CORS origin, trusted-host set, secure-cookie flag, and disabled runtime schema creation. Do not weaken one field to work around a hostname or browser problem; diagnose the canonical routing or source-env generation instead.

## Service-specific diagnosis

### API unhealthy

```bash
docker compose --env-file "$current_env" logs --tail 200 api
docker compose --env-file "$current_env" exec -T api \
  python -c "import urllib.request; r=urllib.request.Request('http://127.0.0.1:8000/healthz',headers={'Host':'laggente.com'}); print(urllib.request.urlopen(r).status)"
docker compose --env-file "$current_env" exec -T api \
  python -c "import urllib.request; r=urllib.request.Request('http://127.0.0.1:8000/readyz',headers={'Host':'laggente.com'}); print(urllib.request.urlopen(r).status)"
docker compose --env-file "$current_env" exec -T db \
  sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Do not rerun migrations until the failure is understood and a pre-migration backup exists.

### Static UI or gateway unhealthy

```bash
docker compose --env-file "$current_env" logs --tail 200 gateway
docker compose --env-file "$current_env" exec -T gateway \
  wget -q --header 'Host: laggente.com' -O /dev/null \
  http://127.0.0.1:8080/_gateway_health
curl -v -H 'Host: laggente.com' http://127.0.0.1:45200/api/health
```

`/_gateway_health` verifies that nginx can read the compiled `index.html`; `/api/health` verifies
the FastAPI proxy separately. A missing deep route with a valid client path should return the SPA
entry file, while a missing fingerprinted `/assets/...` file and every unknown `/api/...` path must
return 404 rather than the SPA. Exact `/api/v1` is also an API request and currently returns
FastAPI's JSON 404; a 200 HTML shell at either API check indicates route-boundary regression.

If loopback works but HTTPS fails, diagnose host nginx, DNS, and TLS without restarting application containers:

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
sudo journalctl -u nginx --since '30 min ago' --no-pager
sudo certbot certificates
sudo systemctl status acme-dns certbot.timer --no-pager
dig +short A auth.laggente.com @1.1.1.1
dig +short NS auth.laggente.com @1.1.1.1
dig +short CNAME _acme-challenge.laggente.com @1.1.1.1
dig +short A laggente.com
dig +short A mauro.laggente.com
```

Run `systemctl reload nginx` only after `nginx -t` succeeds and a host-config change actually requires it.

### Wildcard renewal unhealthy

The Namecheap account credential is not part of renewal and must not be copied to the server. Check
the narrowly delegated path instead:

```bash
sudo systemctl status acme-dns --no-pager
sudo journalctl -u acme-dns --since '30 min ago' --no-pager
curl -fsS http://127.0.0.1:5399/health
sudo stat -c '%U:%G %a %n' /etc/letsencrypt/laggente-acme-dns.json
sudo certbot renew --dry-run --cert-name laggente-wildcard
```

Expected credential ownership is `root:root 600`; never print the file. The registration endpoint
must remain disabled. If the SQLite database is damaged, stop `acme-dns.service`, restore
`/var/backups/laggente-acme-dns/registration.db` to `/var/lib/acme-dns/acme-dns.db` with owner and
group `acme_dns`, mode `600`, restart the service, and repeat the public DNS plus dry-run checks.
Do not change the `_acme-challenge` CNAME or use the broad Namecheap credential unless the limited
registration itself must be deliberately replaced.

### Backup unhealthy

```bash
docker compose --env-file "$current_env" logs --tail 200 backup
./scripts/backup-now.sh
backup_id=$(docker compose --env-file "$current_env" exec -T backup \
  /opt/backup/backup.sh latest)
./scripts/verify-backup-restore.sh "$backup_id"
```

Do not prune backups to make a failed backup appear healthy. Diagnose capacity, credentials, database readiness, permissions, and checksum errors.

The database dump and upload archive are captured sequentially while the application can still
accept writes. Do not deliberately delete or manually purge attachments while a backup is running.
The API's automatic six-hour retention cycle can theoretically overlap this capture; that is part
of the controlled-pilot cross-store caveat until writer quiescence or reconciliation is implemented. A normal
completed set proves each payload is readable and intact, but it does not prove that database rows
and upload files came from one atomic application snapshot. Before claiming complete attachment
consistency, either quiesce all application writers for the backup or produce and verify a
database-to-archive reconciliation manifest. See [Backup and Restore](BACKUP_AND_RESTORE.md).

## Controlled restart

A restart is a change, not a diagnostic. After identifying a service-local transient failure:

```bash
docker compose --env-file "$current_env" restart api
docker compose --env-file "$current_env" ps api
docker compose --env-file "$current_env" logs --since 5m api
```

Restart only the affected LAGGENTE service. Never restart host PostgreSQL, WOFI services, or nginx to repair an application-container issue.

## Capacity response

```bash
free -h
df -h / /opt/laggente/data
sudo du -sh /opt/laggente/data/postgres \
  /opt/laggente/data/uploads \
  /opt/laggente/data/backups \
  /opt/laggente/data/docker
docker system df
```

Treat root disk above 85%, less than 2 GiB free before a build, repeated kernel OOM events, or less than 512 MiB available memory at idle as an operational warning. Report exact image, build-cache, backup, upload, and database sizes before proposing cleanup. Do not run `docker system prune`, remove another project's files, or delete backups automatically.

The application ceilings operators should expect are:

- 512 MiB of durable image data per account and 50 MiB per conversation;
- 20 attachment records per conversation;
- 12 audio transcriptions per account in a rolling hour;
- one hour for a visitor to bind an uploaded photograph or corrected transcript before an
  abandoned draft is reclaimed;
- 60 model-backed public turns and 60 new public conversations per space in a rolling hour;
- at most 60 unengaged conversations per space, with one-hour expiry before pruning on a later
  creation attempt unless a visitor/professional has written, the professional has joined, or an
  attachment has been bound to a durable message;
- Studio inbox pages of up to 100 public conversations, with older pages reachable from the UI;
- automatic application of `CONVERSATION_RETENTION_DAYS` after a five-minute startup grace and
  every six hours thereafter.

The inbox value is a bounded page, not evidence that older conversations were deleted. Retention
cycle failures appear in API logs and retry at the next interval. Do not
raise a ceiling or manually purge data as an incident shortcut. First distinguish an expected HTTP
429 or storage conflict from disk pressure, inspect tenant-scoped usage without exposing private
content, and review any capacity change against the shared host and backup amplification.

## Release and rollback

Application releases pull only the immutable API, gateway, and backup images recorded in their
release metadata. They do not refresh the mutable PostgreSQL or data-init base tags as a side
effect. Treat a foundation-image upgrade as a separate maintenance operation with an explicit
backup, version review, and restore path.

Use only the encoded paths:

```bash
./scripts/deploy-production.sh --help
./scripts/rollback-production.sh PREVIOUS_RELEASE_ID
```

The release script owns migration ordering, health gates, release pointers, and application-image fallback. Do not improvise `docker compose up --build` in production because it loses release identity and rollback evidence.

## Incident evidence

Record:

- UTC start and end time;
- affected host and user journey;
- active release ID and full Git SHA from `/opt/laggente/releases/current.env` (never secret env values);
- container health and relevant redacted log lines;
- whether data writes continued;
- backup ID and restore-rehearsal status;
- exact action taken and acceptance checks;
- unresolved follow-up.

Container health, public HTTP health, browser journey acceptance, and human product/taste acceptance are separate facts.
