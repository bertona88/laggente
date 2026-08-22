# LAGGENTE

> The agentic operating system for real estate.

LAGGENTE gives every real-estate professional a living digital branch office: a public AI presence that understands how the professional works, receives homeowners immediately, qualifies opportunities, and brings the human into the conversation when judgment or responsibility is required.

The first product loop is deliberately narrow and commercially complete:

> conversation → qualification → valuation request → dossier → human takeover

This repository currently contains the project direction and operating documentation. It intentionally contains **no application scaffold yet**. Product code and infrastructure will be introduced only through explicit implementation milestones.

## The first product

The pilot begins with Mauro and expands to five real-estate agents. Each professional has two surfaces:

- `app.laggente.com` — the private LAGGENTE Studio, where the professional configures the public agent by talking;
- `<slug>.laggente.com` — the public digital branch office, beginning with `mauro.laggente.com`.

The professional can change tone, required questions, approved knowledge, and handoff rules through conversation. The change follows:

> Draft → Preview → Approve → Publish

Publishing activates a versioned configuration in the database. It does not deploy new code or create new infrastructure for each professional.

## Documentation map

Start with the [documentation index](docs/README.md).

| Area | Document |
| --- | --- |
| Founding blueprint | [LAGGENTE MVP Blueprint](docs/blueprints/LAGGENTE_BLUEPRINT_MVP.md) |
| Product thesis | [Product Vision](docs/vision/PRODUCT_VISION.md) |
| First build | [MVP Scope](docs/product/MVP_SCOPE.md) |
| System shape | [System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) |
| Delivery plan | [Milestones](docs/roadmap/MILESTONES.md) |
| Hosting | [Hetzner Deployment](docs/operations/HETZNER_DEPLOYMENT.md) |
| Domains | [Domains and Subdomains](docs/operations/DOMAINS_AND_SUBDOMAINS.md) |
| AI collaboration | [ChatGPT Work and Codex](docs/workflows/CHATGPT_WORK_AND_CODEX.md) |
| Git workflow | [Development Workflow](docs/workflows/DEVELOPMENT_WORKFLOW.md) |
| Decisions | [Architecture Decision Records](docs/decisions/README.md) |

## Working principle

The repository is the durable source of truth. ChatGPT Work, Codex cloud, and local Codex are different working surfaces around the same project—not separate versions of the project.

- ChatGPT Work develops product direction, specifications, research, review material, and durable documentation.
- Codex cloud works on bounded repository tasks and returns reviewable Git changes.
- Local Codex owns machine-bound work: local integration, browser and microphone testing, Hetzner administration, Namecheap/DNS operations, secrets, and controlled deployments.
- GitHub carries decisions and implementation between all three.

See [AGENTS.md](AGENTS.md) before making repository changes.

## Current status

- Founding blueprint: draft 0.2
- Pilot professional: Mauro
- Pilot size: five real-estate agents
- First Playbook: seller qualification and valuation request
- Hosting decision: one existing Hetzner server for the MVP
- Repository phase: documentation foundation

