# ADR-0004: Open Professional Entry with Pre-Tenant Email Verification

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

The invitation-only pilot made the Studio entry page look available while silently withholding an
email from unknown addresses. That anti-enumeration behavior was secure but operationally opaque,
and real first-use evidence showed that a professional could reasonably believe they had signed up
even though no account, link, or provider request existed.

Opening signup directly at request time would let automated traffic allocate accounts, Studio
threads, and placeholder spaces for unverified addresses. Public entry therefore needs to become
open without weakening tenant ownership, one-time authentication, or explicit publication.

## Decision

Use one email-first entry form for both new and returning professionals.

- A returning professional receives the existing purpose-bound login link.
- An unknown or not-yet-accepted address receives a distinct, short-lived signup proof.
- The signup proof is stored before any tenant exists and is transported in a URL fragment.
- Only consuming that proof creates or unlocks the private account, non-inviting member, Studio
  conversation, and inactive placeholder space.
- Signup, invitation, and login tokens retain distinct signed and durable purposes.
- Consuming one signup proof invalidates sibling proofs for the same address.
- Email- and IP-scoped request limits apply before delivery; expired pre-tenant proofs are removed
  automatically shortly after they can no longer be used.
- Authorized Studio invitations remain available for curated onboarding, but are optional.
- Slug claim and explicit configuration activation remain mandatory before public resolution.

## Consequences

### Positive

- a professional can start without coordination from an existing pilot member;
- the interface can truthfully say that an access or signup email was sent;
- automated requests do not allocate tenant data before email ownership is proven;
- new and returning professionals use one understandable entry surface;
- invitation authority and public activation controls remain intact.

### Negative

- the public endpoint can generate provider traffic and requires abuse monitoring;
- the application stores a bounded amount of unverified email data until automatic expiry cleanup;
- rate limits in the current single API process reset on restart, so sustained abuse may later
  justify persistent or edge-level enforcement;
- public signup increases the importance of capacity, suppression, and complaint monitoring.

## Alternatives considered

- **Keep invitation-only entry:** rejected after first-use evidence showed a misleading dead end.
- **Create a tenant when an email is submitted:** rejected because unverified traffic could create
  durable account and conversation pressure.
- **Use an unsigned or replayable email link:** rejected because authentication and account creation
  must remain single-use, expiring, and application-owned.
- **Make every new member an inviter:** rejected because invitation authority is a separate platform
  permission and must not propagate through signup.
