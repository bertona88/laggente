# Agent-Native Email Activation

## Current state

The repository implements sealed professional email artifacts, explicit human authorization, an
outbound Resend transport, signed Resend receiving and delivery-event ingestion, a development
capture transport, and the retained Amazon SES/S3 path for a later provider switch.
`AGENT_MAIL_ENABLED=false` remains the production-safe configuration default.

The Resend sending domain `laggente.com` is verified, and its DKIM, sending CNAME, and DMARC records
have been published without changing the apex Namecheap forwarding records. Namecheap's
`EmailType=FWD` API mode did not retain a custom subdomain MX, so the safe pilot reply domain is the
Resend-provided
`aldioprena.resend.app`; `inbound.laggente.com` remains reserved for the later SES path.

Repository support and DNS records alone are not evidence that the database migration ran, a branch
was deployed, a Resend API key or webhook was created, the feature was enabled, or live delivery
passed. Use the dated record below and refresh it after every release.

## Live pilot record — 2026-08-23

- production release `24a4b41b2f1738d6613623e590e8275cc6b4638b` runs both the agent-native
  email and invited-professional onboarding migrations, with `AGENT_MAIL_PROVIDER=resend` and
  `AGENT_MAIL_ENABLED=true`;
- pre-migration backup `20260824T002401Z` and post-release backup `20260824T002711Z` completed and
  passed the repository audit;
- the `laggente.com` sending domain is verified; the restricted server secret file contains the
  Resend API key and webhook signing secret;
- webhook `c82233db-e4ee-4db6-8aa7-c09808a5f2d2` is enabled at the production endpoint for
  `email.received`, `email.delivered`, `email.delivery_delayed`, `email.bounced`,
  `email.complained`, `email.failed`, and `email.suppressed`; an unsigned request is rejected with
  HTTP 401;
- provider-only delivery `c8e3c230-18b2-4b35-a706-c55d0180f11d` from
  `accesso@laggente.com` reached the controlled recipient.

Deployment, migrations, public smoke checks, and provider configuration are accepted. Complete
human product acceptance still requires an explicitly selected invitation recipient and a
controlled onboarding magic-link plus sealed Studio outbound/reply round trip; do not create a
disposable production tenant merely to make that claim.

## Target flow

```text
Mauro ↔ private Studio assistant
             ↓ sealed draft
      human authorization endpoint
             ↓ sealed fields + idempotency key
             Resend → recipient

recipient reply → aldioprena.resend.app → signed Resend email.received webhook
                                                   ↓
                                      Resend raw-message retrieval
                                                   ↓
                                      FastAPI ingestion → Studio event
```

There are still exactly two AI roles. Resend, FastAPI, and PostgreSQL are ordinary infrastructure
and application code. Incoming content is stored as untrusted data and does not cause a model call,
tool call, or automatic reply.

## Resend pilot activation

1. Deploy this branch with the database migration while `AGENT_MAIL_ENABLED=false`.
2. Create one server-side Resend API key with full access. Full access is required because the same
   pilot key sends mail and calls `GET /emails/receiving/{id}` to obtain the signed raw-message URL.
   Store it only in the restricted Hetzner application secret file; never commit or expose it to a
   browser client.
3. Configure production with the values below. `FROM_EMAIL` is used for magic links; the professional
   sender address is derived per tenant from `AGENT_MAIL_FROM_DOMAIN`.
4. Add a Resend webhook pointing to
   `https://app.laggente.com/api/v1/integrations/professional-email/resend`. Copy its distinct signing
   secret to `RESEND_WEBHOOK_SECRET`. Subscribe to `email.received`, `email.delivered`,
   `email.delivery_delayed`, `email.bounced`, `email.complained`, `email.failed`, and
   `email.suppressed`. Create or expand the webhook only after the matching endpoint is deployed, so
   the provider does not retry a missing route.
5. Restart the API, confirm readiness, then enable `AGENT_MAIL_ENABLED=true` and perform a controlled
   outbound/reply round trip. Verify the stored provider IDs, raw hashes, one Studio event, and no
   automatic assistant reply.
6. Exercise the bounce/complaint suppression procedure below before pilot traffic expands.

## Bounce, complaint, and suppression procedure

Resend automatically suppresses addresses after a hard bounce or complaint across the account's
region. The signed delivery events update the matching sealed professional artifact and add a
tenant-scoped Studio notice without retrying or asking an assistant to act. Transactional login and
invitation emails are not professional artifacts; Resend's suppression list remains authoritative
for those addresses.

1. Inspect the email event and the account-level suppression entry in Resend.
2. Do not retry an ambiguous failure or remove a suppression merely to force delivery.
3. Correct a typo or obtain a replacement address through the human professional.
4. Remove a suppression only after its underlying cause is resolved and the professional explicitly
   intends to contact that recipient again.
5. Send a newly authorized artifact; never reuse or mutate the old sealed email.

Resend documents the event payloads in its
[webhook event reference](https://resend.com/docs/webhooks/event-types) and the region-wide behavior
in [Email Suppressions](https://resend.com/docs/dashboard/emails/email-suppressions).

## Values needed by LAGGENTE

Install these only in `/opt/laggente/secrets/application.env` with the existing restricted
ownership and permissions:

```dotenv
AGENT_MAIL_ENABLED=true
AGENT_MAIL_PROVIDER=resend
AGENT_MAIL_FROM_DOMAIN=laggente.com
AGENT_MAIL_REPLY_DOMAIN=aldioprena.resend.app
AGENT_MAIL_MAX_INBOUND_BYTES=5242880
RESEND_API_KEY=<full-access-server-side-key>
RESEND_WEBHOOK_SECRET=<signing-secret-for-the-email-received-webhook>
FROM_EMAIL=LAGGENTE <accesso@laggente.com>
```

Do not enable the flag until the sending domain is verified, the database migration is complete,
the webhook signature path passes, and a controlled outbound/reply round trip succeeds. Deployment
still requires separate explicit approval.

## Planned later switch to Amazon SES

The SES adapter and [`infra/email-relay`](../../infra/email-relay/README.md) remain implemented and
tested. A later switch sets `AGENT_MAIL_PROVIDER=ses` and `AGENT_MAIL_REPLY_DOMAIN=inbound.laggente.com`,
then supplies `AGENT_MAIL_AWS_REGION`, a 32-character `AGENT_MAIL_INBOUND_SECRET`, and dedicated
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` credentials. Before switching, complete SES production
access, DKIM and custom MAIL FROM, the `inbound.laggente.com` MX boundary, private encrypted S3
receipt storage with short retention, the signed relay, and bounce/complaint handling. Do not alter
the apex forwarding MX records.

The switch changes transport configuration only. It does not change the two assistant roles, human
authorization, immutable artifact, tenant isolation, inbound distrust, or no-automatic-retry rules.

## Acceptance checks

- a draft can be read but has no editable subject/body fields;
- asking for a modification supersedes the prior unapproved artifact;
- only an authenticated professional can authorize a tenant-owned outbound draft;
- reauthorizing a `sent` or `simulated` record does not submit it twice;
- provider failure is visible and is not retried automatically;
- delivered, delayed, bounced, complained, failed, and suppressed Resend events update the sealed
  artifact monotonically and duplicate events create no duplicate Studio notice;
- a wrong, stale, or missing inbound signature is rejected;
- a duplicate receipt ID creates no duplicate email or Studio event;
- incoming content is marked untrusted and creates no model call or automatic reply;
- the apex MX records remain unchanged.
