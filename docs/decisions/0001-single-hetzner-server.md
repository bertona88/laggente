# ADR-0001: Run the MVP on the Existing Hetzner Server

- **Status:** Accepted
- **Date:** 2026-08-22
- **Amended:** 2026-08-22 — the uncommitted, undeployed Next.js runtime plan was replaced by a
  Vite/React static build served by the existing container gateway

## Context

The founding blueprint described a production-shaped architecture but intentionally left exact hosting providers open. An existing Hetzner server is already available. The pilot serves five professionals and does not yet justify multiple managed platforms or distributed infrastructure.

## Decision

Run the first LAGGENTE MVP on the existing Hetzner server using Docker Compose.

The intended runtime consists of:

- reverse proxy with HTTPS;
- nginx container gateway serving the Vite/React static build and proxying same-origin API routes;
- FastAPI agent service;
- PostgreSQL;
- private filesystem uploads;
- scheduled PostgreSQL and private-upload backup sets, with the documented cross-store consistency
  caveat.

The browser uses a bespoke Vite/React SPA and relative same-origin `/api/v1` REST endpoints. The
gateway compiles the client during its image build, serves the immutable assets with SPA history
fallback, and proxies the reserved API namespace to FastAPI. Production has no separate Node.js
application server. FastAPI owns authentication, tenant authorization, active configuration,
attachments, and exactly two Agents SDK assistant roles.

Conversation turns are durable, non-streaming request/response operations in this pilot. PostgreSQL
application records are the source of truth; OpenAI provider storage and SDK tracing are disabled.
ChatKit transport, widgets, and provider-owned conversation state are not implemented. A later
streaming or ChatKit transport must preserve the same application-owned persistence, tenant,
privacy, and human-control boundaries without creating a second conversation store.

Server administration, Namecheap, DNS, secrets, and deployment execution are performed through local Codex under explicit authorization.

Do not introduce Vercel, Railway, Redis, Kubernetes, or a managed database for the MVP unless an observed constraint justifies a new ADR.

## Consequences

### Positive

- minimal additional infrastructure cost;
- simple operational topology;
- complete control over the runtime and networking;
- one deployment surface for the pilot;
- easy migration later because services are containerized and state is explicit;
- no dedicated Node.js process or web container in the production runtime;
- one inspectable application contract for browser routing, retries, authorization, and durable
  conversation truth.

### Negative

- the server is initially a shared failure domain;
- backups, upgrades, monitoring, and security hardening are our responsibility;
- deployments and database changes require more operational discipline than a fully managed platform;
- horizontal scaling is deferred.
- token-by-token streaming and ChatKit widgets are unavailable in this release;
- LAGGENTE owns the SPA route fallback, client adapters, retry behavior, and REST compatibility.

## Alternatives considered

- **Next.js application runtime:** replaced before the first commit or deployment because the
  implemented pilot needs static client assets plus the existing FastAPI boundary, not SSR, Server
  Actions, or a second runtime service.
- **Custom ChatKit transport now:** rejected because it would add another transport/store contract
  before the authored product surfaces and application data boundary are proven.
- **Direct browser-to-OpenAI calls or provider-owned thread state:** rejected because secrets,
  tenant authorization, active configuration, persistence, file access, and speaker control are
  server responsibilities.

## Triggers for reconsideration

- resource contention that cannot be solved by resizing;
- unacceptable downtime or recovery objectives;
- sustained workloads requiring a queue or independent workers;
- compliance or data-residency obligations that require a different topology;
- a team size that makes manual server ownership a delivery bottleneck.
