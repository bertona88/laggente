# Studio chat and voice correction — 2026-09-14

The private Studio now has new chats and paginated history; the selected chat is retained in the
URL. Opening a chat preserves the account's space, configuration, drafts, and source library.
Both text and voice routes authorize the selected account/space/private conversation. Legacy
requests without a selection keep the original Studio conversation.

Voice fragments are displayed in the main conversation, deduplicated against persisted events,
and grouped without modifying original records. Backend answers remain inspectable under
“Dettagli della richiesta”. The duplicate transcript panel was removed. Voice controls and a local
“Prova audio” tone are available in the composer. Audio is resumed after microphone/worklet setup,
and a playback indicator is driven by rendered samples.

## Evidence and limits

- API suite: 128 passing tests, including chat isolation, unchanged space configuration, history
  pagination, selected-chat voice tickets, and persisted fragment metadata.
- Web suite: 94 passing tests; build and ESLint pass. The final mobile interaction check covered
  history selection, new chat, and the local audio test without horizontal overflow.
- Browser test: synthetic Italian speech through real GPT-Live and the real Studio backend on
  isolated SQLite data. New chat, backend response, graceful stop, reload, switching back to an old
  chat without cross-chat messages, and reopening the new chat all passed. No page errors or
  horizontal overflow were observed. Audio measured after the actual worklet had a nonzero peak
  of 0.341796875 (normalized PCM).
- Visual QA found and corrected the old fixed-row grid overlapping the new history navigation.
  Tool-detail rows no longer split a spoken sentence. Naive SQLite UTC timestamps are normalized
  before live/persisted timeline ordering, matching the existing display-time convention.
- Microphone setup suspending the audio context is covered by a regression test; output is resumed
  again before the voice stream is started. This is a guarded lifecycle correction, not proof of
  the cause of the user's earlier silence.

Physical speakers/headphones, the user's browser/output selection, echo cancellation, and subjective
barge-in quality remain unverified. Receiving audio and even rendering nonzero PCM do not prove
that a human heard it. The audio test gives the user a direct check of their browser output.

## Production release

Release `199180d0acf7ba4cb4167b8b4b88696b16c94227` was activated on 2026-09-14 and
confirmed by the public version endpoint. Production smoke and the read-only operational audit
passed: all containers healthy, loopback-only gateway, and verified backup checksums.
Unauthenticated private chat history returns HTTP 401.

A real-provider browser voice check on the public Mauro site completed a technical configuration
question, received the backend result, rendered nonzero PCM (peak 0.306640625), stopped gracefully,
and retained the conversation after reload. It reported no page errors, no horizontal overflow,
and no duplicate transcript panel. Authenticated private chat switching was verified locally as
described above; physical listening on the user's device remains unverified.

## Focused voice interface — 2026-09-15

Following user confirmation that voice works, the audio test and expandable voice information
were removed. Starting voice now opens an opaque, full-screen native dialog with AI identity,
one termination button, and an indicator driven by measured microphone/playback RMS. The native
modal makes the underlying chat inert; ending restores it. No voice model or voice selection changed.

Build, lint, and the 94 existing web tests passed; an additional worklet test checks microphone,
playback, and silence levels. Desktop/mobile Chrome browser QA with synthetic audio and a mocked
transport verified one control, changing audio-driven scale, no page errors, and restored chat.
Screenshots were visually inspected at 1280×900 and 390×844.
