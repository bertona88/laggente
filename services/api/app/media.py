from __future__ import annotations

from pathlib import Path
from typing import Protocol

from openai import AsyncOpenAI

from .config import Settings
from .models import Attachment


ALLOWED_MEDIA_TYPES = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "audio/mpeg": ("audio", ".mp3"),
    "audio/wav": ("audio", ".wav"),
    "audio/x-wav": ("audio", ".wav"),
    "audio/webm": ("audio", ".webm"),
    "audio/ogg": ("audio", ".ogg"),
    "audio/mp4": ("audio", ".m4a"),
}

def attachment_content_url(attachment: Attachment) -> str:
    """Return the stable same-origin URL; the endpoint authorizes every request by cookie/header."""

    return f"/api/v1/attachments/{attachment.id}/content"


def media_magic_matches(data: bytes, media_type: str) -> bool:
    if media_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if media_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if media_type in {"audio/wav", "audio/x-wav"}:
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    if media_type == "audio/ogg":
        return data.startswith(b"OggS")
    if media_type == "audio/webm":
        return data.startswith(b"\x1aE\xdf\xa3")
    if media_type == "audio/mp4":
        return len(data) >= 12 and data[4:12].find(b"ftyp") >= 0
    if media_type == "audio/mpeg":
        return data.startswith(b"ID3") or (
            len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0
        )
    return False


class AudioTranscriber(Protocol):
    async def transcribe(self, path: Path, media_type: str) -> str: ...


class OpenAIAudioTranscriber:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe(self, path: Path, media_type: str) -> str:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        async with AsyncOpenAI(api_key=self.settings.openai_api_key) as client:
            with path.open("rb") as audio_file:
                result = await client.audio.transcriptions.create(
                    model=self.settings.openai_transcription_model,
                    file=audio_file,
                    language="it",
                )
        text = getattr(result, "text", None)
        if not text or not str(text).strip():
            raise RuntimeError("Empty transcription")
        return str(text).strip()
