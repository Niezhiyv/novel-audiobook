from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(slots=True)
class AudioClip:
    samples: np.ndarray
    sample_rate: int

    def __post_init__(self) -> None:
        self.samples = np.asarray(self.samples, dtype=np.float32)
        if self.samples.ndim != 1:
            raise ValueError("音频片段必须是单声道一维数组")
        if self.samples.size == 0:
            raise ValueError("音频片段不能为空")
        if self.sample_rate <= 0:
            raise ValueError("采样率必须大于 0")


class TTSEngine(Protocol):
    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioClip:
        ...

