# System Architecture

## Status

This document describes the intended MVP architecture after the agentic product reset. It is not authorization to scaffold, deploy, change DNS, or operate production.

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
- Next.js/React web application;
- FastAPI service for ChatKit, Agents SDK, authorized tools, streaming, and application logic;
- PostgreSQL;
- private upload storage on the server filesystem;
- scheduled database and file backups.

Redis, Kubernetes, Vercel, Railway, and a managed database are not part of the accepted MVP topology.

OpenAI's current ChatKit path supports a custom server-side integration, durable store and file-store contracts, and Agents SDK streaming. The application remains responsible for authentication, authorization, persistence, and tenant context. See [ChatKit](https://developers.openai.com/api/docs/guides/chatkit) and [advanced ChatKit integrations](https://developers.openai.com/api/docs/guides/custom-chatkit).

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

## Configuration model

Conversation is the configuration interface. The stored space configuration is the durable public behavior.

Each professional space has:

1. a starting template;
2. a current active configuration;
3. proposed revisions created through the Studio;
4. recoverable revision history.

A Studio message may produce a proposed revision. It does not silently change public behavior. The professional reviews the visible effect and explicitly activates the revision. Activation changes data in PostgreSQL; it does not deploy code or infrastructure.

The active configuration may remain document-shaped and evolve through validated schemas. Do not normalize every possible professional preference into a dedicated table before usage proves the need.

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
| `participants` | Human professionals, visitors, AI identities, and system identity in conversations |
| `conversations` | Persistent private Studio or public threads |
| `messages` | Immutable authored items in a conversation |
| `attachments` | Private audio, photograph, and other supported file metadata |
| `memory_items` | Correctable, provenance-linked interpretations derived from conversations |
| `events` | Audit trail for configuration, tools, speaker control, consent, and deletion |

This is a conceptual minimum, not a command to create one table per noun. ChatKit storage models may be persisted as JSON where appropriate, while application-owned fields maintain tenant, space, participant, and authorization boundaries.

Every tenant-owned record contains `account_id`. Every public conversation and attachment is also bound to the resolved `space_id` and authorized through server-side context.

## Chat persistence boundary

The FastAPI ChatKit server uses a durable PostgreSQL-backed store for threads and items and a filesystem-backed file store for uploads. ChatKit transport objects do not become a separate source of business truth mirrored into an unrelated chat system.

Application records add the fields ChatKit cannot infer safely: account, space, authenticated member, visitor continuation identity, retention policy, consent, and AI-response control.

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
- Uploads are private and served through authorized, short-lived application URLs.
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
