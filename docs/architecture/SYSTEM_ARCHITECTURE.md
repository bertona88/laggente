# System Architecture

## Status

This document describes the MVP pilot architecture implemented in this repository. It records
system truth; deployment, DNS, migration, and production operations still require the authority
defined by repository and operations policy.

## Product surfaces

| Host | Surface | User |
| --- | --- | --- |
| `laggente.com` | Brand and entry page | Public |
| `app.laggente.com` | Private Studio and conversation workspace | Authenticated professional |
| `<slug>.laggente.com` | Personal public space | Visitor |
| `laggente.com/<slug>` | Development and preview fallback | Visitor |

All MVP user-facing surfaces default to Italian (`it-IT`).

## Core product topology

```text
authenticated professional
          ↕
private Studio assistant
          ↕ authorized tools
LAGGENTE coordination layer
  configuration · conversations · memory · files · permissions
          ↕ active space context
public assistant
          ↕
visitor

The professional may also join the public conversation directly.
```

The coordination layer is ordinary application code and persistent data. It is not a third AI agent.

## Runtime topology

The MVP runs on one existing Hetzner server with Docker Compose:

- reverse proxy and TLS termination;
- internal nginx gateway serving a bespoke Vite/React static single-page build for the brand,
  Studio, and public space;
- same-origin JSON and multipart REST routes, proxied from `/api/v1` to FastAPI;
- FastAPI application logic and exactly two OpenAI Agents SDK assistant definitions;
- PostgreSQL;
- private upload storage on the server filesystem;
- scheduled database and file backups.

Node.js and Vite are build-stage tools only. The gateway image compiles `apps/web`, copies the
resulting immutable files into nginx, serves history routes through `index.html`, and caches
fingerprinted assets. Production has no separate web application process. The browser reads the
hostname for presentation and routing, but FastAPI independently resolves the host to an active
space and enforces `account_id` for every data operation.

The SPA history fallback is deliberately outside the API namespace. Exact `/api/v1` and every
`/api/v1/...` request go to FastAPI; known health paths are explicit; every other `/api/...` path
returns an HTTP 404 and can never receive `index.html`. The host nginx keeps its attachment-upload
regex limiter ahead of the ordinary `/api/v1/` prefix before forwarding into the same boundary.

The Studio assistant and public assistant reuse the application-owned conversation store, HTTP
transport, model integration, and authorized-tool framework. They have different roles,
instructions, participants, and access contexts; shared infrastructure must never collapse their
permission boundaries or expose private Studio material publicly.

Redis, Kubernetes, Vercel, Railway, and a managed database are not part of the accepted MVP topology.

