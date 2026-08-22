# Agent-Native Email Activation

## Current state

The repository implements sealed professional email artifacts, explicit human authorization, an
Amazon SES outbound transport, signed inbound ingestion, and a development capture transport.
`AGENT_MAIL_ENABLED=false` is the production-safe default. Nothing in this implementation creates
an AWS account, changes DNS, runs the migration, deploys the branch, or makes email live.

## Target flow

```text
Mauro ↔ private Studio assistant
             ↓ sealed draft
      human authorization endpoint
             ↓ exact RFC 822 bytes
          Amazon SES → recipient

recipient reply → inbound.laggente.com MX → SES receipt rule → private S3
                                                       ↓
                                                signed AWS relay
                                                       ↓
                                       FastAPI inbound endpoint → Studio event
```

There are still exactly two AI roles. SES, S3, the relay, FastAPI, and PostgreSQL are ordinary
infrastructure and application code.

## What the AWS account owner must do

1. Finish AWS account signup and select the ordinary usage-based SES path; no optional fixed-price
   SES tier or SES Mail Manager subscription is required by this architecture.
2. In `eu-south-1`, verify the sender identity for `laggente.com`, publish the three SES DKIM CNAME
   records, and configure a custom MAIL FROM subdomain such as `bounce.laggente.com` with its SES MX
   and SPF records. Keep DMARC aligned through DKIM.
3. Request SES production access. State the real one-to-one professional correspondence use case,
   low pilot volume, explicit human authorization, and bounce/complaint suppression policy.
4. Create a dedicated IAM principal for the Hetzner API with only SES send permission in the chosen
   region. Provide its access-key ID and secret through the API-only application secret file; never
   paste them into Studio, source code, a browser, or a chat message.
5. Verify `inbound.laggente.com` as the receiving identity. Publish only that subdomain's SES inbound
   MX record. Do not replace the apex `laggente.com` MX records.
6. Create a private, encrypted S3 bucket with short lifecycle retention for raw inbound mail. Create
   an SES receipt rule limited to `inbound.laggente.com` that writes raw messages to that bucket.
7. Deploy the versioned relay in [`infra/email-relay`](../../infra/email-relay/README.md) as a
   narrowly scoped Lambda that can read only that bucket prefix. It Base64-encodes the untouched raw
   message and POSTs `{recipient, receipt_id, raw_base64, received_at}` to
   `/api/v1/integrations/professional-email/inbound`. It signs the exact JSON bytes with
   `HMAC-SHA256(secret, timestamp + "." + body)` in `X-Laggente-Signature: sha256=...` and sends the
   Unix timestamp in `X-Laggente-Timestamp`.
8. Configure SES bounce and complaint events and a suppression procedure before pilot traffic.

## Values needed by LAGGENTE

Install these only in `/opt/laggente/secrets/application.env` with the existing restricted
ownership and permissions:

```dotenv
AGENT_MAIL_ENABLED=true
AGENT_MAIL_PROVIDER=ses
AGENT_MAIL_FROM_DOMAIN=laggente.com
AGENT_MAIL_REPLY_DOMAIN=inbound.laggente.com
AGENT_MAIL_AWS_REGION=eu-south-1
AGENT_MAIL_INBOUND_SECRET=<at-least-32-random-characters-shared-with-relay>
AGENT_MAIL_MAX_INBOUND_BYTES=5242880
AWS_ACCESS_KEY_ID=<dedicated-ses-sender-key-id>
AWS_SECRET_ACCESS_KEY=<dedicated-ses-sender-secret>
AWS_SESSION_TOKEN=
```

Do not enable the flag until DNS and SES identities read back correctly, production access is
approved, the database migration is complete, the relay signature test passes, and a controlled
outbound/reply round trip succeeds. Deployment and DNS changes require separate explicit approval.

## Acceptance checks

- a draft can be read but has no editable subject/body fields;
- asking for a modification supersedes the prior unapproved artifact;
- only an authenticated professional can authorize a tenant-owned outbound draft;
- reauthorizing a `sent` or `simulated` record does not submit it twice;
- provider failure is visible and is not retried automatically;
- a wrong, stale, or missing inbound signature is rejected;
- a duplicate receipt ID creates no duplicate email or Studio event;
- incoming content is marked untrusted and creates no model call or automatic reply;
- the apex MX records remain unchanged.
