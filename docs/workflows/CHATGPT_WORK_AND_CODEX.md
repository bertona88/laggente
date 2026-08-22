# ChatGPT Work and Codex

## One project, several working surfaces

ChatGPT Work, Codex cloud, and local Codex should not maintain separate mental copies of LAGGENTE. GitHub and the documentation in this repository are the handoff protocol.

```text
ChatGPT Work
  product direction, specifications, research, review
        ↓ durable docs and bounded tasks
GitHub repository
  source, history, decisions, branches, pull requests
        ↓ reproducible implementation
Codex cloud
  code, tests, refactors, reviewable diffs
        ↓ machine-bound execution
Local Codex
  local integration, Hetzner, Namecheap, DNS, secrets, deployment
```

## ChatGPT Work owns

- developing and challenging the product thesis;
- converting conversations and source material into durable specifications;
- maintaining the blueprint, product documents, ADR drafts, and decision context;
- researching current APIs, regulations, product choices, and tradeoffs;
- producing reviewable repository changes when GitHub is connected;
- reviewing implementation against product intent;
- preparing pilot material, reports, and decision briefs.

ChatGPT Work may implement repository tasks, but an ephemeral workspace is never the source of truth. Completed Git work must be pushed before the task ends.

## Codex cloud owns

- bounded implementation tasks against a connected repository;
- tests, refactors, migrations, and documentation coupled to code;
- pull-request review and CI diagnosis;
- work that benefits from a clean reproducible environment;
- feature branches that are ready for human review.

Codex cloud should use repository instructions and staging or synthetic resources. It should not require production secrets to perform ordinary development.

## Local Codex owns

- inspecting and operating the existing Hetzner server;
- Namecheap and DNS changes;
- SSH and deployment credentials;
- production environment variables and secret rotation;
- local Docker and database integration;
- browser tests against localhost;
- microphone, audio, and device-specific testing;
- production logs and container diagnosis;
- explicitly authorized deployment and migration execution.

Local access is capability, not standing permission. DNS, production deploys, destructive operations, and production migrations still require explicit authorization.

## Handoff pattern

### From conversation to repository

1. ChatGPT Work turns the decision into an MVP update, ADR, issue description, or acceptance criteria.
2. The change is committed on a feature branch.
3. The remote branch and full SHA are reported.

### From repository to implementation

1. Codex reads `AGENTS.md` and the relevant documents.
2. It confirms the bounded outcome and current repository state.
3. It implements the smallest complete vertical change.
4. It runs the required checks.
5. It pushes a feature branch and reports the SHA.

### From implementation to server

1. Local Codex checks the approved commit or release.
2. It inspects the current server state and proposed diff.
3. It performs the explicitly authorized deployment steps.
4. It runs health and smoke tests.
5. It records operational changes that must remain reproducible.

## Task-writing template

Every substantial implementation task should state:

- desired user-visible outcome;
- relevant documents and decisions;
- in-scope behavior;
- explicitly excluded behavior;
- acceptance criteria;
- required tests;
- whether external systems or credentials are required;
- whether deployment is authorized.

## Context rule

Do not rely on a chat saying “we decided this.” If a decision matters to future implementation, write it into the repository.
