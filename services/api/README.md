# LAGGENTE API

FastAPI service for LAGGENTE's application-owned coordination layer and exactly two OpenAI
Agents SDK roles: the private Studio assistant and the public assistant. PostgreSQL stores
tenant-scoped spaces, active/draft configuration revisions, conversations, immutable messages,
correctable derived memory, attachments, and audit events.

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
- `OPENAI_API_KEY` and optional `OPENAI_MODEL` (default `gpt-5.6`)
- `COOKIE_SECURE=true`
- `AUTO_CREATE_SCHEMA=false`
- `BASE_DOMAIN`, `APP_ORIGIN`, `CORS_ORIGINS`, and `TRUSTED_HOSTS`
- `UPLOAD_DIR=/data/uploads`

The OpenAI key stays server-side. Model responses use the Responses API through the Agents SDK
with provider storage and SDK tracing disabled. No model reasoning is persisted. For an authorized
visitor photograph in recent conversation history, FastAPI verifies the private file's path, type,
size, and digest, then includes its bytes as a Base64 `input_image` with `detail: high`; the private
same-origin attachment URL is never exposed to the model provider.

## HTTP contract

All product routes use `/api/v1`. The main groups are:

- `/auth/*` — auth mode, pilot login, signed single-use magic links, session, logout;
- `/public/{slug}` and `/public/conversations/*` — active public presentation and anonymous
  continuation-token conversations;
- `/studio/*` — private Studio conversation, configuration proposal/activation, public
  conversations, professional join, AI pause/resume, and memory correction;
- `/public/conversations/{id}/attachments` and `/attachments/*` — limited private image/audio
  media with cookie-authorized same-origin content and server-side transcription;
- `/healthz`, `/readyz`, `/version` — operations endpoints (also exposed under `/api/v1`).

Public conversation transport is conventional REST for this release. App-owned PostgreSQL
records are the durable source of truth, so a future ChatKit transport can implement its store
contract without creating a second chat database.

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
| Unengaged public conversations per space | 60; an item with no visitor/professional message, professional participation, or bound attachment expires after one hour and is pruned when another conversation is opened |
| Studio public-conversation inbox | Offset pages of 1–100 conversations; older pages remain reachable |

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
