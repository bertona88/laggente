# Repository Instructions for Coding Agents

This file governs work performed by Codex and other coding agents in this repository.

## Product invariant

LAGGENTE is a personal agentic space for a human professional. Its simplest complete shape is:

```text
human professional ↔ private Studio assistant
                              ↕
                    shared persistent space
                              ↕
visitor ↔ public assistant ↔ human professional when they join
```

There are two conversational AI roles and one ordinary application coordination layer. Do not invent a third coordinating agent or an accidental multi-agent swarm.

The product foundation is profession-agnostic. The Studio learns what the professional does before specializing the space. The first and highest-weighted commercial template helps Mauro receive people who may be considering selling a property. It is a prominent starting configuration for the pilot, not the identity of LAGGENTE, a universal sales pipeline, a mandatory questionnaire, or a permanent product ontology.

Product positioning, the opening Studio question, and ordered/weighted vertical examples are backend-owned configuration. Frontends render that contract and must not hardcode real estate as the universal fallback. A tenant's active configuration remains authoritative for their public role and behavior.

LAGGENTE is not a CRM that makes the professional maintain leads, stages, fields, and statuses. Conversations are primary. The system may derive correctable memory, summaries, signals, and suggested next actions from those conversations without turning that derived material into administrative work for the professional.

The product behavior is agentic. The control boundaries are deterministic:

- assistants may converse, interpret, propose, organize, and use authorized tools;
- the application owns persistence, identity, tenant isolation, permissions, activation of public configuration, AI disclosure, file access, and control of automatic replies;
- generated interpretations must remain inspectable and correctable;
- the human professional retains judgment and responsibility.

The MVP is Italian-first. User-visible copy, seeded conversations, notifications, locale behavior, and product acceptance tests use `it-IT`. Code identifiers and technical documentation may remain in English.

## Read before implementation

Before changing product behavior or architecture, read:

1. `README.md`;
2. `docs/vision/PRODUCT_VISION.md`;
3. `docs/blueprints/LAGGENTE_BLUEPRINT_MVP.md`;
4. `docs/product/MVP_SCOPE.md`;
5. `docs/architecture/SYSTEM_ARCHITECTURE.md`;
6. the relevant ADRs under `docs/decisions/`.

## Current repository phase

The repository contains the explicitly authorized MVP pilot implementation and its infrastructure.
Product behavior, architecture, and operations changes must remain reviewable through repository
files and the governing documents below.

Do not add placeholder applications, speculative services, integrations, configuration, or future
CRM concepts merely because they may be useful later.

## Architectural guardrails

- The MVP runs on the existing Hetzner server.
- Do not introduce Vercel, Railway, Redis, Kubernetes, or a managed database without an explicit decision that replaces ADR-0001.
- Use Docker Compose with the existing nginx gateway serving the Vite/React static build and proxying same-origin `/api/v1`, plus the FastAPI agent service, PostgreSQL, private filesystem uploads, and backups.
- Use one application deployment for every professional subdomain.
- Resolve the tenant from the hostname, but enforce `account_id` in every server-side authorization decision and database query.
- Keep persistent conversations and messages as primary records.
- Treat memory, summaries, signals, and suggested opportunities as derived and correctable unless a later requirement proves that they need independent lifecycles.
- Do not introduce a conventional CRM pipeline or speculative lead taxonomy into the MVP.
- A tenant-private relationship graph may derive bounded, correctable sets from that tenant's own conversations and inspectable memory. It is a navigation view over primary records, not proof of identity, a hidden score, or a CRM lifecycle.
- Do not introduce address-book import, external contact enrichment, or cross-account clustering without an explicit authorized data source, consent/privacy design, and a decision that expands scope.
- Keep professional space configuration document-shaped and extensible inside a typed platform-owned envelope. Do not force identity, knowledge, style, examples, or ways of working into a closed onboarding schema merely because fixed fields are easier to implement.
- Tenant configuration can shape content, behavior, presentation, memory preferences, and available capabilities, but cannot override platform identity, safety, privacy, permissions, or human control.
- Changes proposed by the private Studio assistant do not affect the public assistant until the professional explicitly activates them.
- The OpenAI API key stays server-side.
- Do not store private chain-of-thought.
- Do not claim integrations that are not implemented.

## AI roles in the product

Implement only the two bounded assistants required by the MVP unless a later decision authorizes more:

1. **Private Studio assistant** — talks with the authenticated professional and modifies the professional's space through typed, authorized capabilities.
2. **Public assistant** — talks with visitors using the active configuration of that professional's space.

The coordination layer between them is application code and persistent data, not another AI role.

## Work allocation

- **ChatGPT Work:** product reasoning, specifications, research, documentation, design review, backlog definition, and repository changes that can be reviewed through Git.
- **Codex cloud:** bounded implementation, tests, refactors, code review, and feature branches in a reproducible repository environment.
- **Local Codex:** Hetzner, Namecheap, DNS, SSH, secrets, local Docker, browser/audio hardware tests, operational diagnosis, and controlled deployment.

No surface owns undocumented project state. Record durable decisions in the repository.

## Git and delivery rules

- Work on a feature branch unless explicitly instructed otherwise.
- Inspect the current branch and working tree before editing.
- Preserve unrelated user changes.
- Keep commits focused and descriptive.
- Run the checks defined by the implemented repository before committing.
- When a remote is configured and a commit is created, push that exact commit before ending the task.
- Report the remote branch and full commit SHA.
- Do not merge, deploy production, change DNS, or run production migrations without explicit authorization.
- Infrastructure changes must be encoded in the repository wherever possible; avoid undocumented manual server state.

## Documentation maintenance

Update the relevant document when a task changes scope, architecture, operations, or an accepted decision. Create a new ADR only when reversing or materially altering an architectural choice that is difficult to undo and has real alternatives.
