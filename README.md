# LAGGENTE

> La gente incontra l'agente.

LAGGENTE gives every real-estate professional a personal digital space with two conversational assistants:

- a private Studio assistant that helps the professional shape the space by talking;
- a public assistant that receives people, remembers conversations, and represents the professional without impersonating them.

Between the two assistants is not a third autonomous agent. It is the LAGGENTE application: persistent configuration, conversations, messages, files, memory, permissions, and human participation.

```text
real-estate professional
          ↕
private Studio assistant
          ↕
shared persistent space
          ↕
public assistant
          ↕
visitor
```

The product experience is agentic. The control boundaries are deterministic.

## The first product

The pilot begins with Mauro and expands to five real-estate professionals. Each professional has two surfaces:

- `app.laggente.com` — the private Studio;
- `<slug>.laggente.com` — the public personal space, beginning with `mauro.laggente.com`.

Expansion is invitation-only during the pilot. A member with the platform invitation permission
enters one email address. LAGGENTE creates a separate dormant account and sends a single-use magic
link. The invited professional introduces themselves to Studio in natural Italian, reserves an
available slug, reviews the generated revision, and activates it. That first activation—not a code
change, deployment, or per-professional environment file—opens the public subdomain.

The experience begins with the professional, not the visitor. Each invited professional creates
their identity, chooses the public slug that becomes their subdomain, and talks with the private
Studio assistant about their territory, work, style, knowledge, preferences, and the kind of space
they want to offer people. Mauro remains the seeded first tenant, not a runtime template for the
professionals who follow.

That conversation shapes a living configuration for Mauro's space. The configuration is deliberately extensible: it can grow with what Mauro says and with what the product learns, rather than forcing every professional into a narrow profile schema or fixed onboarding questionnaire. The application keeps only the stable structure required for ownership, publication, permissions, safety, and reliable execution.

Mauro starts from a useful template for conversations with people who may want to sell a property. The template is not a questionnaire, sales pipeline, or universal real-estate ontology. Through the Studio, Mauro can change how his space introduces him, what it knows, how it speaks, what it notices, what it can do, and when it should invite him into a conversation.

The Studio prepares a proposed change and shows Mauro its effect. Mauro decides when that change becomes active. Previous revisions remain recoverable.

The public assistant is the expression and proof of that configuration. It holds natural, persistent conversations in Italian using only Mauro's active space; it can work with text, voice notes, and photographs; maintain useful memory; surface corrections; and help Mauro understand where his attention may be valuable. Visitor information and conversations belong to Mauro's private account context, and Mauro can enter the same conversation without forcing the person through a separate handoff flow.

## What LAGGENTE is not

LAGGENTE is not Salesforce with an AI chat window. It does not ask the professional to maintain a pipeline, classify leads, update arbitrary stages, or perform data entry for the system.

Conversations are primary. Memory, summaries, signals, and possible opportunities are generated from them and remain inspectable and correctable. They are views that help the professional act, not administrative work imposed on the professional.

## Product language

The MVP is Italian-first. User-facing interface copy, seeded content, conversations, notifications, dates, and product tests use `it-IT`. Source code, identifiers, and technical documentation may remain in English.

Use `professional` in code and technical prose for the human real-estate professional. Avoid the bare word `agent` where it could be confused with an AI agent.

## Documentation map

Start with the [documentation index](docs/README.md).

| Area | Document |
| --- | --- |
| Product thesis | [Product Vision](docs/vision/PRODUCT_VISION.md) |
| Current product blueprint | [LAGGENTE MVP Blueprint](docs/blueprints/LAGGENTE_BLUEPRINT_MVP.md) |
| Product we want | [MVP Scope](docs/product/MVP_SCOPE.md) |
| System shape | [System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) |
| Hosting | [Hetzner Deployment](docs/operations/HETZNER_DEPLOYMENT.md) |
| Domains | [Domains and Subdomains](docs/operations/DOMAINS_AND_SUBDOMAINS.md) |
| AI collaboration | [ChatGPT Work and Codex](docs/workflows/CHATGPT_WORK_AND_CODEX.md) |
| Git workflow | [Development Workflow](docs/workflows/DEVELOPMENT_WORKFLOW.md) |
| Decisions | [Architecture Decision Records](docs/decisions/README.md) |

## Working principle

The repository is the durable source of truth. ChatGPT Work, Codex cloud, and local Codex are different working surfaces around the same project, not separate versions of it.

See [AGENTS.md](AGENTS.md) before making repository changes.

## Implemented pilot

The repository now contains a generic LAGGENTE brand entry surface for real-estate professionals
and the Mauro pilot as one tenant space inside the bespoke Vite/React single-page interface. The
apex explains the product without presenting the seeded pilot identity as the product's universal
target. Vite produces static assets during the gateway image build; the existing internal nginx
gateway serves those assets and proxies same-origin `/api/v1` REST endpoints to FastAPI. There is no
Node.js web process in the production runtime. Exactly two OpenAI Agents SDK definitions power the
private Studio assistant and the public assistant. PostgreSQL remains the application-owned source
of truth for tenant-scoped configuration, conversations, messages, correctable memory, attachments,
and audit events.

The implemented pilot can provision additional professional spaces end to end through an
authorized Studio invitation. Dormant invited tenants cannot resolve publicly; slug selection is
globally checked and first publication requires both a claimed slug and an explicitly activated
configuration. Shared Studio, public-space, conversation, media, and takeover code reads the
resolved tenant and contains no Mauro-specific runtime fallback.

Conversation turns currently use durable, non-streaming request/response transport. ChatKit is
not part of the implemented runtime or persistence contract. See
[ADR-0001](docs/decisions/0001-single-hetzner-server.md).

## Current status

- Product blueprint: invited multi-tenant proof 0.4.
- Seeded pilot professional: Mauro; additional professionals join by controlled invitation.
- Pilot size: five real-estate professionals.
- Initial template: conversations with people considering selling a property.
- Hosting decision: one existing Hetzner server for the MVP.
- Repository phase: implemented MVP pilot application and production infrastructure; release checks and
  live deployment state must still be reported separately from repository state.
