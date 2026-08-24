# Hetzner Deployment

## Production contract

LAGGENTE runs on the existing Hetzner `CX23` at `116.203.123.0`. The host is a shared production machine: existing WOFI, blog, PostgreSQL, nginx, and certbot services remain outside LAGGENTE and must not be restarted or reconfigured as a side effect of an application release.

The LAGGENTE boundary is:

```text
internet :80/:443
        ↓
existing host nginx + TLS
        ↓
127.0.0.1:45200 only
        ↓
container nginx gateway
  ├── Vite/React static assets
  └── /api/v1 → api:8000 ── db:5432
                              ↑
                            backup
```

Only `127.0.0.1:45200` is published by Compose. The API and LAGGENTE PostgreSQL ports are not
published. The Vite compiler runs only while the gateway image is built; nginx serves the resulting
static files and proxies same-origin API requests at runtime. The existing host PostgreSQL on
localhost is unrelated; the container database is reachable only on the Compose network.

Wildcard certificate renewal also uses one host-level `acme-dns.service`. It is authoritative only
for the delegated `auth.laggente.com` zone on public TCP/UDP 53, while its update API remains on
`127.0.0.1:5399`. It is certificate infrastructure, not an application container or AI role.

The API container healthcheck connects over its own loopback address but deliberately sends
`Host: laggente.com`, which is inside the exact production `TRUSTED_HOSTS` contract. Do not solve an
internal healthcheck failure by admitting `127.0.0.1`, `*`, or arbitrary container names as trusted
public hosts.

Persistent application state lives under `/opt/laggente/data`. Secrets are split between `/opt/laggente/secrets/database.env` and `/opt/laggente/secrets/application.env`, outside Git and outside Docker build contexts. PostgreSQL, migrations, and backup receive only the database file; the API receives both; the gateway receives neither.

## Current host assumptions

The read-only preflight on 2026-08-22 found 2 vCPU, 3.7 GiB RAM, no swap, about 2.1 GiB memory available, and about 9.8 GiB disk free. Those are a snapshot, not a guarantee. Recheck before every first install or unusually large release:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes -o ConnectTimeout=8 root@116.203.123.0 \
  'hostname; uptime; free -h; df -h /; ss -ltn'
```

Do not run concurrent image builds on this host. The initial `--build-on-host` path serializes builds with `COMPOSE_PARALLEL_LIMIT=1`. If a build is killed for measured memory pressure, stop and either build immutable images elsewhere or add temporary swap as an explicit, monitored operational action; do not assume swap is required in advance.

Do not treat the preflight's free-space snapshot as long-term capacity. A single account at the
512 MiB durable-image ceiling represents about 7 GiB of upload payload across 14 full local backup
sets, before live data, PostgreSQL dumps, images, build cache, and additional accounts. Provider
backups or an independently controlled off-host copy must still be enabled and sized for the
retention policy. See [Backup and Restore](BACKUP_AND_RESTORE.md).

## Repository-side assets

| Path | Purpose |
| --- | --- |
| `compose.yaml` | Hardened, resource-limited production topology |
| `infra/gateway/` | Non-root nginx static runtime and internal `/api/v1` gateway |
| `infra/backup/` | Logical database and private-upload backup job |
| `infra/nginx/laggente.conf` | Existing host nginx site template |
| `infra/acme-dns/` | Limited DNS service, systemd unit, and Certbot hooks for wildcard renewal |
| `infra/secrets/database.env.example` | Database-only production secret template |
| `infra/secrets/application.env.example` | API-only application secret template |
| `scripts/generate-production-env.sh` | Generate new split files or safely split the legacy combined local file |
| `scripts/validate-infrastructure.sh` | Validate shell, secret boundaries, Compose, gateway build, SPA fallback, and canonical redirects |
| `scripts/bootstrap-server.sh` | Idempotent user, directory, Docker Engine, and Compose bootstrap |
| `scripts/deploy-production.sh` | Migration-aware release with automatic application-image rollback |
| `scripts/rollback-production.sh` | Explicit application rollback without database rewind |
| `scripts/audit-production.sh` | Read-only topology, capacity, backup, and endpoint audit |
| `scripts/smoke-production.sh` | Public static-shell, module-asset, API-boundary/metadata, redirect, and security-header smoke checks |

Docker is installed from Docker's official apt repository with the Compose plugin, following the [official Ubuntu installation procedure](https://docs.docker.com/engine/install/ubuntu/). The bootstrap uses a rootless daemon owned by the dedicated `laggente` user so Docker access does not grant that account a rootful host daemon socket. Rootless requirements and systemd behavior follow [Docker's rootless-mode documentation](https://docs.docker.com/engine/security/rootless/). On Ubuntu 24.04 the bootstrap also installs `slirp4netns` and pins RootlessKit to `slirp4netns` with its `builtin` port driver through a user-systemd drop-in. Do not remove that explicit selection: the Docker 29 automatic fallback used when no external userspace backend is installed failed the loopback publication gate on this host and is not part of this deployment contract. Bootstrap verifies both the running RootlessKit arguments and an actual `127.0.0.1` port forward before it succeeds.

## 1. Prepare an exact source snapshot

Do this only from a clean, committed, pushed feature/release commit. The archive makes the transferred source exactly match the selected commit and cannot include `.env.local`.

```bash
cd /Users/andreabertoncini/laggente
release_sha=$(git rev-parse HEAD)
release_branch=$(git branch --show-current)
git diff --quiet
git diff --cached --quiet
remote_sha=$(git ls-remote origin "refs/heads/$release_branch" | awk '{print $1}')
test "$remote_sha" = "$release_sha"

