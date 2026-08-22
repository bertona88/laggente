# Architecture Decision Records

Architecture Decision Records capture choices that materially constrain implementation or operations. They prevent future agents and contributors from silently reopening settled decisions.

## Status meanings

- **Proposed** — under discussion and not yet binding.
- **Accepted** — current project decision.
- **Superseded** — replaced by a later ADR.
- **Rejected** — considered and deliberately not chosen.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-single-hetzner-server.md) | Accepted | Run the MVP on the existing Hetzner server |
| [0002](0002-wildcard-subdomain-tenancy.md) | Accepted | Use wildcard hostname-based tenancy with one deployment |
| [0003](0003-agent-native-professional-email.md) | Accepted | Use sealed email artifacts and a replaceable SES transport |

## Creating a new ADR

Use the next sequential number and include:

- context;
- decision;
- consequences;
- alternatives considered;
- what earlier document or ADR is superseded, if applicable.
