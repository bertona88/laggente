# GPT-Live voice validation — 2026-09-11

The feature is opt-in and has not been deployed or enabled in production by this task.
Implementation and control boundaries are in [ADR-0007](../decisions/0007-gpt-live-conversation-transport.md).

## Evidence

Final automated runs: **124 API tests** and **88 frontend tests** passed.

- API tests cover default-off behavior, authentication, exact origin, single-use and expired
  tickets, cross-host denial, durable account quotas surviving conversation deletion, simultaneous
  text rejection, continuous audio, role-specific delegation, original fragment persistence,
  visible backend-result messages, human pause, duration limits, and graceful-close errors.
- Browser lifecycle tests cover capture before/after readiness, simultaneous playback/capture,
  mute, immediate local stop with delayed server finalization, late microphone permission after
  cancellation, and network backpressure cleanup.
- Desktop (1360 px) and mobile (390 px) Chrome checks used a fake microphone, isolated SQLite
  data, a fake provider, and a deliberately delayed existing backend stub. PCM continued while
  backend work ran. Mute/resume/stop worked, captions persisted after reload, both Studio and public
  controls rendered, and the tested pages had no horizontal overflow or JavaScript page errors.
- A direct `gpt-live-1` smoke test, using no tenant data or microphone recording, returned
  `session.started`, 35 audio deltas, 8 output transcript deltas, and final `session.closed` usage.
- A browser test then used generated Italian speech through the actual AudioWorklet → local
  FastAPI → OpenAI Live path, with a fake public backend and seeded QA data. The successful run
  sent 721 input frames and received 139 audio deltas, 12 input transcript fragments, one client
  delegation, one commentary acknowledgment, 15 output transcript fragments, and `session.closed`.
  GPT-Live recognized the synthetic request about Mauro and began speaking the backend's returned
  answer. The successful run had no provider errors, browser alerts, or page errors.
- A further browser test used generated Italian speech, real GPT-Live, and the actual Studio
  AgentsAssistantService against isolated seeded SQLite data. The Studio model invoked
  `inspect_active_space_configuration`; the original tool completed and returned the seeded
  configuration. Two commentary acknowledgments followed, and GPT-Live began speaking the
  returned name and role ("Mauro Rossi, agente immobiliare"). The run sent 1293 input frames,
  received 248 audio deltas, and closed gracefully, with no captured backend/provider errors,
  browser alerts, or page errors. Tool instrumentation observed the original implementation;
  it did not replace its result. An earlier attempt ended before tool execution; its cause was
  not captured and did not recur in the instrumented run.
- Ending another synthetic run while a result was being injected revealed the documented
  `context_injection_incomplete` error. Shutdown now tolerates that specific error while draining
  to `session.closed`; a regression test verifies final usage remains available.
- Production frontend build, ESLint, and infrastructure shell/secret-boundary checks pass.
  Docker is unavailable locally, so Compose builds and nginx container execution were not tested.

## Remaining release acceptance

No physical microphone/speaker conversation, human listening assessment, production gateway
WebSocket request, or live tenant interaction was performed. Echo cancellation, speakerphone
barge-in, mobile lifecycle, perceived latency, sustained conversations, and human judgment of the
Italian voice remain device acceptance work. Real voice-to-tool execution is verified for the
Studio configuration-read tool only; public tools, document tools, and draft-producing tools have
not been exercised through a real voice session. Existing role/tool authorization is exercised
separately by application tests. The earlier interrupted attempt remains an unresolved reliability
observation.

Live voice starts only after explicit user action. Production needs an authorized deployment,
`LIVE_VOICE_ENABLED=true`, provider access, and the updated privacy notice version. No DNS,
production migration, production secret, or production service was changed.
