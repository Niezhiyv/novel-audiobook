from __future__ import annotations

import hashlib
import json
import os
import unicodedata
import uuid
from pathlib import Path

import soundfile as sf

from app.tts.base import TTSEngine

_SENTENCE_PUNCTUATION = "。！？；.!?;\n"
_SOFT_PUNCTUATION = "，、,:："


def chunk_text(text: str, max_chars: int = 180) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        candidates = [
            index + 1
            for index, character in enumerate(window[:max_chars])
            if character in _SENTENCE_PUNCTUATION + _SOFT_PUNCTUATION
        ]
        split_at = candidates[-1] if candidates else max_chars
        if split_at == 0:
            split_at = max_chars
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks


class AudioCache:
    def __init__(self, root: Path, model_version: str) -> None:
        self.root = Path(root)
        self.model_version = model_version

    def key(self, text: str, voice_id: str, speed: float) -> str:
        normalized = unicodedata.normalize("NFC", text.strip())
        payload = json.dumps(
            {
                "text": normalized,
                "voice_id": voice_id,
                "speed": round(float(speed), 6),
                "model_version": self.model_version,
                "chunking": "v1",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def path_for(self, text: str, voice_id: str, speed: float) -> Path:
        return self.root / f"{self.key(text, voice_id, speed)}.wav"

    def get_or_create(
        self,
        text: str,
        voice_id: str,
        speed: float,
        engine: TTSEngine,
    ) -> Path:
        destination = self.path_for(text, voice_id, speed)
        if destination.is_file():
            return destination

        self.root.mkdir(parents=True, exist_ok=True)
        clip = engine.synthesize(text, voice_id, speed)
        temporary = self.root / f".{destination.stem}.{uuid.uuid4().hex}.tmp.wav"
        try:
            sf.write(
                temporary,
                clip.samples,
                clip.sample_rate,
                format="WAV",
                subtype="FLOAT",
            )
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

