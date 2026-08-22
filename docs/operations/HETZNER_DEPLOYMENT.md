# Hetzner Deployment

## Decision

The MVP will use the existing Hetzner server. Server administration, Namecheap, DNS, secrets, and deployment execution are owned by local Codex under explicit human authorization.

ChatGPT Work and Codex cloud may design, implement, and review the repository-side deployment assets, but they must not assume access to operational credentials.

## Intended containers

| Service | Responsibility |
| --- | --- |
| Reverse proxy | HTTPS, hostname validation, routing, security headers |
| Web | Next.js marketing, Studio, conversation workspace, and public spaces |
| API | FastAPI, ChatKit server, Agents SDK, tools, streaming, and business logic |
| PostgreSQL | Persistent spaces, conversations, messages, memory, and configuration revisions |
| Backup job | Database dumps and private upload backup |

The MVP does not require Redis. Background work should remain simple until measured load or reliability requirements justify a queue.

## Planned server layout

```text
/opt/laggente/
  repo/
  data/
    postgres/
    uploads/
    backups/
  secrets/
    production.env
```

Paths are indicative and must be validated against the actual server before implementation.

## Bootstrap checklist

Local Codex should inspect the existing server before changing it and record relevant non-secret findings. The bootstrap task should cover:

- operating system, CPU, RAM, disk, existing services, and occupied ports;
- dedicated non-root deployment user;
- SSH key authentication and restricted privilege escalation;
- Docker Engine and Docker Compose;
- Hetzner firewall allowing only required public ports;
- application directories and permissions;
- server-side secret file outside Git;
- reverse proxy and TLS;
- log rotation and disk monitoring;
- security updates;
- backup and tested restore procedure.

Never paste SSH keys, passwords, API tokens, or production environment values into project documentation or chat.

## Deployment flow

The intended release path is:

> feature branch → pull request → checks → approved merge → production release → migration → container update → health check

Early deployments may be initiated by local Codex over SSH. The desired steady state is a small, explicit deployment script or GitHub workflow using a restricted deployment identity.

Production deployment, DNS changes, and production database migrations always require explicit authorization.

## Data and backups

At minimum:

- scheduled `pg_dump` with retention;
- scheduled copy of private uploads;
- backup stored outside the primary application disk;
- periodic restore test;
- pre-migration database backup;
- documented retention and deletion behavior for homeowner data and raw audio.

A provider snapshot is useful for server recovery but does not replace application-consistent database backup.

## Rollback

The deployment design must support:

- returning to the previously deployed application image or Git release;
- backward-compatible database changes where possible;
- restoring the database only as a deliberate last resort;
- returning a professional space to an earlier configuration revision.

Application rollback and configuration rollback are separate operations.
