# ADR-0003: Agent-Native Professional Email Through Sealed Artifacts

- **Status:** Accepted
- **Date:** 2026-08-23

## Context

LAGGENTE should let a professional use an address such as `mauro@laggente.com` without recreating
a conventional inbox or composer. The professional should be able to ask the existing private
Studio assistant to prepare correspondence and understand replies while retaining exact authorship
control. Operating a public SMTP service would add reputation, abuse, queue, bounce, complaint,
and security work that is not differentiated product value.

## Decision

Represent each professional email as a tenant-scoped, immutable artifact in PostgreSQL. Studio may
create a sealed outbound draft and inspect correspondence through typed tools, but it cannot send.
An authenticated professional must explicitly authorize the exact stored artifact. The application
then sends its stored RFC 822 bytes through a replaceable transport. The first production transport
is Amazon SES; local and automated tests use a capture transport that clearly reports simulation.

Use `mauro@laggente.com`-style sender addresses and a separate reply-routing domain such as
`inbound.laggente.com`. The separate MX boundary preserves any existing root-domain mail routing.
SES receipt rules store raw incoming mail in a private S3 bucket. A small AWS relay fetches the raw
object and posts it to LAGGENTE's HMAC-authenticated inbound endpoint. FastAPI resolves the
recipient local part to a space, retains the raw bytes and digest, and adds a system event to the
private Studio conversation.

Incoming email is untrusted content. Receipt does not call a model, execute a tool, disclose data,
or send an automatic reply. If Studio later inspects a received message, its tool result explicitly
labels the body as quoted external data.

The application capability remains disabled by default. Repository support is not evidence of an
AWS account, verified domain, production migration, DNS change, or live delivery.

## Consequences

### Positive

- the professional controls every exact outbound message;
- there is no editor state that can diverge from what is authorized;
- conversations remain the primary interface instead of adding an inbox workflow;
- SES owns SMTP delivery and reputation mechanics while LAGGENTE owns product semantics;
- transport state is inspectable and auditable without creating a third AI role;
- a dedicated reply domain avoids replacing the root domain's MX records.

### Negative

- SES account setup, production access, DKIM, custom MAIL FROM, DNS, bounce/complaint handling,
  S3 receipt storage, and the relay remain operational requirements;
- SES can accept a message without guaranteeing recipient delivery, so `sent` means provider
  acceptance rather than human receipt;
- an ambiguous provider failure cannot be retried automatically without duplicate-delivery risk;
- static IAM credentials are required on the current Hetzner topology and must be narrowly scoped,
  stored only in the API secret file, and rotated.

## Alternatives considered

- **Operate SMTP directly:** rejected for the pilot because abuse and deliverability operations are
  disproportionate to the product.
- **Expose a conventional mailbox UI:** rejected because it duplicates generic email software and
  breaks the conversation-primary thesis.
- **Let Studio send directly:** rejected because model intent is not human authorization.
- **Use Resend or Postmark for professional mail:** viable future transports, but SES supports the
  selected outbound and raw inbound path without changing the application artifact contract.