release_stage=$(mktemp -d)
git archive "$release_sha" | tar -x -C "$release_stage"
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes root@116.203.123.0 \
  'install -d -m 0755 /opt/laggente/repo'
rsync -az --delete \
  -e 'ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 -o BatchMode=yes' \
  "$release_stage/" root@116.203.123.0:/opt/laggente/repo/

ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes root@116.203.123.0 \
  'chown -R laggente:laggente /opt/laggente/repo && chmod 0750 /opt/laggente/repo'

rsync -rlnci --delete \
  -e 'ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 -o BatchMode=yes' \
  "$release_stage/" root@116.203.123.0:/opt/laggente/repo/
```

`--delete` is intentionally scoped to `/opt/laggente/repo/`. It never targets `/opt/laggente/data`,
`/opt/laggente/secrets`, or another deployed project. The explicit ownership repair is required
because `mktemp` creates the local staging root with mode `0700` and archive-mode rsync can preserve
that root mode or the local numeric owner on a root receiver. The checksum dry run deliberately
ignores the corrected server ownership metadata and must produce no itemized content changes.
Remove the local staging directory after that exact-tree verification.

## 2. Bootstrap the server

Run once, as root, from the transferred exact source:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes root@116.203.123.0
cd /opt/laggente/repo
chmod 0755 scripts/*.sh infra/backup/*.sh
./scripts/bootstrap-server.sh \
  --authorized-keys-source /root/.ssh/authorized_keys \
  --loopback-port 45200
```

The script:

- refuses a non-Ubuntu-24.04 host or an occupied port `45200`;
- creates the dedicated `laggente` login and copies only the selected public SSH authorization;
- installs Docker Engine, Buildx, Compose, Ubuntu's `slirp4netns`, and the other rootless prerequisites;
- refuses to disable a rootful Docker daemon if it contains any container;
- installs an idempotent user-systemd drop-in selecting `slirp4netns` plus the `builtin` port driver;
- enables or safely restarts the rootless Docker user service with systemd lingering and proves a
  loopback-only container port is reachable;
- creates `/opt/laggente/{repo,releases,data,secrets}` with restricted ownership;
- leaves nginx, DNS, TLS, firewall, WOFI, and every existing service unchanged.

Verify:

```bash
deploy_uid=$(id -u laggente)
sudo -u laggente env \
  XDG_RUNTIME_DIR="/run/user/$deploy_uid" \
  DOCKER_HOST="unix:///run/user/$deploy_uid/docker.sock" \
  docker info
sudo -u laggente env \
  XDG_RUNTIME_DIR="/run/user/$deploy_uid" \
  DOCKER_HOST="unix:///run/user/$deploy_uid/docker.sock" \
  docker compose version
sudo -u laggente env XDG_RUNTIME_DIR="/run/user/$deploy_uid" \
  systemctl --user show docker.service -p Environment --value
ps -u laggente -o args= | grep 'rootlesskit .*--net=slirp4netns.*--port-driver=builtin'
```

The systemd environment must include
`DOCKERD_ROOTLESS_ROOTLESSKIT_NET=slirp4netns` and
`DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=builtin`; the process check must return the running
RootlessKit parent and child. A missing published port is a failed rootless networking gate, not a
reason to weaken the gateway bind or skip infrastructure validation.

## 3. Populate production secrets

The bootstrap creates two placeholder files only when their destinations do not already exist. Generate the real local transfer artifacts without printing values. For the current rollout, split the already-created combined local file so no credential is rotated:

```bash
cd /Users/andreabertoncini/laggente
./scripts/generate-production-env.sh --source-env .env.production.local
```

This creates `.env.database.production.local` and `.env.application.production.local`, both mode `0600` and ignored by Git and Docker builds. If there is no existing combined file, generate new credentials from the dedicated project key instead:

