# ADR-0007: GPT-Live voice for the existing conversational roles

- **Status:** Accepted for opt-in implementation; production activation requires a separately authorized release
- **Date:** 2026-09-11
- **Amends:** ADR-0001's non-streaming-only transport boundary

## Context

The requested experience is an explicit voice session in which a person can speak naturally,
including while the assistant speaks or works. Dictation's record, review, and send loop remains a
fallback, but is not that experience. GPT-Live has a distinct session/event contract from the
Realtime API and delegates tasks while handling full-duplex speech.

## Decision

Use `gpt-live-1` with `delegation.type=client` as the voice interface to the existing private Studio
or public assistant. The application selects one role from authenticated context. Its existing
Agents SDK implementation remains responsible for reasoning and authorized tools. The Live model
has no tool execution authority, private coordination role, or independently routed specialist.
The system still has exactly two product roles; each can have a voice interface.

Use a same-origin browser WebSocket to FastAPI. FastAPI alone opens the primary OpenAI Live
WebSocket and sends `session.start`, immutable instructions, bounded prior history, and
`store=false`. An AudioWorklet simultaneously captures and plays mono PCM16 at 24 kHz. This avoids
allowing browsers to submit provider instructions, synthetic assistant transcripts, delegation
results, or private tool commands. The only browser inputs are bounded audio, mute/unmute, and stop.
Neither an API key nor an OpenAI client credential reaches the browser.

An authenticated HTTP request issues a single-use, 30-second ticket. The first WebSocket message
carries it, never the URL. Tickets are bound to the exact origin, account, space, conversation,
and professional/visitor authorization. The application rechecks authorization every second and
before/after backend work, and closes public sessions when replies are paused or the active
revision changes. Conversation locks prevent concurrent text turns and duplicate voice sessions.
The lease registry is bounded and process-local, consistent with the MVP's single Uvicorn worker.

Original provider transcript fragments and timestamps are preserved in conversation-owned events;
immutable `voice_transcript` messages batch them every five seconds, at delegation, and on close.
Batches are storage units, not asserted semantic turns. Overlapping speaker intervals remain in
the source fragments. Raw audio is never stored by LAGGENTE. Transcripts may include generated
words not heard during interruption or disconnection. Backend results are separate `voice_result` messages, including clickable citations,
not spoken captions; delegation start/result events link their IDs. Public memory remains derived and correctable. Deletion removes voice
messages and conversation events too. A process crash may lose the last unflushed five seconds.

Starting voice explicitly authorizes immediate speech transmission and transcript persistence.
It does not authorize public configuration activation or sending email; existing review and
approval controls remain necessary. Interrupting speech is not proof that backend work was
canceled; drafts already created remain inspectable. Closing cancels pending local work, and
reconnecting never automatically replays a delegation.

## Consequences

- `LIVE_VOICE_ENABLED=false` by default. When enabled and a server key exists, Studio and public
  chat display “Parla con l’assistente” instead of dictation/voice-note capture. Typed chat remains.
- Six starts per account per rolling hour, four simultaneous sessions across the process, at most
  twenty delegations per session, and a five-minute default duration (`LIVE_VOICE_MAX_SECONDS`,
  30–600 seconds). Account start reservations survive conversation deletion.
- Voice-duration charges and backend model charges are separate. Normal termination waits for
  `session.closed` and stores final usage. Missing final events are recorded as incomplete.
- Relay audio adds a network hop and requires buffer and microphone lifecycle QA. Unsupported
  browsers and connection failures return to text without reconnecting automatically.
- There is no new service, database, schema migration, deployment per tenant, or provider-owned
  durable conversation store. Both nginx layers must forward WebSocket upgrades.
- A one-second authorization polling interval and audio already delivered to a client mean human
  intervention cannot retroactively remove speech. The browser clears playback on termination.
- Real-device echo, interruptions, Italian speech quality, latency, and recovery remain release
  acceptance checks; mocked transport success does not establish them.

## Alternatives considered

- **Dictation or STT → text assistant → TTS:** retained as fallback; does not meet full-duplex intent.
- **Realtime speech model:** valid for other use cases, but differs from the explicitly requested
  GPT-Live architecture and would require a separate tool execution adaptation.
- **Direct browser WebRTC plus server sideband:** the provider-recommended browser transport,
  with better media handling. Deferred here because the server relay keeps every client control
  and durable transcript behind the existing application boundary. Reconsider after measuring
  relay latency and verifying provider-side restrictions on the client event channel.
- **Managed Responses delegation:** does not reuse the existing authorized assistant harness and
  application-selected context as directly as client delegation.

## Primary references

Verified 2026-09-11:

- [GPT-Live](https://developers.openai.com/api/docs/guides/live)
- [Client delegation](https://developers.openai.com/api/docs/guides/live-delegation?delegation-mode=client)
- [WebSocket contract](https://developers.openai.com/api/docs/guides/voice-websockets?api=live)
- [Transcripts, history, and graceful close](https://developers.openai.com/api/docs/guides/live-conversations)
