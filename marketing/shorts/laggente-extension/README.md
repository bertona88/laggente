# LAGGENTE — Un'estensione del professionista

Editable production package for the Italian 9:16 product explainer aimed at real-estate professionals.

## Video contract

- Audience: Italian real-estate professionals evaluating LAGGENTE.
- Purpose: explain the product through three linked experiences while showing the professional as the author and participant.
- Progression: Studio Experience → Sharing Link Experience → User Experience.
- Payoff: LAGGENTE is an extension of the professional.
- Format: 1080×1920, 30 fps, H.264/yuv420p, AAC, 38.4 seconds.
- Audio: Italian ElevenLabs narration, voice-led, with a quiet original tonal bed.
- Captions: edited semantic phrases, readable muted, within the vertical-social safe zone.
- Exact material: current LAGGENTE UI, typography, colors, logo treatment, and public role labels.
- Reconstructed material: demo conversations and camera motion are rendered from exact application states with fictional data.
- Graphic material: the sharing-link bridge and final extension map are deterministic SVG/code scenes.

## Authored choice

One clay-colored line carries the same object through the film: it begins beside Studio, becomes the shared public link, continues through the visitor conversation, and ends attached to the professional. It is a visual representation of the persistent conversational thread, not an additional AI role.

## Source files

- `voiceover.txt`: approved Italian narration text.
- `mock-api.mjs`: local-only fictional API used to capture exact application states.
- `generate-voiceover.mjs`: ElevenLabs narration generator. Reads `ELEVENLABS_API_KEY` from the environment and never stores it.
- `render_short.py`: deterministic picture, tonal bed, caption, and final render pipeline.
- `assets/share-link.svg`: the non-product sharing transition. It does not imply an in-app Share button.
- `assets/extension-map.svg`: closing product map.
- `assets/screens/`: exact browser captures produced from the live/public or local demo application.
- `dist/`: final delivery files and inspection output.

## Capture

Run the mock API and the existing web app in separate terminals:

```sh
node marketing/shorts/laggente-extension/mock-api.mjs
npm --prefix apps/web run dev
```

Capture at a 540×960 browser viewport. The renderer scales the source states by 2× to 1080×1920 without changing their 9:16 composition.

## Narration

```sh
ELEVENLABS_API_KEY=... node marketing/shorts/laggente-extension/generate-voiceover.mjs
```

The delivered voiceover was generated through the ElevenLabs API with Brian
(`nPczCjzI2devNBz1zQrb`) and `eleven_v3`. The API key was supplied at runtime,
was read silently from standard input, and is not stored in this package.

If the account cannot use library voices through the API, generate a one-off
ElevenLabs Voice Design preview instead. This produces the narration without
saving a new reusable voice to the account:

```sh
ELEVENLABS_API_KEY=... node marketing/shorts/laggente-extension/generate-voiceover.mjs --voice-design
```

## Render

```sh
python3 marketing/shorts/laggente-extension/render_short.py
```

The render script writes the finished MP4 and a muted review copy to `dist/`.
