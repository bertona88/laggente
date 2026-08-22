# System Architecture

## Status

This document describes the intended MVP architecture. It is not authorization to scaffold or deploy the system.

## Product surfaces

| Host | Surface | User |
| --- | --- | --- |
| `laggente.com` | Brand and entry page | Public |
| `app.laggente.com` | LAGGENTE Studio and opportunity dashboard | Authenticated professional |
| `<slug>.laggente.com` | Personal digital branch office | Public homeowner |
| `laggente.com/<slug>` | Development and DNS fallback | Public homeowner |

## Runtime topology

The MVP is hosted on one existing Hetzner server with Docker Compose.

- reverse proxy and TLS termination;
- Next.js/React web application;
- FastAPI service for ChatKit, Agents SDK, tools, streaming, and server-side business logic;
- PostgreSQL;
- private upload storage on the server filesystem;
- scheduled database and file backups.

Redis, Kubernetes, Vercel, Railway, and a managed database are not part of the accepted MVP topology.

## Software agents

### Private Builder

The Builder can read and modify only the authenticated tenant's draft configuration through typed, server-authorized tools. It shows a preview and diff and publishes only after explicit approval.

### Public Concierge

The Concierge reads only the active published configuration. It runs the Seller Playbook, collects facts, reads approved knowledge, creates a confirmed dossier, requests a valuation or handoff, and never impersonates the professional.

## Configuration model

Conversation is the configuration interface. Conversation is not the configuration database.

The server compiles runtime behavior in this precedence order:

1. immutable LAGGENTE policy;
2. role contract;
3. published tenant configuration;
4. active Playbook;
5. approved knowledge;
6. conversation state.

Publishing switches the active configuration version in PostgreSQL. It does not deploy code.

## Minimum domain model

| Entity | Purpose |
| --- | --- |
| `accounts` | Professional or agency tenant |
| `members` | Authenticated users, roles, and permissions |
| `public_profiles` | Public identity, slug, portrait, and contact details |
| `config_versions` | Draft and published configuration history |
| `playbooks` | Versioned workflows |
| `knowledge_sources` | Approved facts, FAQs, notes, and sources |
| `conversations` | Private and public threads |
| `messages` | AI, human, customer, and system messages |
| `leads` | Commercial opportunity and status |
| `lead_facts` | Structured seller, property, motivation, and timing data |
| `summaries` | Generated and customer-confirmed dossiers |
| `handoffs` | Request, assignment, and takeover state |
| `consents` | Privacy, marketing, audio, and timestamps |
| `events` | Audit trail for publishing, tools, and state changes |

Every tenant-owned row contains `account_id`.

## Request and tenant resolution

1. DNS sends `*.laggente.com` to the Hetzner server.
2. The reverse proxy terminates TLS and forwards the original validated hostname.
3. The application extracts and normalizes the slug.
4. The server resolves the slug to an active public profile and `account_id`.
5. Every subsequent query and tool invocation enforces that `account_id`.
6. Unknown or reserved hosts return a safe not-found response.

The hostname is a routing input, never the security boundary.

## Security boundaries

- No OpenAI, database, DNS, or deployment secret reaches the browser.
- PostgreSQL is not exposed publicly.
- Uploads are private and served through authorized, short-lived application URLs.
- Public writes go through rate-limited server endpoints.
- Tool arguments are validated and authorized server-side.
- User messages and uploads are untrusted input.
- Professional sessions use host-only cookies for `app.laggente.com` rather than cookies shared with all tenant subdomains.
- AI and human speaker state is explicit and audited.