```bash
./scripts/generate-production-env.sh \
  --key-file .env.local \
  --pilot-email 'REPLACE_WITH_MAURO_EMAIL'
```

Transfer each artifact through SSH standard input. Secret values never appear in the command line, shell history, or rsync arguments, and the remote replacement is atomic:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes -o ConnectTimeout=8 root@116.203.123.0 \
  'set -eu
   incoming=$(mktemp /opt/laggente/secrets/.database.env.XXXXXX)
   cleanup() { rm -f -- "$incoming"; }
   trap cleanup EXIT HUP INT TERM
   cat >"$incoming"
   chown root:laggente "$incoming"
   chmod 0640 "$incoming"
   mv -f "$incoming" /opt/laggente/secrets/database.env
   trap - EXIT HUP INT TERM' \
  < .env.database.production.local

ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes -o ConnectTimeout=8 root@116.203.123.0 \
  'set -eu
   incoming=$(mktemp /opt/laggente/secrets/.application.env.XXXXXX)
   cleanup() { rm -f -- "$incoming"; }
   trap cleanup EXIT HUP INT TERM
   cat >"$incoming"
   chown root:laggente "$incoming"
   chmod 0640 "$incoming"
   mv -f "$incoming" /opt/laggente/secrets/application.env
   trap - EXIT HUP INT TERM' \
  < .env.application.production.local
```

The database file contains only `POSTGRES_*` and `DATABASE_URL`. The application file contains session, host, pilot-auth, OpenAI, optional Resend, upload, conversation-retention, and privacy-notice settings. The generator normalizes the security-relevant production contract to `APP_ENV=production`, `BASE_DOMAIN=laggente.com`, `APP_ORIGIN=https://app.laggente.com`, `CORS_ORIGINS=https://app.laggente.com`, `TRUSTED_HOSTS=laggente.com,*.laggente.com`, `COOKIE_SECURE=true`, and `AUTO_CREATE_SCHEMA=false`; deployment and audit reject a server file that drifts from any of those exact values. Visitor and apex traffic stays same-origin through the gateway and does not receive credentialed cross-origin access. The server-side `OPENAI_API_KEY` enters only the API container. The gateway receives no secret or runtime application env file; its Vite assets are fixed at image build time and call relative `/api/v1` routes.

Before starting containers, check ownership, modes, and key names without printing values:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes -o ConnectTimeout=8 root@116.203.123.0 '
    set -eu
    for secret_file in \
      /opt/laggente/secrets/database.env \
      /opt/laggente/secrets/application.env
    do
      stat -c "%U:%G %a %n" "$secret_file"
      awk -F= "/^[A-Z][A-Z0-9_]*=/ {print \$1 \"=[redacted]\"}" "$secret_file"
    done
  '
```

Expected ownership and mode are `root:laggente 640` for both. A pre-existing `/opt/laggente/secrets/production.env` is ignored by current releases and intentionally left untouched by bootstrap for rollout compatibility. Treat it as a manual removal candidate only after the split release passes Compose validation, deployment health gates, and the production audit.

## 4. Configure DNS and TLS

Complete [Domains and Subdomains](DOMAINS_AND_SUBDOMAINS.md) before enabling the host nginx site.
The wildcard procedure installs the pinned `acme-dns.service`, performs one full-record-preserving
Namecheap delegation from the allowlisted Hetzner origin, issues `laggente-wildcard`, and proves a
dry-run renewal. Certificate issuance does not stop application containers or neighboring services.

## 5. First application release

Validate the encoded topology before using the release script. With Docker available, `--build`
also builds the static gateway and backup images, starts an ephemeral gateway on an explicitly
selected high `127.0.0.1` port, verifies that Docker published only that loopback mapping, and checks
SPA history fallback, missing-asset and unknown-API behavior, and query-preserving canonical
redirects. The direct image run mirrors the production gateway's read-only filesystem and writable
nginx tmpfs mounts, while the explicit mapping lets the validator inspect the exact loopback bind.
If Docker starts a live container without materializing that mapping, repair the rootless network
backend and rerun the gate; do not bypass it:

```bash
./scripts/validate-infrastructure.sh --build
```

The preferred steady-state release supplies three immutable image references ending in
`@sha256:<digest>`: API, gateway (including the static web build), and backup. Until an external
builder/registry is configured, the explicit initial fallback builds one image at a time on the
server:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes laggente@116.203.123.0
cd /opt/laggente/repo
release_sha=REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA
./scripts/deploy-production.sh \
  --release "$release_sha" \
  --git-sha "$release_sha" \
  --build-on-host
```

