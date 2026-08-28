# ADR-0006: Consent-Qualified Studio Outreach

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

LAGGENTE needs a first-party way to research a small set of professionals who may want a personal
space and to prepare a link-sharing campaign through the existing private Studio and sealed-email
system. Public web search and outbound email already exist as separate primitives, but combining
them naively would create an external-contact database and an automated cold-email system.

For Italian promotional email, an address being public is not permission to use it. The Italian
Garante has reiterated that promotional email normally requires consent, that accepting a
professional-network connection is not consent, and that legitimate interest cannot replace the
specific email rule. The narrow exception is an address obtained from an existing customer in the
context of a completed sale for the sender's own similar products or services. See the Garante's
[14 May 2026 decision](https://www.garanteprivacy.it/web/guest/home/docweb/-/docweb-display/docweb/10262105),
its [anti-spam guidelines](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/2542348),
and Article 13 of the
[ePrivacy Directive](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32002L0058).

## Decision

Add one bounded outreach capability to the existing private Studio assistant and application
coordination layer. It does not add an AI role.

- Studio may use its explicit public-web research tool to nominate a maximum of five sourced
  candidates in one pilot campaign.
- Every candidate retains a visible HTTPS source and expires after 30 days while it remains
  research-only.
- Public availability, a social connection, role similarity, inferred interest, or a purchased
  list never makes a candidate sendable.
- Delivery requires the professional to record one exact basis for one exact recipient:
  `explicit_consent` or `existing_customer_similar_services`, with a concrete evidence note tied to
  the current authenticated professional message.
- Each outreach email is an immutable professional-email artifact. It must contain the campaign's
  LAGGENTE link; the application adds a privacy link and an opaque, high-entropy unsubscribe token.
- When every recipient has a qualified basis and sealed artifact, the professional may authorize
  the exact bundle once. Studio cannot authorize it, individual email authorization cannot bypass
  the bundle, and an ambiguous failure is never retried automatically.
- Signed unsubscribe requests and provider bounce, suppression, or complaint events create
  tenant-scoped suppression state that blocks later preparation for the same address.
- The capability is disabled by default through `OUTREACH_ENABLED=false`. Its pilot cap is
  independently configured by `OUTREACH_MAX_RECIPIENTS`, with a hard maximum of 20 in code and a
  default of five.

Campaign and recipient statuses describe only research, permission, sealed-artifact preparation,
and delivery execution. They are not lead stages, a sales pipeline, identity proof, or a general
contact lifecycle. Conversations remain primary inside the product.

## Consequences

### Positive

- LAGGENTE can use its own Studio, web research, personal links, and sealed mail contract for a
  reviewable first growth loop.
- Research provenance, permission evidence, exact message hashes, human authorization,
  unsubscribe, suppression, and provider outcomes are inspectable.
- The capability remains profession-agnostic even when the first campaign targets real-estate
  professionals.
- A public-source candidate cannot silently cross into a sendable state.

### Negative

- A cold list found on the web will remain research-only and cannot be emailed through this path.
- Permission evidence is a professional attestation; LAGGENTE records and gates it but does not
  independently prove an offline conversation or customer sale.
- The five-recipient cap and two campaign authorizations per hour are deliberately too small for a
  high-volume marketing operation.
- Complete production use still needs an operator-reviewed privacy notice, lawful acquisition
  process, live provider/domain checks, and a controlled acceptance campaign.

## Alternatives considered

- **Automatically scrape and cold-email public business addresses:** rejected because public
  availability is not email-marketing permission and the resulting system would create avoidable
  privacy, spam, reputation, and product-integrity risk.
- **Treat legitimate interest as the email-delivery basis:** rejected for this Italian pilot because
  the specific electronic-marketing rule requires consent except for the narrow existing-customer
  exception.
- **Use a generic CRM campaign system:** rejected because LAGGENTE needs a bounded conversational
  action, not professional-maintained lead stages or a second source of truth.
- **Send every email through the existing single-artifact button:** rejected because it obscures the
  exact cohort and allows a campaign email to bypass bundle-level review.
