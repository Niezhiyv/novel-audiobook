from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from app.tts.base import AudioClip


class KokoroConfigurationError(RuntimeError):
    pass


class KokoroTTSEngine:
    def __init__(
        self,
        model_path: Path,
        voices_path: Path,
        voices: Mapping[str, str],
        *,
        language: str = "cmn",
        vocab_path: Path | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.voices_path = Path(voices_path)
        self.voices = dict(voices)
        self.language = language
        self.vocab_path = Path(vocab_path) if vocab_path else None
        self._kokoro: Any = None

    def _load(self) -> Any:
        if self._kokoro is not None:
            return self._kokoro
        missing = [
            str(path)
            for path in (self.model_path, self.voices_path)
            if not path.is_file()
        ]
        if self.vocab_path is not None and not self.vocab_path.is_file():
            missing.append(str(self.vocab_path))
        if missing:
            raise KokoroConfigurationError(
                "Kokoro 模型配置不完整，缺少文件: " + ", ".join(missing)
            )
        try:
            from kokoro_onnx import Kokoro

            self._kokoro = Kokoro(
                str(self.model_path),
                str(self.voices_path),
                vocab_config=str(self.vocab_path) if self.vocab_path else None,
            )
        except Exception as error:
            raise KokoroConfigurationError(f"无法加载 Kokoro 模型: {error}") from error
        return self._kokoro

    def synthesize(self, text: str, voice_id: str, speed: float) -> AudioClip:
        if not text.strip():
            raise ValueError("待合成文本不能为空")
        if not 0.5 <= speed <= 2.0:
            raise ValueError("Kokoro 语速必须在 0.5 到 2.0 之间")
        actual_voice = self.voices.get(voice_id)
        if actual_voice is None:
            raise ValueError(f"未知音色: {voice_id}")
        try:
            samples, sample_rate = self._load().create(
                text,
                voice=actual_voice,
                speed=speed,
                lang=self.language,
            )
        except KokoroConfigurationError:
            raise
        except Exception as error:
            raise RuntimeError(f"Kokoro 合成失败: {error}") from error
        return AudioClip(np.asarray(samples, dtype=np.float32), int(sample_rate))

