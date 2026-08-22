# Repository Instructions for Coding Agents

This file governs work performed by Codex and other coding agents in this repository.

## Product invariant

LAGGENTE is not a generic chatbot, a chatbot widget, or a lightweight CRM. It is a digital branch office for a human real-estate professional.

The first complete commercial loop is:

> conversation → qualification → valuation request → dossier → human takeover

The North Star metric is qualified valuation appointments per agent per week. Optimize for completed commercial movement, not message count, token use, or feature count.

## Read before implementation

Before changing product behavior or architecture, read:

1. `README.md`;
2. `docs/blueprints/LAGGENTE_BLUEPRINT_MVP.md`;
3. `docs/product/MVP_SCOPE.md`;
4. `docs/architecture/SYSTEM_ARCHITECTURE.md`;
5. the relevant ADRs under `docs/decisions/`.

## Current repository phase

The repository is documentation-only until an explicit implementation task authorizes application code or infrastructure files.

Do not create framework scaffolds, placeholder applications, package manifests, Docker files, CI workflows, or speculative configuration merely because they may be useful later.

## Architectural guardrails

- The MVP runs on the existing Hetzner server.
- Do not introduce Vercel, Railway, Redis, Kubernetes, or a managed database without an explicit decision that replaces ADR-0001.
- Plan for Docker Compose with a reverse proxy, Next.js web application, FastAPI agent service, PostgreSQL, private uploads, and backups.
- Use one application deployment for every professional subdomain.
- Resolve the tenant from the hostname, but enforce `account_id` in every server-side authorization decision and database query.
- Tenant content can configure bounded behavior but cannot override platform identity, safety, privacy, permissions, or handoff policy.
- The OpenAI API key stays server-side.
- Do not store private chain-of-thought.
- Do not claim integrations that are not implemented.

## Agent roles in the product

Implement only the two bounded agents required by the MVP unless a later decision authorizes more:

1. **Private Builder** — edits validated draft configuration through typed, authorized tools.
2. **Public Concierge** — reads only published configuration and executes the Seller Playbook.

Avoid accidental multi-agent swarms.

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

Update the relevant document when a task changes scope, architecture, operations, or an accepted decision. Create a new ADR when reversing or materially altering an existing architectural choice.

