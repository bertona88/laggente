# LAGGENTE Documentation

This directory is the durable project map. The governing product shape is two conversational assistants around one persistent professional space. Product documents describe the agentic experience; architecture and operations documents define the deterministic boundaries that keep it trustworthy.

## Reading order

1. [Product Vision](vision/PRODUCT_VISION.md)
2. [Current MVP Blueprint](blueprints/LAGGENTE_BLUEPRINT_MVP.md)
3. [MVP Scope](product/MVP_SCOPE.md)
4. [System Architecture](architecture/SYSTEM_ARCHITECTURE.md)
5. [Architecture Decision Records](decisions/README.md)
6. [ChatGPT Work and Codex](workflows/CHATGPT_WORK_AND_CODEX.md)

## Directory structure

| Directory | Purpose |
| --- | --- |
| `vision/` | Enduring thesis, positioning, and principles |
| `product/` | Current product shape and experience |
| `blueprints/` | Current long-form product blueprint and build direction |
| `architecture/` | Current system boundaries and technical shape |
| `decisions/` | Architecture Decision Records (ADRs) |
| `operations/` | Hosting, domains, deployment, backup, and runtime responsibilities |
| `workflows/` | How humans, ChatGPT Work, Codex, GitHub, and the server interact |

## Source-of-truth rule

When documents disagree, use this precedence:

1. explicit current user instruction;
2. accepted ADRs;
3. current MVP scope;
4. system architecture;
5. current blueprint;
6. exploratory notes.

An ADR can intentionally replace part of the current blueprint. When this happens, the ADR must state what it supersedes.