The script validates secrets and free space, serializes the builds, starts container PostgreSQL, runs `alembic upgrade head`, activates the services, waits for the loopback gateway, and records `current.env`. On a failed health check it automatically returns application containers to the previous image set. It never automatically restores the database after a migration.

For later immutable-image releases:

```bash
./scripts/deploy-production.sh \
  --release RELEASE_ID \
  --git-sha FULL_40_CHARACTER_COMMIT_SHA \
  --api-image 'REGISTRY/laggente-api@sha256:DIGEST' \
  --gateway-image 'REGISTRY/laggente-gateway@sha256:DIGEST' \
  --backup-image 'REGISTRY/laggente-backup@sha256:DIGEST'
```

All production migrations must be backward-compatible with the previously deployed application. Destructive schema changes require a separate migration plan and a restore-tested pre-migration backup.

## 6. Enable the host nginx site

Only after `/etc/letsencrypt/live/laggente-wildcard/` exists with the apex and wildcard SANs:

```bash
sudo install -m 0644 \
  /opt/laggente/repo/infra/nginx/laggente.conf \
  /etc/nginx/sites-available/laggente.conf
sudo ln -sfn /etc/nginx/sites-available/laggente.conf \
  /etc/nginx/sites-enabled/laggente.conf
if [ -L /etc/nginx/sites-enabled/laggente-http-bootstrap.conf ]; then
  sudo unlink /etc/nginx/sites-enabled/laggente-http-bootstrap.conf
fi
sudo nginx -t
sudo systemctl reload nginx
```

The template adds host preservation, body limits, connection and route-specific rate limits, security headers, a `www` canonical redirect, streaming-friendly proxy settings, and routing for the apex, Studio, Mauro, and every published wildcard host. Both nginx layers use a dedicated JSON access format with method, normalized `$uri`, status, timing, client, and request ID; query arguments and referers are deliberately omitted so magic-link and signed-download tokens do not enter access logs. The active certificate covers the apex and `*.laggente.com`; no certificate or nginx change occurs per professional.

## 7. Verify the release

Run the server audit first, then public smoke checks:

```bash
ssh -i /Users/andreabertoncini/.ssh/hetzner_wofi_ed25519 \
  -o BatchMode=yes laggente@116.203.123.0 \
  'cd /opt/laggente/repo && ./scripts/audit-production.sh'

cd /Users/andreabertoncini/laggente
./scripts/smoke-production.sh
```

The HTTP smoke confirms that the Mauro API exposes its immutable AI-label contract, but a static
Vite shell cannot prove that runtime React rendered the disclosure where a person can see it. Also
perform the browser acceptance journey on real HTTPS hosts:

1. `app.laggente.com`: Mauro signs in and talks with the private Studio assistant in Italian.
2. Mauro proposes, previews, and explicitly activates a revision.
3. `mauro.laggente.com`: a visitor sees the rendered AI disclosure immediately, before sending
   personal information or a message, and holds a persistent Italian conversation.
4. The public assistant reflects only the active revision, not an unactivated proposal.
5. Mauro sees and joins the same public conversation as a visibly human author; automatic AI replies pause.
6. A second browser profile cannot read the first visitor's conversation without its continuation identity.
7. A second published professional host passes ordinary browser TLS and resolves only its own tenant.
8. Unknown and reserved subdomains pass edge TLS but return a safe response and never resolve tenant data from a client-supplied account ID.

Browser acceptance and taste remain separate from container health.

## Rollback

List recorded releases and roll back application images:

```bash
ls -l /opt/laggente/releases/*.env
cd /opt/laggente/repo
./scripts/rollback-production.sh PREVIOUS_RELEASE_ID
```

Rollback takes a fresh logical backup, activates the selected images, checks loopback health, and updates the release pointers. It deliberately leaves the migrated database in place. Restoring PostgreSQL is a last-resort data-recovery action, not a normal application rollback; follow [Backup and Restore](BACKUP_AND_RESTORE.md).

## Shared-host safety

- Never publish Compose ports `5432` or `8000`, and never bind the gateway anywhere except the
  documented loopback address.
- Never change the existing host PostgreSQL, WOFI database, or WOFI systemd units.
- Never run `docker system prune` or unbounded release deletion on this shared disk.
- Never put Namecheap, OpenAI, database, or email credentials in Git, image layers, build arguments, or browser environment variables.
- Run `nginx -t` before every host nginx reload.
- Inspect the Hetzner Cloud firewall separately. Docker publishes only loopback here. Public access is
  limited to the established SSH source, HTTP/HTTPS `80/443`, and authoritative DNS TCP/UDP `53` for
  `auth.laggente.com`; the acme-dns HTTP API remains loopback-only on `127.0.0.1:5399`.
- Enable Hetzner provider backups or another off-host copy before treating the local backup job as disk-loss protection.
