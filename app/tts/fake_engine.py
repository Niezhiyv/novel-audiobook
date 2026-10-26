from __future__ import annotations

import hashlib

import numpy as np

from app.tts.base import AudioClip


class FakeTTSEngine:
    sample_rate = 24_000

    def __init__(self, sample_rate: int = 24_000) -> None:
        self.sample_rate = sample_rate

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioClip:
        if not text.strip():
            raise ValueError("待合成文本不能为空")
        digest = hashlib.sha256(f"{text}\0{voice_id}".encode("utf-8")).digest()
        frequency = 180.0 + digest[0] * 1.4
        duration = max(0.25, len(text) * 0.04 / max(speed, 0.1))
        sample_count = max(1, round(duration * self.sample_rate))
        timeline = np.arange(sample_count, dtype=np.float32) / self.sample_rate
        phase = digest[1] / 255.0 * 2.0 * np.pi
        samples = 0.08 * np.sin(2.0 * np.pi * frequency * timeline + phase)
        return AudioClip(samples.astype(np.float32), self.sample_rate)

