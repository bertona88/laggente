# LAGGENTE

> La gente incontra l'agente.

LAGGENTE gives a human professional a personal digital space with two conversational assistants:

- a private Studio assistant that helps the professional shape the space by talking;
- a public assistant that receives people, remembers conversations, and represents the professional without impersonating them.

Between the two assistants is not a third autonomous agent. It is the LAGGENTE application: persistent configuration, conversations, messages, files, memory, permissions, and human participation.

```text
human professional
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

The product foundation can specialize to different professions. The commercial pilot deliberately begins with Mauro and expands to five real-estate professionals, so real estate remains the first and most prominent example. Each professional has two surfaces:

- `app.laggente.com` — the private Studio;
- `<slug>.laggente.com` — the public personal space, beginning with `mauro.laggente.com`.

Entry is email-first and open to professionals. LAGGENTE sends a single-use verification link and
creates no tenant until that link is consumed. The verified professional then enters a separate,
private Studio, introduces themselves in natural Italian, reserves an available slug, reviews the
generated revision, and activates it. Existing members return through the same email form. Curated
Studio invitations remain available, but they are no longer a prerequisite. First activation—not a
code change, deployment, or per-professional environment file—opens the public subdomain.

The experience begins with the professional, not the visitor. Each professional creates
their identity, then Studio begins with the backend-owned question “Che lavoro fai?” and adapts its
examples and starting template to the answer. The professional chooses the public slug that becomes
their subdomain and talks with Studio about territory, work, style, knowledge, preferences, and the
kind of space they want to offer people. Mauro remains the seeded first tenant, not a runtime
template for the professionals who follow.

That conversation shapes a living configuration for Mauro's space. The configuration is deliberately extensible: it can grow with what Mauro says and with what the product learns, rather than forcing every professional into a narrow profile schema or fixed onboarding questionnaire. The application keeps only the stable structure required for ownership, publication, permissions, safety, and reliable execution.

Mauro starts from the highest-weighted backend template: conversations with people who may want to sell a property. The template is not a questionnaire, sales pipeline, universal real-estate ontology, or product-wide default for another profession. Through the Studio, Mauro can change how his space introduces him, what it knows, how it speaks, what it notices, what it can do, and when it should invite him into a conversation.

The Studio prepares a proposed change and shows Mauro its effect. Mauro decides when that change becomes active. Previous revisions remain recoverable.

When the professional explicitly asks, the private Studio can search the public web for current
information such as the professional's own website or public profiles. Studio cites the sources,
marks ambiguous identity matches, and treats the findings as untrusted evidence rather than
silently adding them to memory or configuration. The public assistant has no web-search capability
and continues to answer only from the professional's active configuration.

The same conversational control pattern can prepare professional correspondence. Mauro asks
Studio to write an email; Studio seals an exact, read-only artifact; Mauro either asks for another
version or explicitly authorizes that artifact. Replies return to the same private Studio context
as untrusted external content. This is not a conventional inbox or a third email agent.

The public assistant is the expression and proof of that configuration. It holds natural, persistent conversations in Italian using only Mauro's active space; it can work with text, voice notes, and photographs; maintain useful memory; surface corrections; and help Mauro understand where his attention may be valuable. Visitor information and conversations belong to Mauro's private account context, and Mauro can enter the same conversation without forcing the person through a separate handoff flow.

## What LAGGENTE is not

LAGGENTE is not Salesforce with an AI chat window. It does not ask the professional to maintain a pipeline, classify leads, update arbitrary stages, or perform data entry for the system.

Conversations are primary. Memory, summaries, signals, and possible opportunities are generated from them and remain inspectable and correctable. They are views that help the professional act, not administrative work imposed on the professional.

## Product language

The MVP is Italian-first. User-facing interface copy, seeded content, conversations, notifications, dates, and product tests use `it-IT`. Source code, identifiers, and technical documentation may remain in English.

Use `professional` in code and technical prose for the human professional. Avoid the bare word `agent` where it could be confused with an AI agent.

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
| Agent-native email | [Email activation runbook](docs/operations/AGENT_NATIVE_EMAIL.md) |
| Consent-qualified outreach | [Outreach activation runbook](docs/operations/CONSENT_QUALIFIED_OUTREACH.md) |
| AI collaboration | [ChatGPT Work and Codex](docs/workflows/CHATGPT_WORK_AND_CODEX.md) |
| Git workflow | [Development Workflow](docs/workflows/DEVELOPMENT_WORKFLOW.md) |
| Decisions | [Architecture Decision Records](docs/decisions/README.md) |

## Working principle

The repository is the durable source of truth. ChatGPT Work, Codex cloud, and local Codex are different working surfaces around the same project, not separate versions of it.

See [AGENTS.md](AGENTS.md) before making repository changes.

## Implemented pilot

The repository now contains a profession-agnostic LAGGENTE brand entry surface and the Mauro
real-estate pilot as one prominent tenant example inside the bespoke Vite/React single-page
interface. The API owns the opening Studio question and ordered, weighted vertical priorities;
tenant active configuration owns the actual public role. Vite produces static assets during the gateway image build; the existing internal nginx
gateway serves those assets and proxies same-origin `/api/v1` REST endpoints to FastAPI. There is no
Node.js web process in the production runtime. Exactly two OpenAI Agents SDK definitions power the
private Studio assistant and the public assistant. PostgreSQL remains the application-owned source
of truth for tenant-scoped configuration, conversations, messages, correctable memory, attachments,
sealed professional email artifacts, and audit events.

The agent-native email application path is implemented behind the production-safe
`AGENT_MAIL_ENABLED=false` default. Live provider activation and acceptance evidence are tracked
separately in the [email activation runbook](docs/operations/AGENT_NATIVE_EMAIL.md); source code by
itself is never proof of the current production state.

The implemented pilot can provision additional professional spaces through verified self-service
email entry or an authorized Studio invitation. Unknown addresses receive a short-lived pre-tenant
proof; the account and private Studio are created only after verification. Unpublished tenants
cannot resolve publicly; slug selection is globally checked and first publication requires both a
claimed slug and an explicitly activated configuration. Shared Studio, public-space, conversation,
media, and takeover code reads the resolved tenant and contains no Mauro-specific runtime fallback.

The Studio also exposes a bounded `/studio/grafo` view: it connects the
professional to existing conversations and to backend-weighted, correctable sets derived from them.

An optional, disabled-by-default Studio outreach capability can combine explicit public-web
research with the existing sealed-email contract. A public source nominates at most five pilot
candidates but never authorizes contact. Promotional delivery requires a professional-recorded
consent basis or the narrow existing-customer/similar-service exception, an exact sealed bundle,
human authorization, a privacy link, unsubscribe, and suppression checks. This is a bounded action,
not a CRM pipeline or a bulk cold-email system.

Conversation turns currently use durable, non-streaming request/response transport. ChatKit is
not part of the implemented runtime or persistence contract. See
[ADR-0001](docs/decisions/0001-single-hetzner-server.md).

## Current status

- Product blueprint: profession-agnostic open-entry multi-tenant proof 0.5.
- Seeded pilot professional: Mauro; additional professionals verify an email or use a curated invitation.
- Product audience: human professionals whose work depends on relationships, competence, and trust.
- First weighted vertical and pilot cohort: five real-estate professionals.
- Initial real-estate template: conversations with people considering selling a property.
- Relationship graph: tenant-private navigation over conversations and derived sets; no address-book import.
- Studio outreach: sourced five-recipient pilot packs; no send from public contact data alone.
- Hosting decision: one existing Hetzner server for the MVP.
- Repository phase: implemented MVP pilot application and production infrastructure; release checks and
  live deployment state must still be reported separately from repository state.
