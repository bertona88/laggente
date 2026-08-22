# ADR-0001: Run the MVP on the Existing Hetzner Server

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

The founding blueprint described a production-shaped architecture but intentionally left exact hosting providers open. An existing Hetzner server is already available. The pilot serves five professionals and does not yet justify multiple managed platforms or distributed infrastructure.

## Decision

Run the first LAGGENTE MVP on the existing Hetzner server using Docker Compose.

The intended runtime consists of:

- reverse proxy with HTTPS;
- Next.js web application;
- FastAPI agent service;
- PostgreSQL;
- private filesystem uploads;
- application-consistent backups.

Server administration, Namecheap, DNS, secrets, and deployment execution are performed through local Codex under explicit authorization.

Do not introduce Vercel, Railway, Redis, Kubernetes, or a managed database for the MVP unless an observed constraint justifies a new ADR.

## Consequences

### Positive

- minimal additional infrastructure cost;
- simple operational topology;
- complete control over the runtime and networking;
- one deployment surface for the pilot;
- easy migration later because services are containerized and state is explicit.

### Negative

- the server is initially a shared failure domain;
- backups, upgrades, monitoring, and security hardening are our responsibility;
- deployments and database changes require more operational discipline than a fully managed platform;
- horizontal scaling is deferred.

## Triggers for reconsideration

- resource contention that cannot be solved by resizing;
- unacceptable downtime or recovery objectives;
- sustained workloads requiring a queue or independent workers;
- compliance or data-residency obligations that require a different topology;
- a team size that makes manual server ownership a delivery bottleneck.

