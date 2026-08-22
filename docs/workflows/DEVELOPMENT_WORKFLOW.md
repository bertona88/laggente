# Development Workflow

## Repository state

The repository begins with documentation only. Application code is added when an explicit milestone task authorizes it.

## Branches

- Use short-lived feature branches.
- Keep the default branch releasable.
- Do not push feature work directly to the default branch.
- Do not mix product documentation, unrelated refactors, and infrastructure changes in one commit without a clear reason.

Suggested branch patterns:

```text
docs/project-foundation
feat/milestone-a-tenant-resolution
feat/builder-publish-loop
fix/account-isolation
ops/hetzner-bootstrap
```

## Change sequence

1. Read `AGENTS.md` and the relevant project documents.
2. Inspect the current branch, status, and recent changes.
3. State the bounded result and acceptance criteria.
4. Make the smallest coherent change.
5. Run relevant checks.
6. Review the diff for accidental scope.
7. Commit with a clear message.
8. Push the exact commit to the remote feature branch.
9. Report the branch, full SHA, checks, and any blocker.

## Pull requests

A pull request should explain:

- what user or operator outcome changed;
- why the change belongs in the current milestone;
- important architecture or security implications;
- tests performed;
- screenshots or recordings when UI or audio behavior changed;
- deployment and migration notes;
- remaining limitations.

Opening, merging, or deploying a pull request is a separate action from creating and pushing its branch.

## Documentation requirements

Update documentation in the same change when implementation alters:

- product scope or acceptance criteria;
- system boundaries or data ownership;
- tenant isolation or security behavior;
- deployment and rollback procedures;
- environment variables or operational dependencies;
- an accepted architecture decision.

## Environments

- Local and automated tests use synthetic data.
- Staging is isolated from production.
- Production secrets stay outside Git.
- Preview environments must not send real notifications or mutate production data.
- Database migrations are versioned and tested before production execution.

## Release principle

Publishing a professional configuration is a product operation. Deploying application code is an engineering operation. Never couple the two unnecessarily.

