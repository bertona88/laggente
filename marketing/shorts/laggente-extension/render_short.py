#!/usr/bin/env python3
"""Render the LAGGENTE 9:16 product short from exact app captures.

The application screens are browser captures. Camera movement, captions, the
sharing-link bridge, the closing map, and the quiet tonal bed are authored here
so the whole piece remains deterministic and editable.
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SCREENS = ASSETS / "screens"
WORK = ROOT / "work"
DIST = ROOT / "dist"

WIDTH = 1080
HEIGHT = 1920
FPS = 30
BASE_DURATION = 38.4

PAPER = "#f1eee5"
PAPER_LIGHT = "#f8f6ef"
INK = "#17231d"
MOSS = "#26382e"
OLIVE = "#c2c99a"
CLAY = "#a96343"
MUTED = "#72786f"

SERIF_PATH = Path("/System/Library/Fonts/Supplemental/Iowan Old Style.ttc")
SANS_PATH = Path("/System/Library/Fonts/SFNS.ttf")


@dataclass(frozen=True)
class Scene:
    start: float
    end: float
    kind: str
    source: str | None
    chapter: str
    caption: str
    caption_y: int
    pan_x: float = 0.0
    pan_y: float = 0.0


SCENES = (
    Scene(0.0, 4.6, "screen", "studio-chat.png", "01 / STUDIO EXPERIENCE", "Parte dallo Studio.", 1360, -0.12, 0.10),
    Scene(4.6, 10.2, "screen", "studio-preview.png", "01 / STUDIO EXPERIENCE", "Racconti come lavori.", 1430, 0.12, -0.10),
    Scene(10.2, 16.4, "screen", "studio-activate.png", "01 / STUDIO EXPERIENCE", "Vedi. Correggi. Attivi.", 1460, 0.0, 0.04),
    Scene(16.4, 19.5, "share", None, "02 / SHARING LINK EXPERIENCE", "", 0),
    Scene(19.5, 23.2, "screen", "public-start.png", "03 / USER EXPERIENCE", "La gente entra.", 1290, -0.08, 0.10),
    Scene(23.2, 27.5, "screen", "public-conversation.png", "03 / USER EXPERIENCE", "La conversazione resta.", 1280, 0.08, -0.05),
    Scene(27.5, 31.1, "screen", "studio-conversation.png", "03 / USER EXPERIENCE", "Tu la ritrovi.", 1320, -0.05, 0.04),
    Scene(31.1, 34.7, "screen", "studio-joined.png", "03 / USER EXPERIENCE", "Quando serve, entri tu.", 1430, 0.06, -0.05),
    Scene(34.7, BASE_DURATION, "extension", None, "LAGGENTE", "", 0),
)


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def serif(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(SERIF_PATH), size=size, index=0)


def sans(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(SANS_PATH), size=size)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def fade_window(progress: float, edge: float = 0.12) -> float:
    return clamp(min(progress / edge, (1.0 - progress) / edge))


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_chapter(frame: Image.Image, label: str, opacity: float = 1.0) -> None:
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = int(242 * clamp(opacity))
    bbox = (66, 128, 620, 198)
    draw.rounded_rectangle(bbox, radius=12, fill=(248, 246, 239, alpha), outline=(169, 99, 67, alpha), width=2)
    draw.text((94, 151), label, font=sans(25), fill=(169, 99, 67, int(255 * opacity)), anchor="lm")
    frame.alpha_composite(overlay)


def draw_thread(frame: Image.Image, progress: float, light: bool = False) -> None:
    draw = ImageDraw.Draw(frame)
    color = OLIVE if light else CLAY
    y0, y1 = 224, int(224 + (1645 - 224) * clamp(progress))
    draw.line((48, y0, 48, y1), fill=color, width=5)
    draw.ellipse((39, y1 - 9, 57, y1 + 9), fill=color)


def draw_caption(frame: Image.Image, text: str, y: int, opacity: float = 1.0) -> None:
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = serif(68)
    lines = wrap(draw, text, font, 820)
    line_height = 78
    height = 60 + line_height * len(lines)
    x0, x1 = 68, 1012
    draw.rounded_rectangle(
        (x0, y, x1, y + height),
        radius=20,
        fill=(248, 246, 239, int(246 * opacity)),
        outline=(169, 99, 67, int(255 * opacity)),
        width=3,
    )
    for index, line in enumerate(lines):
        draw.text((112, y + 31 + index * line_height), line, font=font, fill=(23, 35, 29, int(255 * opacity)))
    frame.alpha_composite(overlay)


def load_screens() -> dict[str, Image.Image]:
    required = {scene.source for scene in SCENES if scene.source}
    screens: dict[str, Image.Image] = {}
    for name in sorted(required):
        assert name is not None
        path = SCREENS / name
        if not path.exists():
            raise SystemExit(f"Missing browser capture: {path}")
        image = Image.open(path).convert("RGB")
        if image.size != (540, 960):
            raise SystemExit(f"Expected a 540x960 capture, got {image.size}: {path}")
        screens[name] = image
    return screens


def render_screen(scene: Scene, progress: float, screens: dict[str, Image.Image], global_progress: float) -> Image.Image:
    assert scene.source
    source = screens[scene.source]
    push = 1.018 + 0.018 * ease(progress)
    width = round(WIDTH * push)
    height = round(HEIGHT * push)
    image = source.resize((width, height), Image.Resampling.LANCZOS)
    spare_x = width - WIDTH
    spare_y = height - HEIGHT
    x = int(spare_x * (0.5 + scene.pan_x * (ease(progress) - 0.5)))
    y = int(spare_y * (0.5 + scene.pan_y * (ease(progress) - 0.5)))
    image = image.crop((x, y, x + WIDTH, y + HEIGHT))
    image = ImageEnhance.Contrast(image).enhance(1.015).convert("RGBA")

    local_fade = clamp(progress / 0.10)
    draw_thread(image, global_progress)
    draw_chapter(image, scene.chapter, local_fade)
    draw_caption(image, scene.caption, scene.caption_y, fade_window(progress, 0.10))
    return image


def draw_share(progress: float, global_progress: float) -> Image.Image:
    frame = Image.new("RGBA", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(frame)
    p = ease(progress)
    draw_thread(frame, global_progress)
    draw_chapter(frame, "02 / SHARING LINK EXPERIENCE", clamp(progress / 0.10))

    title_alpha = int(255 * clamp(progress / 0.18))
    draw.text((84, 292), "Condividi", font=serif(104), fill=(23, 35, 29, title_alpha))
    draw.text((84, 396), "il tuo spazio.", font=serif(104), fill=(23, 35, 29, title_alpha))

    card_y = int(635 + (1.0 - p) * 44)
    draw.rounded_rectangle((84, card_y, 996, card_y + 250), radius=20, fill=PAPER_LIGHT, outline="#cecfc6", width=3)
    draw.text((132, card_y + 73), "SPAZIO PUBBLICO", font=sans(23), fill=MUTED)
    draw.text((132, card_y + 172), "mauro", font=serif(58), fill=CLAY)
    draw.text((302, card_y + 172), ".laggente.com", font=serif(58), fill=INK)

    line_start = card_y + 250
    line_end = 1118
    line_progress = ease(clamp((progress - 0.18) / 0.42))
    current_end = int(line_start + (line_end - line_start) * line_progress)
    draw.line((540, line_start, 540, current_end), fill=CLAY, width=6)
    if line_progress > 0.96:
        draw.ellipse((527, line_end - 13, 553, line_end + 13), fill=CLAY)

    share_progress = ease(clamp((progress - 0.46) / 0.36))
    share_y = int(1185 + (1.0 - share_progress) * 70)
    share_alpha = int(255 * share_progress)
    share_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    share_draw = ImageDraw.Draw(share_layer)
    share_draw.rounded_rectangle((170, share_y, 910, share_y + 282), radius=40, fill=(38, 56, 46, share_alpha))
    share_draw.text((230, share_y + 82), "LINK CONDIVISO", font=sans(23), fill=(194, 201, 154, share_alpha))
    share_draw.text((230, share_y + 181), "mauro.laggente.com", font=serif(47), fill=(248, 246, 239, share_alpha))
    frame.alpha_composite(share_layer)
    draw = ImageDraw.Draw(frame)
    draw.text((84, 1712), "Un link normale. Uno spazio personale.", font=sans(31), fill=INK)
    return frame


def draw_extension(progress: float, global_progress: float) -> Image.Image:
    frame = Image.new("RGBA", (WIDTH, HEIGHT), MOSS)
    draw = ImageDraw.Draw(frame)
    p = ease(progress)
    draw_thread(frame, global_progress, light=True)

    draw.text((84, 164), "LAGGENTE", font=sans(27), fill=OLIVE)
    title_alpha = int(255 * clamp(progress / 0.16))
    draw.text((84, 318), "Un’estensione", font=serif(102), fill=(248, 246, 239, title_alpha))
    draw.text((84, 425), "del professionista.", font=serif(102), fill=(248, 246, 239, title_alpha))

    node_progress = ease(clamp((progress - 0.10) / 0.22))
    radius = int(118 * node_progress)
    draw.ellipse((540 - radius, 766 - radius, 540 + radius, 766 + radius), fill=CLAY)
    if node_progress > 0.55:
        draw.text((540, 748), "MAURO", font=sans(28), fill=PAPER_LIGHT, anchor="mm")
        draw.text((540, 795), "agente immobiliare", font=sans(21), fill=PAPER_LIGHT, anchor="mm")

    flow = ease(clamp((progress - 0.24) / 0.42))
    line1_end = int(884 + (1045 - 884) * clamp(flow * 2.0))
    draw.line((540, 884, 540, line1_end), fill=OLIVE, width=6)
    if flow > 0.30:
        box_alpha = int(255 * clamp((flow - 0.30) / 0.18))
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((178, 1045, 902, 1205), radius=18, fill=(248, 246, 239, box_alpha))
        ld.text((540, 1113), "STUDIO", font=sans(26), fill=(23, 35, 29, box_alpha), anchor="mm")
        ld.text((540, 1160), "costruisce lo spazio con te", font=serif(30), fill=(114, 120, 111, box_alpha), anchor="mm")
        frame.alpha_composite(layer)

    draw = ImageDraw.Draw(frame)
    line2_progress = clamp((flow - 0.42) / 0.28)
    draw.line((540, 1205, 540, int(1205 + 155 * line2_progress)), fill=OLIVE, width=6)
    if flow > 0.60:
        box_alpha = int(255 * clamp((flow - 0.60) / 0.18))
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((178, 1360, 902, 1520), radius=18, fill=(248, 246, 239, box_alpha))
        ld.text((540, 1427), "SPAZIO PUBBLICO", font=sans(25), fill=(23, 35, 29, box_alpha), anchor="mm")
        ld.text((540, 1475), "accoglie la gente", font=serif(30), fill=(114, 120, 111, box_alpha), anchor="mm")
        frame.alpha_composite(layer)

    people_progress = ease(clamp((progress - 0.58) / 0.22))
    draw = ImageDraw.Draw(frame)
    draw.line((540, 1520, 540, int(1520 + 135 * people_progress)), fill=OLIVE, width=6)
    for x, delay in ((410, 0.0), (540, 0.08), (670, 0.16)):
        person_p = ease(clamp((people_progress - delay) / (1.0 - delay)))
        r = int(43 * person_p)
        draw.ellipse((x - r, 1710 - r, x + r, 1710 + r), fill=PAPER_LIGHT)
    draw.text((540, 1810), "LA GENTE", font=sans(25), fill=OLIVE, anchor="mm")
    return frame


def scene_at(base_time: float) -> Scene:
    for scene in SCENES:
        if scene.start <= base_time < scene.end:
            return scene
    return SCENES[-1]


def render_frame(time_seconds: float, duration: float, screens: dict[str, Image.Image]) -> Image.Image:
    base_time = time_seconds / duration * BASE_DURATION
    scene = scene_at(base_time)
    progress = clamp((base_time - scene.start) / (scene.end - scene.start))
    global_progress = clamp(time_seconds / duration)
    if scene.kind == "screen":
        return render_screen(scene, progress, screens, global_progress)
    if scene.kind == "share":
        return draw_share(progress, global_progress)
    return draw_extension(progress, global_progress)


def make_bed(path: Path, duration: float) -> None:
    sample_rate = 44_100
    total = int(duration * sample_rate)
    notes = (130.81, 164.81, 196.00)
    phrase = 4.0
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        block = bytearray()
        for index in range(total):
            t = index / sample_rate
            local = t % phrase
            attack = clamp(local / 0.42)
            release = clamp((phrase - local) / 1.25)
            envelope = min(attack, release) ** 1.8
            shimmer = 0.72 + 0.28 * math.sin(2 * math.pi * 0.07 * t)
            sample = 0.0
            for note_index, frequency in enumerate(notes):
                sample += math.sin(2 * math.pi * frequency * t + note_index * 0.6) / (note_index + 1.5)
            sample += 0.22 * math.sin(2 * math.pi * 261.63 * t)
            value = int(max(-1.0, min(1.0, sample * envelope * shimmer * 0.024)) * 32767)
            block.extend(value.to_bytes(2, "little", signed=True))
            block.extend(value.to_bytes(2, "little", signed=True))
            if len(block) >= 65_536:
                wav.writeframes(block)
                block.clear()
        if block:
            wav.writeframes(block)


def render_picture(path: Path, duration: float, screens: dict[str, Image.Image]) -> list[Image.Image]:
    frame_count = round(duration * FPS)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    samples: list[Image.Image] = []
    sample_indices = {round((frame_count - 1) * i / 7) for i in range(8)}
    assert process.stdin is not None
    try:
        for index in range(frame_count):
            frame = render_frame(index / FPS, duration, screens).convert("RGB")
            process.stdin.write(frame.tobytes())
            if index in sample_indices:
                samples.append(frame.copy())
            if index % 150 == 0:
                print(f"Rendered {index}/{frame_count} frames", flush=True)
    finally:
        process.stdin.close()
    code = process.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg picture encode failed with exit code {code}")
    return samples


def make_contact_sheet(samples: list[Image.Image], path: Path) -> None:
    thumb_size = (270, 480)
    sheet = Image.new("RGB", (WIDTH, 960), PAPER)
    for index, frame in enumerate(samples[:8]):
        thumb = frame.resize(thumb_size, Image.Resampling.LANCZOS)
        x = (index % 4) * thumb_size[0]
        y = (index // 4) * thumb_size[1]
        sheet.paste(thumb, (x, y))
    sheet.save(path, quality=94)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voiceover", type=Path, default=ASSETS / "voiceover.mp3")
    parser.add_argument("--allow-bed-only", action="store_true", help="Render a visual/audio draft if narration is unavailable.")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe are required")
    if not SERIF_PATH.exists() or not SANS_PATH.exists():
        raise SystemExit("Required system fonts are missing")

    voiceover = args.voiceover.resolve()
    has_voice = voiceover.exists()
    if not has_voice and not args.allow_bed_only:
        raise SystemExit(f"Narration is missing: {voiceover}. Generate or supply it before the final render.")

    duration = BASE_DURATION
    if has_voice:
        duration = max(BASE_DURATION, ffprobe_duration(voiceover) + 0.9)

    WORK.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    screens = load_screens()
    picture = WORK / "picture.mp4"
    bed = WORK / "tonal-bed.wav"
    samples = render_picture(picture, duration, screens)
    make_bed(bed, duration)
    make_contact_sheet(samples, DIST / "contact-sheet.png")

    muted = DIST / "laggente-extension-muted.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(picture), "-c:v", "copy", "-an", str(muted)])

    if has_voice:
        final = DIST / "laggente-extension-it.mp4"
        filter_complex = (
            f"[1:a]highpass=f=60,lowpass=f=12000,apad=pad_dur={duration:.3f},"
            f"atrim=0:{duration:.3f},volume=1.0[voice];"
            f"[2:a]atrim=0:{duration:.3f},volume=0.20[bed];"
            "[voice][bed]amix=inputs=2:duration=longest:dropout_transition=0,"
            "loudnorm=I=-16:LRA=7:TP=-1.5[a]"
        )
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(picture), "-i", str(voiceover), "-i", str(bed),
            "-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}",
            "-movflags", "+faststart", str(final),
        ])
    else:
        final = DIST / "laggente-extension-bed-only.mp4"
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(picture), "-i", str(bed), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
            "-movflags", "+faststart", str(final),
        ])

    print(f"Wrote {final}")
    print(f"Wrote {muted}")
    print(f"Wrote {DIST / 'contact-sheet.png'}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Command failed with exit code {error.returncode}", file=sys.stderr)
        raise
