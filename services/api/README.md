# LAGGENTE API

FastAPI service for LAGGENTE's application-owned coordination layer and exactly two OpenAI
Agents SDK roles: the private Studio assistant and the public assistant. PostgreSQL stores
tenant-scoped spaces, active/draft configuration revisions, conversations, immutable messages,
correctable derived memory, attachments, sealed professional email artifacts, and audit events.

## Local run

```bash
cd services/api
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
```

In development `AUTO_CREATE_SCHEMA=true` can create the schema automatically. Production must
set it to `false` and run Alembic before starting the service.

## Required production environment

- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg://...`
- `SESSION_SECRET` (at least 32 random characters)
- `AUTH_MODE=pilot_password` with `PILOT_EMAIL` and a `PILOT_PASSWORD` of at least 14 characters,
  or `AUTH_MODE=magic_link` with `RESEND_API_KEY` and `FROM_EMAIL`
- `RESEND_API_KEY` and `FROM_EMAIL` whenever professional invitations are used, even if the
  seeded operator still uses `AUTH_MODE=pilot_password`
- optional `INVITATION_TTL_SECONDS` (default seven days)
- `OPENAI_API_KEY` and optional `OPENAI_MODEL` (default `gpt-5.6`)
- `COOKIE_SECURE=true`
- `AUTO_CREATE_SCHEMA=false`
- `BASE_DOMAIN`, `APP_ORIGIN`, `CORS_ORIGINS`, and `TRUSTED_HOSTS`
- `UPLOAD_DIR=/data/uploads`
- Agent-native email is disabled by default. Activation requires `AGENT_MAIL_ENABLED=true`,
  `AGENT_MAIL_PROVIDER=resend`, sender/reply domains, `RESEND_API_KEY`, and
  `RESEND_WEBHOOK_SECRET`. The pilot uses the same server-side Resend key as magic-link delivery;
  inbound raw-message retrieval requires full API access. The retained later SES path instead uses
  `AGENT_MAIL_PROVIDER=ses`, a random `AGENT_MAIL_INBOUND_SECRET` of at least 32 characters, the
  standard boto3 credential chain, and a dedicated IAM key in the API-only application secret file.

The OpenAI key stays server-side. Model responses use the Responses API through the Agents SDK
with provider storage and SDK tracing disabled. No model reasoning is persisted. For an authorized
visitor photograph attached to the current turn, FastAPI verifies the private file's path, type,
size, and digest, then includes its bytes as a Base64 `input_image` with `detail: high`; the private
same-origin attachment URL is never exposed to the model provider, and historical images are not
replayed on later text turns.

The private Studio assistant has a hosted web-search tool for explicit professional requests.
Search results are treated as untrusted evidence and their URL annotations are persisted as
clickable Markdown citations. Search queries must exclude private Studio material, visitor data,
email bodies, credentials, and secrets. The public assistant has no web-search tool and remains
bounded to the active tenant configuration.

Consent-qualified Studio outreach is disabled by default. Enabling `OUTREACH_ENABLED=true`
requires agent mail, keeps public-source candidates research-only for 30 days by default, caps a
campaign through `OUTREACH_MAX_RECIPIENTS=5`, and accepts only `explicit_consent` or
`existing_customer_similar_services` as send bases. One authenticated action authorizes the exact
sealed bundle; opaque-token unsubscribe and provider complaint/bounce/suppression events block later
preparation. Public availability alone never permits delivery.

## HTTP contract

All product routes use `/api/v1`. The main groups are:

- `/auth/*` — auth mode, pilot login, purpose-bound single-use signup, invitation, and login
  links, session, and logout;
- `/public/{slug}` and `/public/conversations/*` — active public presentation and anonymous
  continuation-token conversations;
- `/studio/*` — authorized professional invitation, dormant-space slug claim, private Studio
  conversation, configuration proposal/activation, public conversations, professional join, AI
  pause/resume, memory correction, explicit human authorization of sealed email drafts, and
  consent-qualified outreach bundles;
- `/outreach/unsubscribe` — opaque-token public suppression request with a non-enumerating response;
- `/integrations/professional-email/resend` — signed Resend receiving webhook; the API retrieves the
  original raw email, stores it as untrusted data, and never causes an automatic reply;
- `/integrations/professional-email/inbound` — retained HMAC-authenticated SES/S3 relay ingestion
  endpoint for the planned later provider switch;
- `/public/conversations/{id}/attachments` and `/attachments/*` — limited private image/audio
  media with cookie-authorized same-origin content and server-side transcription;
- `/healthz`, `/readyz`, `/version` — operations endpoints (also exposed under `/api/v1`).

Public conversation transport is conventional REST for this release. App-owned PostgreSQL
records are the durable source of truth, so a future ChatKit transport can implement its store
contract without creating a second chat database.

## Professional entry lifecycle

`POST /auth/magic-link/request` is the single email-first entry point. Existing members receive an
ordinary login link. Unknown addresses receive an expiring pre-tenant signup proof; the API creates
the separate account, inactive space, and private Studio only after `POST /auth/signup/consume`
verifies that proof. Consuming one link invalidates its siblings. New members do not inherit
invitation permission, and nothing resolves publicly before an explicit first activation.

`POST /studio/invitations` is available only to a member with `can_invite=true`. It creates a new
tenant and inactive space before sending the recipient a purpose-bound invitation link. The
recipient talks to Studio while the space is private, claims a globally unique slug through
`PATCH /studio/space/slug`, and activates a draft through the ordinary revision endpoint. First
activation marks the space published and makes the shared public routes resolve it. Invited
members do not inherit invitation permission and can request ordinary login magic links after the
invitation has been consumed.

## Pilot capacity and abuse ceilings

The current pilot enforces these platform-owned boundaries. They are deterministic application
controls, not tenant-configurable assistant behavior, lead stages, or a real-estate methodology.

| Boundary | Pilot ceiling |
| --- | --- |
| Durable image payloads per account | 512 MiB |
| Durable image payloads per conversation | 50 MiB |
| Attachment records per conversation | 20, including image and audio records |
| Audio transcriptions per account | 12 in a rolling hour |
| Model-backed public-assistant turns per space | 60 in a rolling hour |
| New public conversations per space | 60 in a rolling hour |
| Professional email entry | 8 requests per IP in 15 minutes, 3 per address in one hour, and 60 new-address requests per API process in one hour |
| Unengaged public conversations per space | 60; an item with no visitor/professional message, professional participation, or bound attachment expires after one hour and is pruned when another conversation is opened |
| Studio public-conversation inbox | Offset pages of 1–100 conversations; older pages remain reachable |
| Professional email authorization | 10 human-authorized attempts per member in a rolling hour |

The Studio inbox page size bounds one request; it does not delete or hide older reachable pages.
The API enforces `CONVERSATION_RETENTION_DAYS` automatically after a five-minute startup grace and
every six hours thereafter, using the same scoped file-and-record deletion routine as an explicit
request. Failures are logged and retried at the next interval. Raw audio is temporary and deleted
after transcription. Failed or cancelled transcription rows are released immediately while the
account-level attempt event remains part of the rolling spend ceiling. An image or transcript that
is still unbound after one hour is treated as an abandoned draft, including in a never-engaged
conversation: the worker, and safely the next upload, delete its row and unlink any private image
payload. Bound attachment records remain subject to the per-conversation count. Durable-byte
ceilings apply to retained image payloads. Rate-limited requests fail with a retryable HTTP 429;
storage and attachment-count conflicts fail without accepting another durable upload.
Expired pre-tenant signup proofs are removed one day after they cease to be usable.