Conversation turns currently complete as durable, non-streaming HTTP request/response operations.
The FastAPI service runs the relevant assistant through the Agents SDK and persists authored
messages and derived interpretations in the application database. Provider-side conversation
storage and SDK tracing are disabled; private reasoning is not persisted. ChatKit is not an
implemented transport or store contract. See
[ADR-0001](../decisions/0001-single-hetzner-server.md) and the
[Agents SDK guide](https://developers.openai.com/api/docs/guides/agents).

## Two AI roles

### Private Studio assistant

The Studio talks with an authenticated professional. Through typed, server-authorized capabilities, it can inspect the current space, start from a template, and propose changes to:

- public identity and presentation;
- tone, language, and conversational behavior;
- professional knowledge;
- topics and signals worth noticing;
- available actions and media capabilities;
- invitation and human-participation preferences;
- bounded layout and component choices supplied by the platform.

The Studio does not impose a real-estate methodology and does not generate arbitrary application code, scripts, or tenant HTML in the MVP.

### Public assistant

The public assistant talks with visitors using only the active configuration of the resolved professional space. It can converse naturally, use approved knowledge, maintain correctable memory, work with enabled tools, and invite the professional to participate.

It does not run a hard-coded qualification pipeline. The initial seller template is guidance for useful behavior, not a required sequence of questions or completion gates.

## Coordination layer responsibilities

The application between the two assistants owns:

- tenant and professional identity;
- active and historical space configuration;
- persistent threads, participants, messages, and attachments;
- retrieval of approved professional knowledge;
- correctable memory and generated conversation views;
- authorized tool execution;
- human participation and automatic-response control;
- notifications;
- consent, retention, deletion, and audit events;
- rate limits and abuse controls.

The coordination layer may ask an AI model to interpret or summarize. It does not surrender authorization or data ownership decisions to the model.

### Pilot abuse and capacity ceilings

The coordination layer owns the following pilot ceilings independently of both assistants and of
tenant configuration:

| Resource | Enforced ceiling |
| --- | --- |
| Durable image storage | 512 MiB per account and 50 MiB per conversation |
| Attachments | 20 records per conversation, including image and audio records |
| Audio transcription | 12 attempts per account in a rolling hour |
| Public-assistant model use | 60 model-backed turns per space in a rolling hour |
| Conversation creation | 60 new public conversations per space in a rolling hour |
| Empty-conversation pressure | At most 60 unengaged public conversations per space; conversations without a visitor/professional message, professional participation, or a bound attachment expire after one hour and are pruned on a subsequent creation attempt |
| Studio inbox projection | Cursorless offset pages of 1–100 conversations; the client can retrieve older pages |

The inbox page size bounds each retrieval, not reachability or durable conversation retention. Raw
audio is discarded after transcription. A successfully transcribed or photographed draft has a
one-hour binding window; an abandoned unbound record and any private image payload are then
reclaimed. A failed transcription releases its unusable row immediately while its content-free
attempt event remains for rolling spend control. The byte ceilings apply to durable image payloads.
The rolling public rate counters live in the single API process used by the current pilot
topology and reset if that process restarts; database-backed storage, attachment, transcription,
and unengaged-conversation checks remain persistent. These operational controls do not create a
lead taxonomy, a mandatory visitor questionnaire, or another AI role.

The API process enforces `CONVERSATION_RETENTION_DAYS` automatically. It starts the first cycle
after a five-minute startup grace, then checks every six hours with a fresh database session. Each
expired public conversation uses the same tenant-scoped deletion routine as an explicit request,
including private-file removal and a content-free outcome event. A failed cycle is logged and
retried at the next interval rather than disabling the public service.

## Configuration model

Conversation is the configuration interface. The stored space configuration is the durable public behavior.

Each professional space has:

1. a starting template;
2. a current active configuration;
3. proposed revisions created through the Studio;
4. recoverable revision history.

A Studio message may produce a proposed revision. It does not silently change public behavior. The professional reviews the visible effect and explicitly activates the revision. Activation changes data in PostgreSQL; it does not deploy code or infrastructure.

The active configuration remains document-shaped and extensible. The platform validates a stable envelope for ownership, revision identity, activation, permissions, capabilities, safety, and references to protected resources. It must not require every professional-specific fact, preference, example, or way of working to fit a closed schema.

The Studio may extend the configuration document as new meaning emerges from conversation. Runtime instructions are composed from the active configuration; the stored configuration is not merely one opaque generated prompt. Professional meaning remains inspectable and correctable, and stable application controls remain typed and server-authorized.

The meta-prompting loop is therefore concrete product behavior: Studio conversation → evolving space configuration → professional preview and activation → composed public-assistant behavior. It is not a general-purpose prompt generator built independently of the space it is meant to create.

Do not normalize every possible professional preference into a dedicated table, build a universal onboarding field set, or treat the current seller template as the configuration schema.

## Conversation and memory model

Conversation is primary. A persistent thread contains participants, messages, attachment references, and authorship. A visitor may begin with a secure anonymous session identity and later provide contact information without being forced to create an account.

Memory is derived from conversation content. It may contain facts, preferences, open questions, summaries, signals, and suggested next actions. Every derived item must retain enough provenance to show where it came from and must be correctable without rewriting the original message history.

An `opportunity` is initially a generated view or signal that a conversation may deserve professional attention. Do not create a universal sales lifecycle until real usage proves that it exists.

## Minimum persistent model

| Entity | Purpose |
| --- | --- |
| `accounts` | Tenant boundary for a professional or agency |
| `members` | Authenticated people, roles, and permissions within an account |
| `spaces` | Public identity, slug, active configuration reference, and visibility |
| `config_revisions` | Proposed, active, and historical space configurations |
| `conversations` | Persistent private Studio or public threads |
| `messages` | Immutable authored items in a conversation |
| `attachments` | Private audio, photograph, and other supported file metadata |
| `memory_items` | Correctable, provenance-linked interpretations derived from conversations |
| `events` | Audit trail for authentication, configuration, assistant failures, media, memory correction, and speaker control |
| `magic_links` | Signed, expiring, single-use Studio authentication records when magic-link mode is enabled |

This table describes the current application-owned persistence boundary, not a permanent command
to create one table per future noun. Participant identity and visible authorship are represented by
conversation state and immutable message authorship in this release; a separate participant
lifecycle has not been introduced without evidence that it is needed.

Every tenant-owned record contains `account_id`. Every public conversation and attachment is also bound to the resolved `space_id` and authorized through server-side context.

## Conversation persistence and transport boundary

The browser calls relative `/api/v1` endpoints. The reverse proxy sends those same-origin requests
to FastAPI, which authorizes them, runs application or assistant logic, and commits the resulting
records to PostgreSQL before returning a complete JSON response. Uploads use bounded multipart
requests and private filesystem storage; downloads pass through an authorized FastAPI route.

Application records are the only durable conversation truth. They contain the context a model or
generic chat transport cannot infer safely: account, space, authenticated member, anonymous
visitor continuation identity, authorship, attachment ownership, revision activation, and
AI-response control. Adding streaming or ChatKit later must preserve this boundary and must not
create a second chat database.

## Human participation

Human participation is not modeled as a one-way sales handoff pipeline.

The application tracks two independent facts:

- which participants are present or have authored messages;
- whether automatic public-assistant replies are enabled.

When the professional writes, the interface identifies them explicitly and automatic replies pause by default. Re-enabling the assistant is an explicit professional action. The message history remains one continuous conversation.

## Request and tenant resolution

1. DNS sends `*.laggente.com` to the Hetzner server.
2. The reverse proxy terminates TLS and forwards the validated original hostname.
3. The application extracts and normalizes the slug.
4. The server resolves the slug to an active space and `account_id`.
5. Every store operation, query, tool invocation, file path, and event independently enforces that context.
6. Unknown, inactive, or reserved hosts return a safe not-found response.

The hostname is a routing input, never the security boundary.

## Security boundaries

- No OpenAI, database, DNS, or deployment secret reaches the browser.
- PostgreSQL is not exposed publicly.
- Uploads are private and served through same-origin application endpoints that re-authorize every
  request from the current visitor or professional session and disable shared caching.
- Public writes go through rate-limited server endpoints.
- Tool arguments and configuration revisions are validated and authorized server-side.
- User messages, professional knowledge, and uploads are untrusted input.
- Professional sessions use host-only cookies for `app.laggente.com`, not cookies shared with tenant subdomains.
- An anonymous continuation token grants access only to its own public conversation and is revocable.
- AI and human authorship is explicit and audited.
- Raw audio is deleted after transcription by default unless an explicit retained-audio policy applies.
- Private chain-of-thought is never stored.

## Design consequence

The architecture should make the product feel simple: two conversations around one living space. Internal services, schemas, and controls exist to preserve that simplicity, not to expose a CRM underneath it.
