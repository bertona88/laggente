# LAGGENTE Documentation

This directory is the durable project map. It separates enduring vision, current MVP commitments, architectural decisions, operations, and working procedures so that future conversations do not have to reconstruct the project from memory.

## Reading order

1. [Product Vision](vision/PRODUCT_VISION.md)
2. [MVP Scope](product/MVP_SCOPE.md)
3. [Founding MVP Blueprint](blueprints/LAGGENTE_BLUEPRINT_MVP.md)
4. [System Architecture](architecture/SYSTEM_ARCHITECTURE.md)
5. [Milestones](roadmap/MILESTONES.md)
6. [Architecture Decision Records](decisions/README.md)
7. [ChatGPT Work and Codex](workflows/CHATGPT_WORK_AND_CODEX.md)

## Directory structure

| Directory | Purpose |
| --- | --- |
| `vision/` | Enduring thesis, positioning, and principles |
| `product/` | Current product scope and definition of done |
| `blueprints/` | Long-form founding and build documents |
| `architecture/` | Current system boundaries and technical shape |
| `decisions/` | Architecture Decision Records (ADRs) |
| `roadmap/` | Ordered delivery milestones and evidence gates |
| `operations/` | Hosting, domains, deployment, backup, and runtime responsibilities |
| `workflows/` | How humans, ChatGPT Work, Codex, GitHub, and the server interact |

## Source-of-truth rule

When documents disagree, use this precedence:

1. explicit current user instruction;
2. accepted ADRs;
3. current MVP scope;
4. system architecture;
5. founding blueprint;
6. exploratory notes.

An ADR can intentionally replace part of the founding blueprint. When this happens, the ADR must state what it supersedes.

