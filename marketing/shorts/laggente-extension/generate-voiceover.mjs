import { readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const voiceId = process.env.ELEVENLABS_VOICE_ID || "nPczCjzI2devNBz1zQrb";
const modelId = process.env.ELEVENLABS_MODEL_ID || "eleven_v3";
const apiKey = process.env.ELEVENLABS_API_KEY;
const useVoiceDesign = process.argv.includes("--voice-design");

if (!apiKey) throw new Error("ELEVENLABS_API_KEY is required.");

const text = (await readFile(path.join(root, "voiceover.txt"), "utf8"))
  .split(/\n\s*\n/)
  .map((part) => part.trim())
  .filter(Boolean)
  .join("\n\n");

const response = useVoiceDesign
  ? await fetch(
      "https://api.elevenlabs.io/v1/text-to-voice/design?output_format=mp3_44100_192",
      {
        method: "POST",
        headers: { "content-type": "application/json", "xi-api-key": apiKey },
        body: JSON.stringify({
          voice_description:
            "Native Italian male voice in his late thirties. Warm, grounded and confident without sounding like an advertisement. Natural conversational cadence, precise diction, understated energy, close-mic studio recording, suitable for a refined short-form product film.",
          text,
          auto_generate_text: false,
          seed: 250825,
          quality: 0.92,
          guidance_scale: 4.5,
          loudness: 0.35,
        }),
      },
    )
  : await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}?output_format=mp3_44100_128`,
      {
        method: "POST",
        headers: { "content-type": "application/json", "xi-api-key": apiKey },
        body: JSON.stringify({
          text,
          model_id: modelId,
          seed: 250825,
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.82,
            style: 0.12,
            use_speaker_boost: true,
            speed: 1.02,
          },
        }),
      },
    );

if (!response.ok) {
  throw new Error(`ElevenLabs returned ${response.status}: ${(await response.text()).slice(0, 800)}`);
}

const rawPath = path.join(root, "assets", "voiceover.raw.mp3");
const outputPath = path.join(root, "assets", "voiceover.mp3");
if (useVoiceDesign) {
  const payload = await response.json();
  const preview = payload.previews?.[0];
  if (!preview?.audio_base_64) {
    throw new Error("ElevenLabs Voice Design returned no audio preview.");
  }
  await writeFile(rawPath, Buffer.from(preview.audio_base_64, "base64"));
} else {
  await writeFile(rawPath, new Uint8Array(await response.arrayBuffer()));
}

await new Promise((resolve, reject) => {
  const child = spawn("ffmpeg", [
    "-hide_banner", "-loglevel", "error", "-y",
    "-i", rawPath,
    "-af", "highpass=f=60,lowpass=f=12000,equalizer=f=170:t=q:w=1.1:g=1.2,loudnorm=I=-18:LRA=6:TP=-2",
    "-codec:a", "libmp3lame", "-b:a", "160k", outputPath,
  ], { stdio: "inherit" });
  child.once("error", reject);
  child.once("exit", (code) => code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`)));
});

console.log(`Wrote ${outputPath}`);
