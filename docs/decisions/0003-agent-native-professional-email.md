# ADR-0003: Agent-Native Professional Email Through Sealed Artifacts

- **Status:** Accepted
- **Date:** 2026-08-23
- **Amended:** 2026-08-23 — Resend is the pilot transport; SES is retained as the planned later
  transport.

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
then submits content derived only from that artifact through a replaceable transport. The pilot
production transport is Resend; local and automated tests use a capture transport that clearly
reports simulation. Resend accepts structured sender, recipient, reply-to, subject, body, and custom
header fields rather than raw RFC 822 bytes, so the adapter parses those fields from the sealed
artifact at authorization time and uses the artifact ID as its idempotency key. The stored artifact
and digests remain the application audit source.

Use `mauro@laggente.com`-style sender addresses. During the Resend pilot, replies use the
account-provided receiving domain and arrive through a signed `email.received` webhook. FastAPI
verifies the untouched Svix-signed body, retrieves the original raw message through Resend's
receiving API, resolves the recipient local part to a space, retains the raw bytes and digest, and
adds a system event to the private Studio conversation.

Retain the existing Amazon SES adapter and the `inbound.laggente.com` SES/S3 relay as the planned
later transport. That separate MX boundary avoids replacing root-domain mail routing when it can be
published. Switching providers is an operational configuration change, not a change to assistant
roles, authorization, tenancy, or the sealed-artifact contract.

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
- Resend currently owns SMTP delivery and receiving mechanics while LAGGENTE owns product semantics;
- transport state is inspectable and auditable without creating a third AI role;
- the pilot receiving domain avoids replacing the root domain's MX records;
- the SES implementation remains reviewable and tested for the planned later switch.

### Negative

- Resend domain verification, an API key, a webhook signing secret, delivery-event subscriptions,
  and suppression review remain operational requirements for the pilot;
- Resend does not accept raw RFC 822 content on its send endpoint, so provider-generated MIME is not
  byte-identical to the stored artifact even though the sealed authored fields are preserved;
- a provider can accept a message without guaranteeing recipient delivery, so `sent` means provider
  acceptance rather than human receipt;
- an ambiguous provider failure cannot be retried automatically without duplicate-delivery risk;
- the later SES path requires narrowly scoped static IAM credentials on the current Hetzner
  topology, private S3 receipt storage, and the signed relay.

## Alternatives considered

- **Operate SMTP directly:** rejected for the pilot because abuse and deliverability operations are
  disproportionate to the product.
- **Expose a conventional mailbox UI:** rejected because it duplicates generic email software and
  breaks the conversation-primary thesis.
- **Let Studio send directly:** rejected because model intent is not human authorization.
- **Use Amazon SES immediately:** retained as the planned later transport, but deferred because the
  pilot can use the already available Resend account and usage-based service without completing AWS
  account setup now.
- **Use Postmark for professional mail:** still a viable replaceable transport, but it adds another
  provider with no pilot need.
